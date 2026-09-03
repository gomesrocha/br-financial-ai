from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.ai.news_classifier import (
    NewsClassificationOutput,
    NewsClassifier,
)
from br_financial_ai.db.models import (
    Company,
    FinancialFiling,
    FinancialStatementItem,
    NewsArticle,
    Security,
)
from br_financial_ai.domain.news import NEWS_PROVIDER_YAHOO, news_content_hash
from br_financial_ai.domain.news_signals import NewsClassifierIdentity
from br_financial_ai.domain.recommendation import (
    ANALYSIS_DISCLAIMER,
    RecommendationResult,
    RecommendationStance,
)
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.financial_filing import FinancialFilingRepository
from br_financial_ai.repositories.financial_statement_item import (
    FinancialStatementItemRepository,
)
from br_financial_ai.repositories.news_article import NewsArticleRepository
from br_financial_ai.repositories.news_article_signal import (
    NewsArticleSignalRepository,
)
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.services.analysis_context import AnalysisContextService
from br_financial_ai.services.company_analysis import CompanyAnalysisService
from br_financial_ai.services.news_classification import (
    NewsClassificationService,
    classifier_identity_from_settings,
)

QUOTE_TIMESTAMP = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
PUBLISHED_AT = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _history_bars() -> list[dict[str, object]]:
    return [
        {
            "timestamp": datetime(2026, 8, day, tzinfo=UTC),
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1000,
        }
        for day, close in ((1, "10"), (2, "11"), (3, "12"))
    ]


def _market_client():
    from br_financial_ai.clients.yahoo_market import YahooMarketClient

    return YahooMarketClient(
        fetch_quote=lambda symbol: {
            "price": "46.87",
            "previous_close": "45.02",
            "currency": "BRL",
            "timestamp": QUOTE_TIMESTAMP,
            "market_cap": "200000",
        },
        fetch_history=lambda symbol, period: _history_bars(),
    )


def _classifier(payloads: list[object]) -> NewsClassifier:
    structured_model = AsyncMock()
    structured_model.ainvoke = AsyncMock(side_effect=payloads)
    return NewsClassifier(structured_model, concurrency=1)


def _signal_payload() -> NewsClassificationOutput:
    return NewsClassificationOutput(
        relevance="HIGH",
        materiality="HIGH",
        sentiment="POSITIVE",
        company_specific=True,
        categories=["production"],
        confidence=0.9,
        rationale="Company production guidance.",
    )


async def _seed_company_with_news(
    session: AsyncSession,
    *,
    ticker: str,
    cvm_code: str,
    cnpj: str,
    isin: str,
    news_titles: tuple[str, ...],
) -> Company:
    company = await CompanyRepository(session).add(
        Company(
            cvm_code=cvm_code,
            cnpj=cnpj,
            legal_name="PETROLEO BRASILEIRO S.A. PETROBRAS",
            trade_name="PETROBRAS",
        )
    )
    assert company.id is not None
    await SecurityRepository(session).add(
        Security(
            company_id=company.id,
            ticker=ticker,
            isin=isin,
            security_type="PN",
        )
    )
    filing = await FinancialFilingRepository(session).add(
        FinancialFiling(
            company_id=company.id,
            document_type="DFP",
            reference_date=date(2025, 12, 31),
            version=1,
            source_year=2025,
        )
    )
    assert filing.id is not None
    await FinancialStatementItemRepository(session).add_all(
        [
            FinancialStatementItem(
                filing_id=filing.id,
                statement_type="DRE",
                scope="CONSOLIDATED",
                exercise_order="ÚLTIMO",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
                statement_column=None,
                account_code=code,
                account_name=name,
                value=Decimal(value),
                currency="REAL",
                currency_scale="MIL",
                fixed_account_status="S",
                source_group="DF Consolidado - DRE",
            )
            for code, name, value in (
                ("3.01", "Receita", "100.0000000000"),
                ("3.03", "Resultado Bruto", "40.0000000000"),
                ("3.05", "Resultado operacional", "20.0000000000"),
                ("3.11", "Lucro", "10.0000000000"),
            )
        ]
    )
    news_repository = NewsArticleRepository(session)
    for index, title in enumerate(news_titles, start=1):
        url = f"https://example.com/news-{ticker.lower()}-{index}"
        await news_repository.add(
            NewsArticle(
                company_id=company.id,
                provider=NEWS_PROVIDER_YAHOO,
                provider_article_id=f"yahoo-{ticker}-{index}",
                title=title,
                summary=title,
                publisher="Reuters",
                url=url,
                canonical_url=url,
                published_at=PUBLISHED_AT,
                content_hash=news_content_hash(
                    title=title,
                    publisher="Reuters",
                    published_at=PUBLISHED_AT,
                    canonical_url=url,
                ),
            )
        )
    return company


def _recommendation() -> RecommendationResult:
    return RecommendationResult(
        ticker="CACH4",
        stance=RecommendationStance.NEUTRAL,
        confidence=Decimal("0.5"),
        summary="Neutral outlook.",
        positives=(),
        risks=(),
        fundamentals_view="Neutral.",
        valuation_view="Neutral.",
        market_view="Neutral.",
        news_view="News used.",
        limitations=(),
        evidence=(),
        as_of=QUOTE_TIMESTAMP,
        disclaimer=ANALYSIS_DISCLAIMER,
    )


