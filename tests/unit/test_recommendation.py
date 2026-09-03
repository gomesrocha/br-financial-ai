from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest

from br_financial_ai.ai.recommendation import (
    RecommendationEngine,
    RecommendationModelOutput,
    create_recommendation_engine,
    parse_recommendation_output,
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
from br_financial_ai.domain.recommendation import (
    ANALYSIS_DISCLAIMER,
    RecommendationStance,
    limitations_from_context,
)
from br_financial_ai.domain.valuation import ValuationMetrics
from br_financial_ai.services.company_analysis import (
    CompanyAnalysisService,
)
from br_financial_ai.services.exceptions import (
    RecommendationGenerationError,
)

AS_OF = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)

CVM_EVIDENCE = EvidenceReference(
    source="CVM",
    kind="financial_statement",
    reference="DFP 2025",
)
QUOTE_EVIDENCE = EvidenceReference(
    source="Yahoo Finance",
    kind="market_quote",
    reference="PETR4.SA",
)
NEWS_EVIDENCE = EvidenceReference(
    source="Yahoo Finance",
    kind="news",
    reference="https://example.com/petrobras-guidance",
)


def _financials() -> AnnualFinancials:
    return AnnualFinancials(
        ticker="PETR4",
        year=2025,
        document_type="DFP",
        revenue=Decimal("100000"),
        gross_profit=Decimal("40000"),
        operating_result=Decimal("20000"),
        net_income=Decimal("10000"),
        currency="BRL",
    )


def _valuation(
    *,
    net_income: Decimal | None = Decimal("10000"),
    price_to_earnings: Decimal | None = Decimal("20"),
    price_to_sales: Decimal | None = Decimal("2"),
    market_cap: Decimal | None = Decimal("200000"),
) -> ValuationMetrics:
    revenue = Decimal("100000")
    return ValuationMetrics(
        ticker="PETR4",
        reference_year=2025,
        revenue=revenue,
        gross_profit=Decimal("40000"),
        operating_result=Decimal("20000"),
        net_income=net_income,
        gross_margin=Decimal("0.4"),
        operating_margin=Decimal("0.2"),
        net_margin=(
            None if net_income is None or revenue == 0 else net_income / revenue
        ),
        market_cap=market_cap,
        price_to_sales=price_to_sales,
        price_to_earnings=price_to_earnings,
    )


def make_context(
    *,
    ticker: str = "PETR4",
    recent_news: tuple[NewsContextItem, ...] | None = None,
    news_signals: tuple[NewsSignal, ...] | None = None,
    unavailable: tuple[UnavailableSection, ...] = (),
    valuation: ValuationMetrics | None = None,
    evidence: tuple[EvidenceReference, ...] | None = None,
) -> RecommendationContext:
    news_item = NewsContextItem(
        article_id=1,
        title="Petrobras anuncia guidance de producao",
        publisher="Reuters",
        published_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        url="https://example.com/petrobras-guidance",
        canonical_url="https://example.com/petrobras-guidance",
    )
    signal = NewsSignal(
        article_id=1,
        relevance=NewsRelevance.HIGH,
        materiality=NewsMateriality.MEDIUM,
        sentiment=NewsSentiment.POSITIVE,
        company_specific=True,
        categories=("production",),
        confidence=Decimal("0.8"),
        rationale="Company production guidance.",
    )

    if recent_news is None:
        recent_news = (news_item,)

    if news_signals is None:
        news_signals = (signal,) if recent_news else ()

    if evidence is None:
        evidence = (CVM_EVIDENCE, QUOTE_EVIDENCE, NEWS_EVIDENCE)

    return RecommendationContext(
        ticker=ticker,
        company_name="PETROBRAS",
        financial_profile="NON_FINANCIAL",
        as_of=AS_OF,
        financials=_financials(),
        valuation=valuation or _valuation(),
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
        recent_news=recent_news,
        news_signals=news_signals,
        evidence=evidence,
        unavailable=unavailable,
    )


def valid_payload(
    *,
    ticker: str = "PETR4",
    stance: str = "FAVORABLE",
    confidence: object = 0.78,
    summary: str = "Evidence is predominantly constructive.",
    evidence: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "stance": stance,
        "confidence": confidence,
        "summary": summary,
        "positives": ["Positive margins and recovering prices."],
        "risks": ["Commodity prices can reverse."],
        "fundamentals_view": "Annual profitability is constructive.",
        "valuation_view": "P/S and P/E are usable and not stretched in this snapshot.",
        "market_view": "The 1mo return is positive with a modest drawdown.",
        "news_view": (
            "Recent company-specific news is production-related and constructive."
        ),
        "evidence": evidence
        or [
            {
                "source": "CVM",
                "kind": "financial_statement",
                "reference": "DFP 2025",
            }
        ],
    }


