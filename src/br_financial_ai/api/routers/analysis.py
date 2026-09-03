from fastapi import APIRouter, HTTPException, Query, status

from br_financial_ai.api.dependencies import (
    AnalysisContextServiceDep,
    CompanyAnalysisServiceDep,
    YahooMarketClientDep,
)
from br_financial_ai.clients.yahoo_market import (
    MarketDataNotFoundError,
    YahooMarketProviderError,
)
from br_financial_ai.domain.analysis import (
    EvidenceReference,
    RecommendationContext,
)
from br_financial_ai.domain.recommendation import RecommendationResult
from br_financial_ai.schemas.analysis import (
    AnalysisRequest,
    AnnualFinancialsRead,
    EvidenceRead,
    MarketPeriodMetricsRead,
    MarketQuoteRead,
    NewsItemRead,
    NewsSignalRead,
    PriceBarRead,
    PriceChangeRead,
    RecommendationContextRead,
    RecommendationRead,
    RecommendationViewsRead,
    UnavailableSectionRead,
    ValuationMetricsRead,
)
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
    RecommendationGenerationError,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["analysis"],
)


@router.post(
    "/analysis",
    response_model=RecommendationRead,
)
async def create_analysis(
    request: AnalysisRequest,
    service: CompanyAnalysisServiceDep,
) -> RecommendationRead:
    try:
        result = await service.analyze_company(
            request.ticker,
            news_limit=request.news_limit,
        )
    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        ) from exc
    except (YahooMarketProviderError, MarketDataNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market data provider is unavailable.",
        ) from exc
    except RecommendationGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recommendation model is unavailable.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return recommendation_to_read(result)


@router.get(
    "/analysis/context/{ticker}",
    response_model=RecommendationContextRead,
)
async def get_analysis_context(
    ticker: str,
    service: AnalysisContextServiceDep,
    news_limit: int = Query(default=10, ge=0, le=20),
) -> RecommendationContextRead:
    try:
        context = await service.build_recommendation_context(
            ticker,
            news_limit=news_limit,
        )
    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        ) from exc
    except (YahooMarketProviderError, MarketDataNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market data provider is unavailable.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return context_to_read(context)


@router.get(
    "/analysis/market-history/{ticker}",
    response_model=list[PriceBarRead],
)
async def get_market_history(
    ticker: str,
    market_client: YahooMarketClientDep,
    period: str = Query(default="1y"),
) -> list[PriceBarRead]:
    try:
        bars = await market_client.get_price_history(ticker, period=period)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (YahooMarketProviderError, MarketDataNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market data provider is unavailable.",
        ) from exc

    return [
        PriceBarRead(
            ticker=item.ticker,
            timestamp=item.timestamp,
            open=item.open,
            high=item.high,
            low=item.low,
            close=item.close,
            volume=item.volume,
        )
        for item in bars
    ]


def recommendation_to_read(
    result: RecommendationResult,
) -> RecommendationRead:
    return RecommendationRead(
        ticker=result.ticker,
        stance=result.stance,
        confidence=result.confidence,
        summary=result.summary,
        views=RecommendationViewsRead(
            fundamentals=result.fundamentals_view,
            valuation=result.valuation_view,
            market=result.market_view,
            news=result.news_view,
        ),
        positives=list(result.positives),
        risks=list(result.risks),
        limitations=list(result.limitations),
        evidence=[_evidence_to_read(item) for item in result.evidence],
        as_of=result.as_of,
        disclaimer=result.disclaimer,
    )


def context_to_read(
    context: RecommendationContext,
) -> RecommendationContextRead:
    financials = context.financials
    valuation = context.valuation
    quote = context.market_quote

    return RecommendationContextRead(
        ticker=context.ticker,
        company_name=context.company_name,
        financial_profile=context.financial_profile,
        as_of=context.as_of,
        financials=AnnualFinancialsRead(
            ticker=financials.ticker,
            year=financials.year,
            document_type=financials.document_type,
            revenue=financials.revenue,
            gross_profit=financials.gross_profit,
            operating_result=financials.operating_result,
            net_income=financials.net_income,
            currency=financials.currency,
        ),
        valuation=ValuationMetricsRead(
            ticker=valuation.ticker,
            reference_year=valuation.reference_year,
            revenue=valuation.revenue,
            gross_profit=valuation.gross_profit,
            operating_result=valuation.operating_result,
            net_income=valuation.net_income,
            gross_margin=valuation.gross_margin,
            operating_margin=valuation.operating_margin,
            net_margin=valuation.net_margin,
            market_cap=valuation.market_cap,
            price_to_sales=valuation.price_to_sales,
            price_to_earnings=valuation.price_to_earnings,
        ),
        market_quote=MarketQuoteRead(
            ticker=quote.ticker,
            symbol=quote.symbol,
            price=quote.price,
            previous_close=quote.previous_close,
            currency=quote.currency,
            timestamp=quote.timestamp,
            market_cap=quote.market_cap,
        ),
        price_change=PriceChangeRead(
            absolute=context.price_change.absolute,
            percentage=context.price_change.percentage,
        ),
        market_metrics=[
            MarketPeriodMetricsRead(
                period=item.period,
                period_return=item.period_return,
                volatility=item.volatility,
                max_drawdown=item.max_drawdown,
            )
            for item in context.market_metrics
        ],
        recent_news=[
            NewsItemRead(
                article_id=item.article_id,
                title=item.title,
                publisher=item.publisher,
                published_at=item.published_at,
                url=item.url,
                canonical_url=item.canonical_url,
                summary=item.summary,
            )
            for item in context.recent_news
        ],
        news_signals=[
            NewsSignalRead(
                article_id=item.article_id,
                relevance=item.relevance.value,
                materiality=item.materiality.value,
                sentiment=item.sentiment.value,
                company_specific=item.company_specific,
                categories=list(item.categories),
                confidence=item.confidence,
                rationale=item.rationale,
            )
            for item in context.news_signals
        ],
        evidence=[_evidence_to_read(item) for item in context.evidence],
        unavailable=[
            UnavailableSectionRead(
                section=item.section,
                source=item.source,
                reason=item.reason,
                reference=item.reference,
            )
            for item in context.unavailable
        ],
    )


def _evidence_to_read(item: EvidenceReference) -> EvidenceRead:
    return EvidenceRead(
        source=item.source,
        kind=item.kind,
        reference=item.reference,
    )
