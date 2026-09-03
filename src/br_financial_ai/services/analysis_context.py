from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.clients.yahoo_market import (
    YahooMarketClient,
    YahooMarketProviderError,
)
from br_financial_ai.db.models import NewsArticle
from br_financial_ai.domain.analysis import (
    CONTEXT_MARKET_PERIODS,
    AnnualFinancials,
    EvidenceReference,
    NewsContextItem,
    RecommendationContext,
    UnavailableSection,
)
from br_financial_ai.domain.financial_metrics import (
    list_unsupported_context_metrics,
)
from br_financial_ai.domain.financial_profile import (
    METRIC_UNSUPPORTED_FOR_PROFILE,
    financial_profile_from_setor_ativ,
)
from br_financial_ai.domain.market import (
    MarketPeriodMetrics,
    compute_period_metrics,
    quote_price_change,
)
from br_financial_ai.domain.news import NEWS_PROVIDER_YAHOO
from br_financial_ai.domain.news_signals import NewsSignal
from br_financial_ai.domain.valuation import (
    ValuationMetrics,
    is_brl_currency,
)
from br_financial_ai.repositories.news_article_signal import (
    NewsArticleSignalRepository,
)
from br_financial_ai.services.company_query import (
    CompanyQueryService,
)
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
)
from br_financial_ai.services.news_classification import (
    classifier_identity_from_settings,
    news_signal_from_record,
)
from br_financial_ai.services.news_query import NewsQueryService
from br_financial_ai.services.valuation import ValuationService

NEWS_SOURCE = {
    NEWS_PROVIDER_YAHOO: "Yahoo Finance",
}


