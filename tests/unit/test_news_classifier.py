import asyncio
from dataclasses import replace
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from br_financial_ai.ai.news_classifier import (
    NEWS_CLASSIFIER_PROMPT_VERSION,
    NEWS_CLASSIFIER_VERSION,
    NewsClassificationOutput,
    NewsClassifier,
    create_news_classifier,
    parse_news_classification_output,
)
from br_financial_ai.domain.news_signals import (
    NewsClassificationRequest,
    NewsMateriality,
    NewsRelevance,
    NewsSentiment,
)
from br_financial_ai.services.exceptions import (
    NewsClassificationError,
)
from br_financial_ai.services.news_classification import (
    classifier_identity_from_settings,
)

REQUEST = NewsClassificationRequest(
    article_id=17,
    ticker="PETR4",
    company_name="PETROBRAS",
    title="Petrobras anuncia aumento de producao",
    summary="A companhia elevou o guidance de producao e capex.",
    publisher="Reuters",
)

VALID_PAYLOAD = {
    "relevance": "HIGH",
    "materiality": "HIGH",
    "sentiment": "POSITIVE",
    "company_specific": True,
    "categories": ["production", "capex", "unknown_tag"],
    "confidence": "0.86",
    "rationale": "The article reports Petrobras production and capex.",
}


def test_structured_signal_validation() -> None:
    signal = parse_news_classification_output(17, VALID_PAYLOAD)

    assert signal.article_id == 17
    assert signal.relevance is NewsRelevance.HIGH
    assert signal.materiality is NewsMateriality.HIGH
    assert signal.sentiment is NewsSentiment.POSITIVE
    assert signal.company_specific is True
    assert signal.categories == ("production", "capex")
    assert signal.confidence == Decimal("0.86")
    assert "production" in signal.rationale


def test_valid_enums_and_confidence_range() -> None:
    output = NewsClassificationOutput.model_validate(VALID_PAYLOAD)

    assert output.relevance == "HIGH"
    assert output.confidence == 0.86

    with pytest.raises(ValidationError):
        NewsClassificationOutput.model_validate(
            {**VALID_PAYLOAD, "relevance": "CRITICAL"}
        )

    with pytest.raises(ValidationError):
        NewsClassificationOutput.model_validate({**VALID_PAYLOAD, "confidence": "1.5"})


def test_malformed_model_result() -> None:
    with pytest.raises(
        NewsClassificationError,
        match="Malformed news classification result",
    ):
        parse_news_classification_output(1, {"relevance": "HIGH"})


@pytest.mark.asyncio
async def test_classifier_associates_article() -> None:
    structured_model = AsyncMock()
    structured_model.ainvoke = AsyncMock(
        return_value=NewsClassificationOutput.model_validate(
            VALID_PAYLOAD,
        )
    )
    classifier = NewsClassifier(structured_model)

    signal = await classifier.classify(REQUEST)

    assert signal.article_id == 17
    structured_model.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_news_returns_no_signals() -> None:
    classifier = NewsClassifier(AsyncMock())

    assert await classifier.classify_many([]) == []


@pytest.mark.asyncio
async def test_classify_many_preserves_order_and_isolates_failures() -> None:
    structured_model = AsyncMock()
    structured_model.ainvoke = AsyncMock(
        side_effect=[
            NewsClassificationOutput.model_validate(VALID_PAYLOAD),
            RuntimeError("bad json"),
            NewsClassificationOutput.model_validate(VALID_PAYLOAD),
        ]
    )
    classifier = NewsClassifier(structured_model, concurrency=1)
    requests = [
        replace(REQUEST, article_id=1),
        replace(REQUEST, article_id=2),
        replace(REQUEST, article_id=3),
    ]

    results = await classifier.classify_many(requests)

    assert [item.article_id if item else None for item in results] == [1, None, 3]


@pytest.mark.asyncio
async def test_classify_many_respects_concurrency_limit() -> None:
    current = 0
    peak = 0
    lock = asyncio.Lock()
    gate = asyncio.Event()

    async def fake_ainvoke(messages, config=None):
        nonlocal current, peak
        async with lock:
            current += 1
            peak = max(peak, current)
            if current == 3:
                gate.set()
        await gate.wait()
        async with lock:
            current -= 1
        return NewsClassificationOutput.model_validate(VALID_PAYLOAD)

    structured_model = AsyncMock()
    structured_model.ainvoke = fake_ainvoke
    classifier = NewsClassifier(structured_model, concurrency=3)
    requests = [replace(REQUEST, article_id=index) for index in range(6)]

    results = await classifier.classify_many(requests)

    assert [item.article_id for item in results if item is not None] == list(range(6))
    assert all(item is not None for item in results)
    assert peak == 3
    assert classifier.classification_concurrency() == 3


@pytest.mark.asyncio
async def test_classifier_wraps_model_failure() -> None:
    structured_model = AsyncMock()
    structured_model.ainvoke = AsyncMock(
        side_effect=RuntimeError("ollama down"),
    )
    classifier = NewsClassifier(structured_model)

    with pytest.raises(
        NewsClassificationError,
        match="Failed to classify news article",
    ):
        await classifier.classify(REQUEST)


def test_create_news_classifier_uses_chat_model() -> None:
    structured = Mock(name="structured")
    model = Mock()
    model.with_structured_output = Mock(return_value=structured)

    classifier = create_news_classifier(model)

    model.with_structured_output.assert_called_once_with(
        NewsClassificationOutput,
        include_raw=True,
    )
    assert classifier._structured_model is structured


def test_classifier_identity_uses_settings_and_prompt_version() -> None:
    from br_financial_ai.core.settings import get_settings

    settings = get_settings()
    identity = classifier_identity_from_settings(settings)

    assert identity.model_provider == settings.llm_provider
    assert identity.model_name == settings.llm_model
    assert identity.classifier_version == NEWS_CLASSIFIER_VERSION
    assert identity.prompt_version == NEWS_CLASSIFIER_PROMPT_VERSION
    assert identity.prompt_version == "news-v1"
