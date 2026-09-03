from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from br_financial_ai.api.dependencies import (
    get_analysis_context_service,
    get_company_analysis_service,
    get_yahoo_market_client,
)
from br_financial_ai.domain.analysis import (
    AnnualFinancials,
    EvidenceReference,
    NewsContextItem,
    RecommendationContext,
)
from br_financial_ai.domain.market import (
    MarketPeriodMetrics,
    MarketQuote,
    PriceBar,
    PriceChange,
)
from br_financial_ai.domain.recommendation import (
    ANALYSIS_DISCLAIMER,
    RecommendationResult,
    RecommendationStance,
)
from br_financial_ai.domain.valuation import ValuationMetrics
from br_financial_ai.main import app
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
    RecommendationGenerationError,
)

AS_OF = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)

EVIDENCE = EvidenceReference(
    source="CVM",
    kind="financial_statement",
    reference="DFP 2025",
)


def _result(
    stance: RecommendationStance = RecommendationStance.FAVORABLE,
) -> RecommendationResult:
    return RecommendationResult(
        ticker="PETR4",
        stance=stance,
        confidence=Decimal("0.78"),
        summary="Evidence is predominantly constructive.",
        positives=("Positive margins.",),
        risks=("Commodity prices can reverse.",),
        fundamentals_view="Annual profitability is constructive.",
        valuation_view="P/S and P/E are usable.",
        market_view="The 1mo return is positive.",
        news_view="Recent news is constructive.",
        limitations=("P/B not supported", "EV/EBITDA not supported"),
        evidence=(EVIDENCE,),
        as_of=AS_OF,
    )


def _context() -> RecommendationContext:
    return RecommendationContext(
        ticker="PETR4",
        company_name="PETROBRAS",
        financial_profile="NON_FINANCIAL",
        as_of=AS_OF,
        financials=AnnualFinancials(
            ticker="PETR4",
            year=2025,
            document_type="DFP",
            revenue=Decimal("100000"),
            gross_profit=Decimal("40000"),
            operating_result=Decimal("20000"),
            net_income=Decimal("10000"),
            currency="BRL",
        ),
        valuation=ValuationMetrics(
            ticker="PETR4",
            reference_year=2025,
            revenue=Decimal("100000"),
            gross_profit=Decimal("40000"),
            operating_result=Decimal("20000"),
            net_income=Decimal("10000"),
            gross_margin=Decimal("0.4"),
            operating_margin=Decimal("0.2"),
            net_margin=Decimal("0.1"),
            market_cap=Decimal("200000"),
            price_to_sales=Decimal("2"),
            price_to_earnings=Decimal("20"),
        ),
        market_quote=MarketQuote(
            ticker="PETR4",
            symbol="PETR4.SA",
            price=Decimal("46.87"),
            previous_close=Decimal("45.02"),
            currency="BRL",
            timestamp=AS_OF,
            market_cap=Decimal("200000"),
        ),
        price_change=PriceChange(
            absolute=Decimal("1.85"),
            percentage=Decimal("0.0410928476"),
        ),
        market_metrics=(
            MarketPeriodMetrics(
                period="1mo",
                period_return=Decimal("0.12"),
                volatility=Decimal("0.30"),
                max_drawdown=Decimal("-0.05"),
            ),
        ),
        recent_news=(
            NewsContextItem(
                article_id=11,
                title="Petrobras announces production guidance",
                publisher="Reuters",
                published_at=AS_OF,
                url="https://example.com/news",
                canonical_url="https://example.com/news",
                summary="The company raised its own production outlook.",
            ),
        ),
        news_signals=(),
        evidence=(EVIDENCE,),
        unavailable=(),
    )


