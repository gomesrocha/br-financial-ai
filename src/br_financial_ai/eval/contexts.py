from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

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
from br_financial_ai.domain.valuation import ValuationMetrics

AS_OF = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)


def context_from_case(case: dict[str, Any]) -> RecommendationContext:
    payload = case["context"]
    ticker = str(payload.get("ticker") or "PETR4")
    revenue = _decimal(payload.get("revenue"))
    gross = _decimal(payload.get("gross"))
    operating = _decimal(payload.get("operating"))
    net_income = _decimal(payload.get("net_income"))
    news_title = payload.get("news_title")
    no_news = bool(payload.get("no_news")) or not news_title
    unavailable: list[UnavailableSection] = []

    if payload.get("unavailable_1y"):
        unavailable.append(
            UnavailableSection(
                section="market_history",
                source="Yahoo Finance",
                reason="insufficient_price_history",
                reference=f"{ticker}.SA 1y",
            )
        )

    news_item = None
    signal = None
    news_evidence = None

    if not no_news:
        news_item = NewsContextItem(
            article_id=1,
            title=str(news_title),
            publisher="Reuters",
            published_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
            url="https://example.com/news",
            canonical_url="https://example.com/news",
            summary=str(news_title),
        )
        signal = NewsSignal(
            article_id=1,
            relevance=NewsRelevance.HIGH,
            materiality=NewsMateriality.HIGH,
            sentiment=NewsSentiment(str(payload.get("news_sentiment") or "NEUTRAL")),
            company_specific=True,
            categories=("production",),
            confidence=Decimal("0.8"),
            rationale=str(news_title),
        )
        news_evidence = EvidenceReference(
            source="Yahoo Finance",
            kind="news",
            reference="https://example.com/news",
        )

    evidence = [
        EvidenceReference(
            source="CVM",
            kind="financial_statement",
            reference="DFP 2025",
        ),
        EvidenceReference(
            source="Yahoo Finance",
            kind="market_quote",
            reference=f"{ticker}.SA",
        ),
    ]
    if news_evidence is not None:
        evidence.append(news_evidence)

    return RecommendationContext(
        ticker=ticker,
        company_name=str(payload.get("company_name") or "PETROBRAS"),
        financial_profile="NON_FINANCIAL",
        as_of=AS_OF,
        financials=AnnualFinancials(
            ticker=ticker,
            year=2025,
            document_type="DFP",
            revenue=revenue,
            gross_profit=gross,
            operating_result=operating,
            net_income=net_income,
            currency="BRL",
        ),
        valuation=ValuationMetrics(
            ticker=ticker,
            reference_year=2025,
            revenue=revenue,
            gross_profit=gross,
            operating_result=operating,
            net_income=net_income,
            gross_margin=_margin(gross, revenue),
            operating_margin=_margin(operating, revenue),
            net_margin=_margin(net_income, revenue),
            market_cap=_decimal(payload.get("market_cap")),
            price_to_sales=_decimal(payload.get("price_to_sales")),
            price_to_earnings=_decimal(payload.get("price_to_earnings")),
        ),
        market_quote=MarketQuote(
            ticker=ticker,
            symbol=f"{ticker}.SA",
            price=Decimal("46.87"),
            previous_close=Decimal("45.02"),
            currency="BRL",
            timestamp=AS_OF,
            market_cap=_decimal(payload.get("market_cap")),
        ),
        price_change=PriceChange(
            absolute=Decimal("1.85"),
            percentage=Decimal("0.0410928476"),
        ),
        market_metrics=(
            MarketPeriodMetrics(
                period="1mo",
                period_return=_decimal(payload.get("period_return")) or Decimal("0"),
                volatility=Decimal("0.25"),
                max_drawdown=_decimal(payload.get("drawdown")) or Decimal("0"),
            ),
        ),
        recent_news=() if news_item is None else (news_item,),
        news_signals=() if signal is None else (signal,),
        evidence=tuple(evidence),
        unavailable=tuple(unavailable),
    )


def expected_stances(case: dict[str, Any]) -> set[str]:
    expected = case["expected_stance"]
    if isinstance(expected, list):
        return {str(item) for item in expected}
    return {str(expected)}


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _margin(numerator: Decimal | None, revenue: Decimal | None) -> Decimal | None:
    if numerator is None or revenue is None or revenue == 0:
        return None
    return numerator / revenue
