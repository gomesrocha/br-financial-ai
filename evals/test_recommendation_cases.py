from datetime import UTC, datetime
from decimal import Decimal

import pytest

from br_financial_ai.ai.recommendation import (
    create_recommendation_engine,
)
from br_financial_ai.domain.analysis import (
    AnnualFinancials,
    EvidenceReference,
    NewsContextItem,
    RecommendationContext,
    UnavailableSection,
)
from br_financial_ai.domain.market import (
    MarketPeriodMetrics,
    MarketQuote,
    PriceChange,
)
from br_financial_ai.domain.news_signals import (
    NewsMateriality,
    NewsRelevance,
    NewsSentiment,
    NewsSignal,
)
from br_financial_ai.domain.recommendation import RecommendationStance
from br_financial_ai.domain.valuation import ValuationMetrics

pytestmark = [
    pytest.mark.eval,
    pytest.mark.external,
    pytest.mark.ollama,
    pytest.mark.slow,
]

AS_OF = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)


def _quote(price: str, previous: str) -> MarketQuote:
    return MarketQuote(
        ticker="PETR4",
        symbol="PETR4.SA",
        price=Decimal(price),
        previous_close=Decimal(previous),
        currency="BRL",
        timestamp=AS_OF,
        market_cap=Decimal("400000000000"),
    )


def _metrics(period: str, period_return: str, drawdown: str) -> MarketPeriodMetrics:
    return MarketPeriodMetrics(
        period=period,
        period_return=Decimal(period_return),
        volatility=Decimal("0.25"),
        max_drawdown=Decimal(drawdown),
    )


def _signal(
    *,
    sentiment: NewsSentiment,
    relevance: NewsRelevance = NewsRelevance.HIGH,
    title: str,
) -> tuple[NewsContextItem, NewsSignal]:
    item = NewsContextItem(
        article_id=1,
        title=title,
        publisher="Reuters",
        published_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        url="https://example.com/news",
        canonical_url="https://example.com/news",
    )
    signal = NewsSignal(
        article_id=1,
        relevance=relevance,
        materiality=NewsMateriality.HIGH,
        sentiment=sentiment,
        company_specific=True,
        categories=("production",),
        confidence=Decimal("0.8"),
        rationale=title,
    )
    return item, signal


def _context(
    *,
    revenue: str,
    gross: str,
    operating: str,
    net_income: str,
    market_cap: str,
    price_to_sales: str | None,
    price_to_earnings: str | None,
    period_return: str,
    drawdown: str,
    news_title: str,
    news_sentiment: NewsSentiment,
    unavailable: tuple[UnavailableSection, ...] = (),
) -> RecommendationContext:
    net = Decimal(net_income)
    revenue_value = Decimal(revenue)
    item, signal = _signal(sentiment=news_sentiment, title=news_title)

    return RecommendationContext(
        ticker="PETR4",
        company_name="PETROBRAS",
        financial_profile="NON_FINANCIAL",
        as_of=AS_OF,
        financials=AnnualFinancials(
            ticker="PETR4",
            year=2025,
            document_type="DFP",
            revenue=revenue_value,
            gross_profit=Decimal(gross),
            operating_result=Decimal(operating),
            net_income=net,
            currency="BRL",
        ),
        valuation=ValuationMetrics(
            ticker="PETR4",
            reference_year=2025,
            revenue=revenue_value,
            gross_profit=Decimal(gross),
            operating_result=Decimal(operating),
            net_income=net,
            gross_margin=Decimal(gross) / revenue_value,
            operating_margin=Decimal(operating) / revenue_value,
            net_margin=net / revenue_value,
            market_cap=Decimal(market_cap),
            price_to_sales=(
                None if price_to_sales is None else Decimal(price_to_sales)
            ),
            price_to_earnings=(
                None if price_to_earnings is None else Decimal(price_to_earnings)
            ),
        ),
        market_quote=_quote("46.87", "45.02"),
        price_change=PriceChange(
            absolute=Decimal("1.85"),
            percentage=Decimal("0.0410928476"),
        ),
        market_metrics=(_metrics("1mo", period_return, drawdown),),
        recent_news=(item,),
        news_signals=(signal,),
        evidence=(
            EvidenceReference(
                source="CVM",
                kind="financial_statement",
                reference="DFP 2025",
            ),
            EvidenceReference(
                source="Yahoo Finance",
                kind="market_quote",
                reference="PETR4.SA",
            ),
            EvidenceReference(
                source="Yahoo Finance",
                kind="news",
                reference="https://example.com/news",
            ),
        ),
        unavailable=unavailable,
    )


FAVORABLE_CONTEXT = _context(
    revenue="490829000000",
    gross="196000000000",
    operating="120000000000",
    net_income="80000000000",
    market_cap="400000000000",
    price_to_sales="0.81",
    price_to_earnings="5.0",
    period_return="0.12",
    drawdown="-0.04",
    news_title="Petrobras raises production guidance and reports solid cash generation",
    news_sentiment=NewsSentiment.POSITIVE,
)

MIXED_CONTEXT = _context(
    revenue="490829000000",
    gross="196000000000",
    operating="120000000000",
    net_income="80000000000",
    market_cap="400000000000",
    price_to_sales="0.81",
    price_to_earnings="5.0",
    period_return="-0.03",
    drawdown="-0.08",
    news_title=(
        "Petrobras beats annual earnings estimates but faces a new regulatory probe"
    ),
    news_sentiment=NewsSentiment.MIXED,
    unavailable=(
        UnavailableSection(
            section="market_history",
            source="Yahoo Finance",
            reason="insufficient_price_history",
            reference="PETR4.SA 1y",
        ),
    ),
)

UNFAVORABLE_CONTEXT = _context(
    revenue="200000000000",
    gross="20000000000",
    operating="-15000000000",
    net_income="-25000000000",
    market_cap="400000000000",
    price_to_sales="2.0",
    price_to_earnings=None,
    period_return="-0.25",
    drawdown="-0.30",
    news_title="Petrobras cuts production guidance after severe operational setback",
    news_sentiment=NewsSentiment.NEGATIVE,
)


@pytest.mark.asyncio
async def test_favorable_synthetic_context() -> None:
    engine = create_recommendation_engine()
    result = await engine.generate_recommendation(FAVORABLE_CONTEXT)

    assert result.stance is RecommendationStance.FAVORABLE
    assert result.ticker == "PETR4"
    assert result.evidence == FAVORABLE_CONTEXT.evidence


@pytest.mark.asyncio
async def test_mixed_synthetic_context() -> None:
    engine = create_recommendation_engine()
    result = await engine.generate_recommendation(MIXED_CONTEXT)

    assert result.stance is RecommendationStance.NEUTRAL
    assert "1y market history unavailable" in result.limitations


@pytest.mark.asyncio
async def test_unfavorable_synthetic_context() -> None:
    engine = create_recommendation_engine()
    result = await engine.generate_recommendation(UNFAVORABLE_CONTEXT)

    assert result.stance is RecommendationStance.UNFAVORABLE
    assert (
        "P/E unavailable because annual net income is non-positive"
        in result.limitations
    )