def test_favorable_recommendation() -> None:
    result = parse_recommendation_output(
        make_context(),
        valid_payload(stance="FAVORABLE"),
    )

    assert result.stance is RecommendationStance.FAVORABLE
    assert result.ticker == "PETR4"
    assert result.disclaimer == ANALYSIS_DISCLAIMER
    assert result.evidence == (CVM_EVIDENCE, QUOTE_EVIDENCE, NEWS_EVIDENCE)
    assert result.as_of == AS_OF


def test_neutral_recommendation() -> None:
    result = parse_recommendation_output(
        make_context(),
        valid_payload(stance="NEUTRAL", confidence=0.5),
    )

    assert result.stance is RecommendationStance.NEUTRAL


def test_unfavorable_recommendation() -> None:
    result = parse_recommendation_output(
        make_context(),
        valid_payload(stance="UNFAVORABLE", confidence=0.62),
    )

    assert result.stance is RecommendationStance.UNFAVORABLE


def test_confidence_converts_to_decimal() -> None:
    result = parse_recommendation_output(
        make_context(),
        valid_payload(confidence=0.78),
    )

    assert result.confidence == Decimal("0.78")
    assert isinstance(result.confidence, Decimal)


def test_invalid_confidence() -> None:
    with pytest.raises(
        RecommendationGenerationError,
        match="Malformed recommendation result",
    ):
        parse_recommendation_output(
            make_context(),
            valid_payload(confidence=1.5),
        )


def test_invalid_stance() -> None:
    with pytest.raises(
        RecommendationGenerationError,
        match="Malformed recommendation result",
    ):
        parse_recommendation_output(
            make_context(),
            valid_payload(stance="BUY"),
        )


def test_ticker_mismatch() -> None:
    with pytest.raises(
        RecommendationGenerationError,
        match="does not match the context",
    ):
        parse_recommendation_output(
            make_context(),
            valid_payload(ticker="VALE3"),
        )


def test_hallucinated_evidence_is_rejected() -> None:
    with pytest.raises(
        RecommendationGenerationError,
        match="not in the context",
    ):
        parse_recommendation_output(
            make_context(),
            valid_payload(
                evidence=[
                    {
                        "source": "Imaginary Wire",
                        "kind": "news",
                        "reference": "https://fake.example/story",
                    }
                ]
            ),
        )


def test_missing_required_section() -> None:
    with pytest.raises(
        RecommendationGenerationError,
        match="Recommendation summary is empty",
    ):
        parse_recommendation_output(
            make_context(),
            valid_payload(summary="   "),
        )


def test_unavailable_context_is_represented_in_limitations() -> None:
    context = make_context(
        recent_news=(),
        news_signals=(),
        valuation=_valuation(
            net_income=Decimal("-10000"),
            price_to_earnings=None,
        ),
        unavailable=(
            UnavailableSection(
                section="market_history",
                source="Yahoo Finance",
                reason="provider_error",
                reference="PETR4.SA 1y",
            ),
            UnavailableSection(
                section="news_classification",
                source="LLM",
                reason="classification_failed",
                reference="1",
            ),
        ),
        evidence=(CVM_EVIDENCE, QUOTE_EVIDENCE),
    )

    limitations = limitations_from_context(context)

    assert "P/E unavailable because annual net income is non-positive" in limitations
    assert "1y market history unavailable" in limitations
    assert "no recent company news" in limitations
    assert "one news classification failed" in limitations
    assert "P/B not supported" in limitations
    assert "EV/EBITDA not supported" in limitations

    result = parse_recommendation_output(
        context,
        valid_payload(stance="UNFAVORABLE", evidence=[]),
    )

    assert result.limitations == limitations
    assert result.evidence == context.evidence


def test_unsupported_profile_metrics_are_not_treated_as_missing_or_zero() -> None:
    context = make_context(
        valuation=_valuation(
            net_income=Decimal("45849000000"),
            price_to_earnings=Decimal("8"),
            price_to_sales=None,
        ),
        unavailable=(
            UnavailableSection(
                section="metric",
                source="financial_profile",
                reason="METRIC_UNSUPPORTED_FOR_PROFILE",
                reference="gross_profit",
            ),
            UnavailableSection(
                section="metric",
                source="financial_profile",
                reason="METRIC_UNSUPPORTED_FOR_PROFILE",
                reference="price_to_sales",
            ),
        ),
    )

    limitations = limitations_from_context(context)

    assert "gross profit unsupported for this financial profile" in limitations
    assert "P/S unsupported for this financial profile" in limitations
    assert "P/S unavailable" not in limitations
    assert "gross profit unavailable" not in limitations
    assert context.valuation.gross_margin != 0