@pytest.mark.asyncio
async def test_first_analysis_classifies_and_persists_missing_articles(
    db_session: AsyncSession,
) -> None:
    await _seed_company_with_news(
        db_session,
        ticker="CACH4",
        cvm_code="99401",
        cnpj="96000000000401",
        isin="BRCACH4CNPR6",
        news_titles=("Artigo um", "Artigo dois"),
    )
    classifier = _classifier([_signal_payload(), _signal_payload()])
    captured: list = []
    engine = AsyncMock()

    async def generate(context):
        captured.append(context)
        return _recommendation()

    engine.generate_recommendation = generate
    classification = NewsClassificationService(
        NewsArticleSignalRepository(db_session),
        classifier,
        identity=classifier_identity_from_settings(),
    )
    service = CompanyAnalysisService(
        AnalysisContextService(db_session, _market_client()),
        engine,
        classification,
    )

    await service.analyze_company("CACH4", reference_year=2025, news_limit=2)

    assert classifier._structured_model.ainvoke.await_count == 2
    assert classification.last_stats is not None
    assert classification.last_stats.cache_hits == 0
    assert classification.last_stats.cache_misses == 2
    assert classification.last_stats.classified == 2
    assert len(captured[0].news_signals) == 2
    assert [item.article_id for item in captured[0].news_signals] == [
        item.article_id for item in captured[0].recent_news
    ]
    article_ids = [
        item.article_id for item in captured[0].recent_news if item.article_id
    ]
    rows = await NewsArticleSignalRepository(
        db_session
    ).list_by_article_ids_and_identity(
        article_ids,
        classifier_identity_from_settings(),
    )
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_second_analysis_reuses_cache_with_zero_classifier_calls(
    db_session: AsyncSession,
) -> None:
    await _seed_company_with_news(
        db_session,
        ticker="CACH5",
        cvm_code="99402",
        cnpj="96000000000402",
        isin="BRCACH5CNPR6",
        news_titles=("Artigo um", "Artigo dois"),
    )
    classifier = _classifier([_signal_payload(), _signal_payload(), _signal_payload()])
    engine = AsyncMock()
    engine.generate_recommendation = AsyncMock(return_value=_recommendation())
    service = CompanyAnalysisService(
        AnalysisContextService(db_session, _market_client()),
        engine,
        NewsClassificationService(
            NewsArticleSignalRepository(db_session),
            classifier,
        ),
    )

    await service.analyze_company("CACH5", reference_year=2025, news_limit=2)
    assert classifier._structured_model.ainvoke.await_count == 2

    await service.analyze_company("CACH5", reference_year=2025, news_limit=2)
    assert classifier._structured_model.ainvoke.await_count == 2
    stats = service.news_classification_service.last_stats
    assert stats is not None
    assert stats.cache_hits == 2
    assert stats.cache_misses == 0
    assert stats.classified == 0


@pytest.mark.asyncio
async def test_partially_cached_set_classifies_only_missing_articles(
    db_session: AsyncSession,
) -> None:
    await _seed_company_with_news(
        db_session,
        ticker="CACH6",
        cvm_code="99403",
        cnpj="96000000000403",
        isin="BRCACH6CNPR6",
        news_titles=("Artigo um", "Artigo dois", "Artigo tres"),
    )
    classifier = _classifier([_signal_payload(), _signal_payload(), _signal_payload()])
    engine = AsyncMock()
    engine.generate_recommendation = AsyncMock(return_value=_recommendation())
    service = CompanyAnalysisService(
        AnalysisContextService(db_session, _market_client()),
        engine,
        NewsClassificationService(
            NewsArticleSignalRepository(db_session),
            classifier,
        ),
    )

    await service.analyze_company("CACH6", reference_year=2025, news_limit=2)
    assert classifier._structured_model.ainvoke.await_count == 2

    await service.analyze_company("CACH6", reference_year=2025, news_limit=3)
    assert classifier._structured_model.ainvoke.await_count == 3
    stats = service.news_classification_service.last_stats
    assert stats is not None
    assert stats.cache_hits == 2
    assert stats.cache_misses == 1
    assert stats.classified == 1


@pytest.mark.asyncio
async def test_one_classification_failure_is_degradable_and_not_cached(
    db_session: AsyncSession,
) -> None:
    await _seed_company_with_news(
        db_session,
        ticker="CACH7",
        cvm_code="99404",
        cnpj="96000000000404",
        isin="BRCACH7CNPR6",
        news_titles=("Artigo valido", "Artigo malformado"),
    )
    classifier = _classifier([_signal_payload(), RuntimeError("bad json")])
    captured: list = []
    engine = AsyncMock()

    async def generate(context):
        captured.append(context)
        return _recommendation()

    engine.generate_recommendation = generate
    identity = classifier_identity_from_settings()
    repository = NewsArticleSignalRepository(db_session)
    service = CompanyAnalysisService(
        AnalysisContextService(db_session, _market_client()),
        engine,
        NewsClassificationService(repository, classifier, identity=identity),
    )

    await service.analyze_company("CACH7", reference_year=2025, news_limit=2)

    context = captured[0]
    assert len(context.recent_news) == 2
    assert len(context.news_signals) == 1
    assert any(
        item.section == "news_classification" and item.reason == "classification_failed"
        for item in context.unavailable
    )
    article_ids = [
        item.article_id for item in context.recent_news if item.article_id is not None
    ]
    rows = await repository.list_by_article_ids_and_identity(article_ids, identity)
    assert len(rows) == 1
    stale = NewsClassifierIdentity(
        model_provider=identity.model_provider,
        model_name=identity.model_name,
        classifier_version=identity.classifier_version,
        prompt_version="news-v0",
    )
    assert await repository.list_by_article_ids_and_identity(article_ids, stale) == {}