class AnalysisContextService:
    def __init__(
        self,
        session: AsyncSession,
        market_client: YahooMarketClient,
    ) -> None:
        self.company_query_service = CompanyQueryService(session)
        self.valuation_service = ValuationService(session)
        self.news_query_service = NewsQueryService(session)
        self.news_signals = NewsArticleSignalRepository(session)
        self.market_client = market_client

    async def build_recommendation_context(
        self,
        ticker: str,
        *,
        news_limit: int = 10,
        reference_year: int | None = None,
        as_of: datetime | None = None,
    ) -> RecommendationContext:
        if news_limit < 0:
            raise ValueError("News limit must be at least 0.")

        company = await self.company_query_service.find_by_ticker(ticker)

        if company is None:
            raise CompanyNotFoundError(ticker.strip().upper())

        quote = await self.market_client.get_quote(ticker)
        snapshot_at = as_of or quote.timestamp
        year = (
            reference_year
            if reference_year is not None
            else (snapshot_at.astimezone(UTC).year - 1)
        )
        normalized_ticker = ticker.strip().upper()
        profile = financial_profile_from_setor_ativ(company.setor_ativ)
        evidence: list[EvidenceReference] = []
        unavailable: list[UnavailableSection] = []

        valuation = await self.valuation_service.get_metrics(
            normalized_ticker,
            year,
            quote=quote,
        )
        financials = _annual_financials(valuation)
        evidence.append(
            EvidenceReference(
                source="CVM",
                kind="financial_statement",
                reference=f"DFP {year}",
            )
        )
        evidence.append(
            EvidenceReference(
                source="Yahoo Finance",
                kind="market_quote",
                reference=quote.symbol,
            )
        )

        if quote.market_cap is not None and not is_brl_currency(
            quote.currency,
        ):
            unavailable.append(
                UnavailableSection(
                    section="market_valuation",
                    source="Yahoo Finance",
                    reason="currency_mismatch",
                    reference=quote.currency,
                )
            )

        for metric_key in list_unsupported_context_metrics(profile):
            unavailable.append(
                UnavailableSection(
                    section="metric",
                    source="financial_profile",
                    reason=METRIC_UNSUPPORTED_FOR_PROFILE,
                    reference=metric_key,
                )
            )

        market_metrics, history_unavailable = await self._market_metrics(
            normalized_ticker,
            quote.symbol,
        )
        unavailable.extend(history_unavailable)

        for metrics in market_metrics:
            evidence.append(
                EvidenceReference(
                    source="Yahoo Finance",
                    kind="market_history",
                    reference=f"{quote.symbol} {metrics.period}",
                )
            )

        recent_news, news_signals, news_evidence = await self._news_context(
            ticker=normalized_ticker,
            news_limit=news_limit,
        )
        evidence.extend(news_evidence)

        return RecommendationContext(
            ticker=normalized_ticker,
            company_name=company.trade_name,
            financial_profile=profile.value,
            as_of=snapshot_at,
            financials=financials,
            valuation=valuation,
            market_quote=quote,
            price_change=quote_price_change(quote),
            market_metrics=tuple(market_metrics),
            recent_news=tuple(recent_news),
            news_signals=tuple(news_signals),
            evidence=tuple(evidence),
            unavailable=tuple(unavailable),
        )

    async def _market_metrics(
        self,
        ticker: str,
        symbol: str,
    ) -> tuple[list[MarketPeriodMetrics], list[UnavailableSection]]:
        metrics: list[MarketPeriodMetrics] = []
        unavailable: list[UnavailableSection] = []

        for period in CONTEXT_MARKET_PERIODS:
            try:
                bars = await self.market_client.get_price_history(
                    ticker,
                    period=period,
                )
            except YahooMarketProviderError:
                unavailable.append(
                    UnavailableSection(
                        section="market_history",
                        source="Yahoo Finance",
                        reason="provider_error",
                        reference=f"{symbol} {period}",
                    )
                )
                continue

            if len(bars) < 3:
                unavailable.append(
                    UnavailableSection(
                        section="market_history",
                        source="Yahoo Finance",
                        reason="insufficient_price_history",
                        reference=f"{symbol} {period}",
                    )
                )
                continue

            try:
                metrics.append(
                    compute_period_metrics(bars, period=period),
                )
            except ValueError:
                unavailable.append(
                    UnavailableSection(
                        section="market_history",
                        source="Yahoo Finance",
                        reason="insufficient_price_history",
                        reference=f"{symbol} {period}",
                    )
                )

        return metrics, unavailable

    async def _news_context(
        self,
        *,
        ticker: str,
        news_limit: int,
    ) -> tuple[
        list[NewsContextItem],
        list[NewsSignal],
        list[EvidenceReference],
    ]:
        if news_limit == 0:
            return [], [], []

        articles = await self.news_query_service.get_recent_company_news(
            ticker,
            limit=news_limit,
        )
        recent_news = [_news_item(article) for article in articles]
        evidence = [
            EvidenceReference(
                source=NEWS_SOURCE.get(article.provider, article.provider),
                kind="news",
                reference=article.canonical_url,
            )
            for article in articles
        ]
        article_ids = [article.id for article in articles if article.id is not None]
        cached_rows = await self.news_signals.list_by_article_ids_and_identity(
            article_ids,
            classifier_identity_from_settings(),
        )
        news_signals = [
            news_signal_from_record(cached_rows[article.id])
            for article in articles
            if article.id is not None and article.id in cached_rows
        ]
        return recent_news, news_signals, evidence


def _annual_financials(valuation: ValuationMetrics) -> AnnualFinancials:
    return AnnualFinancials(
        ticker=valuation.ticker,
        year=valuation.reference_year,
        document_type="DFP",
        revenue=valuation.revenue,
        gross_profit=valuation.gross_profit,
        operating_result=valuation.operating_result,
        net_income=valuation.net_income,
        currency="BRL",
    )


def _news_item(article: NewsArticle) -> NewsContextItem:
    return NewsContextItem(
        article_id=article.id,
        title=article.title,
        publisher=article.publisher,
        published_at=article.published_at,
        url=article.url,
        canonical_url=article.canonical_url,
        summary=article.summary,
    )
