from decimal import Decimal

import pytest

from br_financial_ai.ai.news_classifier import (
    create_news_classifier,
)
from br_financial_ai.domain.news_signals import (
    NewsClassificationRequest,
    NewsRelevance,
)

pytestmark = [
    pytest.mark.eval,
    pytest.mark.external,
    pytest.mark.ollama,
    pytest.mark.slow,
]

COMPANY_SPECIFIC = NewsClassificationRequest(
    article_id=1,
    ticker="PETR4",
    company_name="Petrobras",
    title="Petrobras announces 2026 production guidance and capex plan",
    summary=(
        "Petrobras said it will raise its own oil production and increase "
        "capital expenditure on pre-salt fields. The company detailed its "
        "drilling schedule and capex budget for the next five years."
    ),
    publisher="Reuters",
)

SECTOR_GEOPOLITICS = NewsClassificationRequest(
    article_id=2,
    ticker="PETR4",
    company_name="Petrobras",
    title="Oil companies rise after Strait of Hormuz disruption fears",
    summary=(
        "Crude jumped after reports of tension in the Strait of Hormuz. "
        "Shares of Exxon, Shell, BP and Petrobras moved higher along with "
        "the broader oil sector. No company-specific operational update "
        "was provided."
    ),
    publisher="Bloomberg",
)

WEAK_MENTION = NewsClassificationRequest(
    article_id=3,
    ticker="PETR4",
    company_name="Petrobras",
    title="Ibovespa closes mixed as banks outperform",
    summary=(
        "Brazilian equities were mixed. Vale and Itau led gains, while "
        "several other names including a brief mention of Petrobras were "
        "little changed on light volume."
    ),
    publisher="Valor",
)


@pytest.mark.asyncio
async def test_company_specific_production_article() -> None:
    classifier = create_news_classifier()
    signal = await classifier.classify(COMPANY_SPECIFIC)

    assert signal.company_specific is True
    assert signal.relevance is NewsRelevance.HIGH
    assert signal.confidence >= Decimal("0")
    assert signal.confidence <= Decimal("1")


@pytest.mark.asyncio
async def test_sector_hormuz_article_is_not_company_specific() -> None:
    classifier = create_news_classifier()
    signal = await classifier.classify(SECTOR_GEOPOLITICS)

    assert signal.company_specific is False
    assert signal.relevance in {
        NewsRelevance.MEDIUM,
        NewsRelevance.HIGH,
    }
    assert {"geopolitics", "oil_price", "commodity_price"} & set(signal.categories)


@pytest.mark.asyncio
async def test_weak_mention_has_low_relevance() -> None:
    classifier = create_news_classifier()
    signal = await classifier.classify(WEAK_MENTION)

    assert signal.relevance is NewsRelevance.LOW