@pytest.mark.asyncio
async def test_engine_uses_structured_model() -> None:
    structured_model = AsyncMock()
    structured_model.ainvoke = AsyncMock(
        return_value=RecommendationModelOutput.model_validate(
            valid_payload(),
        )
    )
    engine = RecommendationEngine(structured_model)
    result = await engine.generate_recommendation(make_context())

    assert result.stance is RecommendationStance.FAVORABLE
    structured_model.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_engine_retries_when_numeric_claim_is_ungrounded() -> None:
    bad = valid_payload(summary="Net income is BRL 8 billion.")
    bad["fundamentals_view"] = (
        "Net income is BRL 8 billion against 80000000000 in the JSON."
    )
    good = valid_payload(summary="Net income is 80000000000.")
    good["fundamentals_view"] = "Net income is 80000000000."
    structured_model = AsyncMock()
    structured_model.ainvoke = AsyncMock(
        side_effect=[
            RecommendationModelOutput.model_validate(bad),
            RecommendationModelOutput.model_validate(good),
        ]
    )
    context = replace(
        make_context(),
        financials=AnnualFinancials(
            ticker="PETR4",
            year=2025,
            document_type="DFP",
            revenue=Decimal("490829000000"),
            gross_profit=Decimal("196000000000"),
            operating_result=Decimal("120000000000"),
            net_income=Decimal("80000000000"),
            currency="BRL",
        ),
    )
    engine = RecommendationEngine(structured_model)
    result = await engine.generate_recommendation(context)

    assert result.summary == "Net income is 80000000000."
    assert structured_model.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_engine_retries_when_evidence_is_not_in_context() -> None:
    bad = valid_payload(
        evidence=[
            {
                "source": "Imaginary Wire",
                "kind": "news",
                "reference": "https://fake.example/story",
            }
        ]
    )
    structured_model = AsyncMock()
    structured_model.ainvoke = AsyncMock(
        side_effect=[
            RecommendationModelOutput.model_validate(bad),
            RecommendationModelOutput.model_validate(valid_payload()),
        ]
    )
    engine = RecommendationEngine(structured_model)
    result = await engine.generate_recommendation(make_context())

    assert result.stance is RecommendationStance.FAVORABLE
    assert result.evidence == (CVM_EVIDENCE, QUOTE_EVIDENCE, NEWS_EVIDENCE)
    assert structured_model.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_engine_wraps_model_failure() -> None:
    structured_model = AsyncMock()
    structured_model.ainvoke = AsyncMock(side_effect=RuntimeError("ollama down"))
    engine = RecommendationEngine(structured_model)

    with pytest.raises(
        RecommendationGenerationError,
        match="Failed to generate recommendation",
    ):
        await engine.generate_recommendation(make_context())


def test_create_recommendation_engine_uses_chat_model() -> None:
    structured = Mock(name="structured")
    model = Mock()
    model.with_structured_output = Mock(return_value=structured)

    engine = create_recommendation_engine(model)

    model.with_structured_output.assert_called_once_with(
        RecommendationModelOutput,
        include_raw=True,
    )
    assert engine._structured_model is structured


@pytest.mark.asyncio
async def test_analyze_company_uses_existing_context_builder() -> None:
    context = make_context()
    expected = parse_recommendation_output(context, valid_payload())
    analysis_context_service = AsyncMock()
    analysis_context_service.build_recommendation_context = AsyncMock(
        return_value=context,
    )
    recommendation_engine = AsyncMock()
    recommendation_engine.generate_recommendation = AsyncMock(
        return_value=expected,
    )
    news_classification_service = AsyncMock()
    news_classification_service.enrich_context = AsyncMock(
        return_value=context,
    )
    service = CompanyAnalysisService(
        analysis_context_service,
        recommendation_engine,
        news_classification_service,
    )

    result = await service.analyze_company("PETR4", news_limit=7)

    assert result is expected
    analysis_context_service.build_recommendation_context.assert_awaited_once_with(
        "PETR4",
        news_limit=7,
        reference_year=None,
    )
    news_classification_service.enrich_context.assert_awaited_once_with(context)
    recommendation_engine.generate_recommendation.assert_awaited_once_with(
        context,
    )