async def _request(
    method: str,
    url: str,
    *,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.request(method, url, json=json)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stance",
    [
        RecommendationStance.FAVORABLE,
        RecommendationStance.NEUTRAL,
        RecommendationStance.UNFAVORABLE,
    ],
)
async def test_analysis_api_serializes_recommendation(
    stance: RecommendationStance,
) -> None:
    service = AsyncMock()
    service.analyze_company = AsyncMock(return_value=_result(stance))
    app.dependency_overrides[get_company_analysis_service] = lambda: service

    try:
        response = await _request(
            "POST",
            "/api/v1/analysis",
            json={"ticker": "petr4", "news_limit": 8},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "PETR4"
    assert payload["stance"] == stance.value
    assert payload["confidence"] == "0.78"
    assert payload["summary"]
    assert payload["views"]["fundamentals"]
    assert payload["views"]["valuation"]
    assert payload["views"]["market"]
    assert payload["views"]["news"]
    assert payload["positives"] == ["Positive margins."]
    assert payload["risks"] == ["Commodity prices can reverse."]
    assert payload["limitations"] == [
        "P/B not supported",
        "EV/EBITDA not supported",
    ]
    assert payload["evidence"] == [
        {
            "source": "CVM",
            "kind": "financial_statement",
            "reference": "DFP 2025",
        }
    ]
    assert payload["disclaimer"] == ANALYSIS_DISCLAIMER
    assert "as_of" in payload
    service.analyze_company.assert_awaited_once_with(
        "petr4",
        news_limit=8,
    )


@pytest.mark.asyncio
async def test_analysis_api_unknown_ticker() -> None:
    service = AsyncMock()
    service.analyze_company = AsyncMock(
        side_effect=CompanyNotFoundError("ZZZZ4"),
    )
    app.dependency_overrides[get_company_analysis_service] = lambda: service

    try:
        response = await _request(
            "POST",
            "/api/v1/analysis",
            json={"ticker": "ZZZZ4"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found."


@pytest.mark.asyncio
async def test_analysis_api_recommendation_failure() -> None:
    service = AsyncMock()
    service.analyze_company = AsyncMock(
        side_effect=RecommendationGenerationError("ollama down"),
    )
    app.dependency_overrides[get_company_analysis_service] = lambda: service

    try:
        response = await _request(
            "POST",
            "/api/v1/analysis",
            json={"ticker": "PETR4"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Recommendation model is unavailable."


@pytest.mark.asyncio
async def test_analysis_api_validation_error() -> None:
    response = await _request(
        "POST",
        "/api/v1/analysis",
        json={"ticker": "PETR4", "news_limit": 99},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analysis_context_api() -> None:
    service = AsyncMock()
    service.build_recommendation_context = AsyncMock(return_value=_context())
    app.dependency_overrides[get_analysis_context_service] = lambda: service

    try:
        response = await _request("GET", "/api/v1/analysis/context/PETR4")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "PETR4"
    assert payload["company_name"] == "PETROBRAS"
    assert payload["financial_profile"] == "NON_FINANCIAL"
    assert payload["financials"]["document_type"] == "DFP"
    assert payload["valuation"]["price_to_earnings"] == "20"
    assert payload["market_quote"]["symbol"] == "PETR4.SA"
    assert payload["disclaimer"] == ANALYSIS_DISCLAIMER
    assert payload["recent_news"][0]["summary"] == (
        "The company raised its own production outlook."
    )
    service.build_recommendation_context.assert_awaited_once_with(
        "PETR4",
        news_limit=10,
    )


@pytest.mark.asyncio
async def test_market_history_api() -> None:
    client = AsyncMock()
    client.get_price_history = AsyncMock(
        return_value=[
            PriceBar(
                ticker="PETR4",
                timestamp=AS_OF,
                open=Decimal("45.00"),
                high=Decimal("47.00"),
                low=Decimal("44.50"),
                close=Decimal("46.87"),
                volume=1000,
            )
        ]
    )
    app.dependency_overrides[get_yahoo_market_client] = lambda: client

    try:
        response = await _request(
            "GET",
            "/api/v1/analysis/market-history/PETR4?period=1y",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["ticker"] == "PETR4"
    assert payload[0]["close"] == "46.87"
    client.get_price_history.assert_awaited_once_with("PETR4", period="1y")


def test_get_analysis_context_service_does_not_create_classifier() -> None:
    from br_financial_ai.api.dependencies import get_analysis_context_service

    service = get_analysis_context_service(
        MagicMock(),
        MagicMock(),
    )

    assert not hasattr(service, "news_classifier")
    assert service.market_client is not None
