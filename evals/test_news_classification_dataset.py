from decimal import Decimal

import pytest
from langchain_core.language_models import BaseChatModel

from br_financial_ai.ai.news_classifier import create_news_classifier
from br_financial_ai.domain.news_signals import NewsClassificationRequest
from br_financial_ai.eval.cache import EvalResultCache
from br_financial_ai.eval.concurrency import map_bounded
from br_financial_ai.eval.datasets import dataset_cases, expected_min_cases
from br_financial_ai.eval.metrics import mean_ratio
from br_financial_ai.eval.profile import eval_llm_concurrency
from br_financial_ai.eval.runtime import RESULTS
from br_financial_ai.eval.timing import timed_eval_section
from br_financial_ai.observability.usage import (
    merge_usage,
    usage_as_dict_with_calls,
)

pytestmark = [
    pytest.mark.eval,
    pytest.mark.external,
    pytest.mark.ollama,
    pytest.mark.asyncio,
]


@pytest.mark.slow
async def test_news_classification_dataset(
    eval_chat_model: BaseChatModel,
    eval_result_cache: EvalResultCache,
) -> None:
    base = create_news_classifier(eval_chat_model)
    cases = dataset_cases("news_classification.json")

    async def run_case(case: dict) -> dict:
        request = NewsClassificationRequest(**case["request"])
        expected = case["expected"]

        async def classify():
            classifier = base.fork()
            signal = await classifier.classify(request)
            return signal, classifier.last_usage

        signal, usage = await eval_result_cache.get_or_set(
            "news",
            str(case["id"]),
            classify,
        )
        allowed = set(expected.get("categories_any") or [])
        return {
            "id": case["id"],
            "relevance": signal.relevance.value in expected["relevance"],
            "materiality": signal.materiality.value in expected["materiality"],
            "company_specific": signal.company_specific is expected["company_specific"],
            "sentiment": signal.sentiment.value in expected["sentiment"],
            "category": True if not allowed else bool(allowed & set(signal.categories)),
            "confidence": signal.confidence,
            "usage": usage,
        }

    with timed_eval_section("news_eval_seconds") as extras:
        outcomes = await map_bounded(
            cases,
            run_case,
            concurrency=eval_llm_concurrency(),
        )
        extras["news_llm_calls"] = len(outcomes)

    RESULTS["news_classification"] = {
        "cases": len(cases),
        "relevance_accuracy": mean_ratio([item["relevance"] for item in outcomes]),
        "materiality_accuracy": mean_ratio([item["materiality"] for item in outcomes]),
        "company_specific_accuracy": mean_ratio(
            [item["company_specific"] for item in outcomes]
        ),
        "sentiment_agreement": mean_ratio([item["sentiment"] for item in outcomes]),
        "category_agreement": mean_ratio([item["category"] for item in outcomes]),
        "case_ids": [item["id"] for item in outcomes],
    }
    RESULTS["llm_usage"]["news_classification"] = usage_as_dict_with_calls(
        merge_usage(*[item["usage"] for item in outcomes]),
        len(outcomes),
    )

    assert [item["id"] for item in outcomes] == [case["id"] for case in cases]
    for item in outcomes:
        assert item["confidence"] >= Decimal("0")
        assert item["confidence"] <= Decimal("1")
    assert len(cases) >= expected_min_cases("news_classification.json")
