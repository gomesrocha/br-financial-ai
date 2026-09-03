from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.clients.yahoo_market import (
    MarketDataNotFoundError,
    YahooMarketClient,
    YahooMarketProviderError,
)
from br_financial_ai.db.models import (
    Company,
    FinancialFiling,
    FinancialStatementItem,
    NewsArticle,
    NewsArticleSignal,
    Security,
)
from br_financial_ai.domain.financial_profile import (
    METRIC_UNSUPPORTED_FOR_PROFILE,
)
from br_financial_ai.domain.news import (
    NEWS_PROVIDER_YAHOO,
    news_content_hash,
)
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.financial_filing import (
    FinancialFilingRepository,
)
from br_financial_ai.repositories.financial_statement_item import (
    FinancialStatementItemRepository,
)
from br_financial_ai.repositories.news_article import (
    NewsArticleRepository,
)
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.services.analysis_context import (
    AnalysisContextService,
)
from br_financial_ai.services.exceptions import CompanyNotFoundError
from br_financial_ai.services.news_classification import (
    classifier_identity_from_settings,
)

QUOTE_TIMESTAMP = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
PUBLISHED_AT = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _quote_payload() -> dict[str, object]:
    return {
        "price": "46.87",
        "previous_close": "45.02",
        "currency": "BRL",
        "timestamp": QUOTE_TIMESTAMP,
        "market_cap": "200000",
    }


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


def _market_client(
    *,
    history: dict[str, object] | None = None,
    quote_error: Exception | None = None,
) -> YahooMarketClient:
    resolved_history = history or {
        "1mo": _history_bars(),
        "3mo": _history_bars(),
        "1y": _history_bars(),
    }

    def fetch_quote(symbol: str) -> dict[str, object]:
        if quote_error is not None:
            raise quote_error

        return _quote_payload()

    def fetch_history(symbol: str, period: str) -> list[dict[str, object]]:
        payload = resolved_history[period]

        if isinstance(payload, Exception):
            raise payload

        if not isinstance(payload, list):
            raise TypeError("History payload must be a list.")

        return payload

    return YahooMarketClient(
        fetch_quote=fetch_quote,
        fetch_history=fetch_history,
    )


async def _seed_company(
    session: AsyncSession,
    *,
    ticker: str,
    cvm_code: str,
    cnpj: str,
    isin: str,
    news_titles: tuple[str, ...] = (),
    setor_ativ: str | None = None,
    trade_name: str = "PETROBRAS",
    legal_name: str = "PETROLEO BRASILEIRO S.A. PETROBRAS",
    dre_accounts: tuple[tuple[str, str, str], ...] = (
        ("3.01", "Receita", "100.0000000000"),
        ("3.03", "Resultado Bruto", "40.0000000000"),
        ("3.05", "Resultado operacional", "20.0000000000"),
        ("3.11", "Lucro", "10.0000000000"),
    ),
) -> Company:
    company_repository = CompanyRepository(session)
    security_repository = SecurityRepository(session)

    company = await company_repository.add(
        Company(
            cvm_code=cvm_code,
            cnpj=cnpj,
            legal_name=legal_name,
            trade_name=trade_name,
            setor_ativ=setor_ativ,
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker=ticker,
            isin=isin,
            security_type="PN",
        )
    )

    filing_repository = FinancialFilingRepository(session)
    item_repository = FinancialStatementItemRepository(session)
    filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="DFP",
            reference_date=date(2025, 12, 31),
            version=1,
            source_year=2025,
        )
    )

    assert filing.id is not None

    await item_repository.add_all(
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
            for code, name, value in dre_accounts
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


@pytest.mark.asyncio
async def test_build_recommendation_context(
    db_session: AsyncSession,
) -> None:
    await _seed_company(
        db_session,
        ticker="FCTX4",
        cvm_code="99301",
        cnpj="93000000000301",
        isin="BRCTX4ACNPR6",
        news_titles=("Petrobras anuncia guidance de producao",),
    )

    service = AnalysisContextService(
        db_session,
        _market_client(),
    )

    context = await service.build_recommendation_context(
        "fctx4",
        reference_year=2025,
        news_limit=10,
    )

    assert context.ticker == "FCTX4"
    assert context.company_name == "PETROBRAS"
    assert context.financial_profile == "NON_FINANCIAL"
    assert context.as_of == QUOTE_TIMESTAMP
    assert context.financials.document_type == "DFP"
    assert context.financials.revenue == Decimal("100000.0000000000")
    assert context.financials.currency == "BRL"
    assert context.valuation.price_to_sales == Decimal("2")
    assert context.valuation.price_to_earnings == Decimal("20")
    assert context.market_quote.price == Decimal("46.87")
    assert context.market_quote.market_cap == Decimal("200000")
    assert context.price_change.absolute == Decimal("1.85")
    assert [item.period for item in context.market_metrics] == [
        "1mo",
        "3mo",
        "1y",
    ]
    assert len(context.recent_news) == 1
    assert context.recent_news[0].title.startswith("Petrobras")
    assert context.news_signals == ()
    assert context.unavailable == ()
    assert not hasattr(service, "news_classifier")

    evidence_kinds = {item.kind for item in context.evidence}
    assert evidence_kinds == {
        "financial_statement",
        "market_quote",
        "market_history",
        "news",
    }
    assert any(
        item.source == "CVM" and item.reference == "DFP 2025"
        for item in context.evidence
    )
    assert any(
        item.source == "Yahoo Finance"
        and item.kind == "market_quote"
        and item.reference == "FCTX4.SA"
        for item in context.evidence
    )
    assert any(
        item.kind == "news" and item.reference == "https://example.com/news-fctx4-1"
        for item in context.evidence
    )


@pytest.mark.asyncio
async def test_unknown_ticker_is_fatal(
    db_session: AsyncSession,
) -> None:
    service = AnalysisContextService(
        db_session,
        _market_client(),
    )

    with pytest.raises(CompanyNotFoundError, match="ZZZZ4"):
        await service.build_recommendation_context("ZZZZ4")


@pytest.mark.asyncio
async def test_missing_market_quote_is_fatal(
    db_session: AsyncSession,
) -> None:
    await _seed_company(
        db_session,
        ticker="FCTX5",
        cvm_code="99302",
        cnpj="93000000000302",
        isin="BRCTX5ACNPR6",
    )

    service = AnalysisContextService(
        db_session,
        _market_client(quote_error=RuntimeError("yahoo down")),
    )

    with pytest.raises(YahooMarketProviderError):
        await service.build_recommendation_context(
            "FCTX5",
            reference_year=2025,
        )


@pytest.mark.asyncio
async def test_quote_not_found_is_fatal(
    db_session: AsyncSession,
) -> None:
    await _seed_company(
        db_session,
        ticker="FCTX6",
        cvm_code="99303",
        cnpj="93000000000303",
        isin="BRCTX6ACNPR6",
    )

    service = AnalysisContextService(
        db_session,
        YahooMarketClient(
            fetch_quote=lambda symbol: {"currency": "BRL"},
            fetch_history=lambda symbol, period: _history_bars(),
        ),
    )

    with pytest.raises(MarketDataNotFoundError):
        await service.build_recommendation_context(
            "FCTX6",
            reference_year=2025,
        )


@pytest.mark.asyncio
async def test_empty_news_is_valid_not_an_outage(
    db_session: AsyncSession,
) -> None:
    await _seed_company(
        db_session,
        ticker="FCTX7",
        cvm_code="99304",
        cnpj="93000000000304",
        isin="BRCTX7ACNPR6",
    )

    service = AnalysisContextService(
        db_session,
        _market_client(),
    )

    context = await service.build_recommendation_context(
        "FCTX7",
        reference_year=2025,
    )

    assert context.recent_news == ()
    assert context.news_signals == ()
    assert all(item.section != "news_classification" for item in context.unavailable)


@pytest.mark.asyncio
async def test_get_context_returns_cached_classification(
    db_session: AsyncSession,
) -> None:
    company = await _seed_company(
        db_session,
        ticker="FCTX8",
        cvm_code="99305",
        cnpj="93000000000305",
        isin="BRCTX8ACNPR6",
        news_titles=("Petrobras anuncia guidance de producao",),
    )
    articles = await NewsArticleRepository(db_session).list_recent_by_company(
        company_id=company.id or 0,
        limit=1,
    )
    identity = classifier_identity_from_settings()
    db_session.add(
        NewsArticleSignal(
            news_article_id=articles[0].id,
            model_provider=identity.model_provider,
            model_name=identity.model_name,
            classifier_version=identity.classifier_version,
            prompt_version=identity.prompt_version,
            relevance="HIGH",
            materiality="HIGH",
            sentiment="POSITIVE",
            company_specific=True,
            categories=["production"],
            confidence=Decimal("0.90000000"),
            rationale="Company production guidance.",
            classified_at=QUOTE_TIMESTAMP,
        )
    )
    await db_session.flush()

    context = await AnalysisContextService(
        db_session,
        _market_client(),
    ).build_recommendation_context(
        "FCTX8",
        reference_year=2025,
        news_limit=1,
    )

    assert len(context.recent_news) == 1
    assert len(context.news_signals) == 1
    assert context.news_signals[0].company_specific is True
    assert context.news_signals[0].article_id == context.recent_news[0].article_id
    assert all(item.section != "news_classification" for item in context.unavailable)


@pytest.mark.asyncio
async def test_get_context_ignores_mismatched_classifier_identity(
    db_session: AsyncSession,
) -> None:
    company = await _seed_company(
        db_session,
        ticker="FCTY4",
        cvm_code="99307",
        cnpj="93000000000307",
        isin="BRCTX9ACNPR6",
        news_titles=("Petrobras anuncia guidance de producao",),
    )
    articles = await NewsArticleRepository(db_session).list_recent_by_company(
        company_id=company.id or 0,
        limit=1,
    )
    db_session.add(
        NewsArticleSignal(
            news_article_id=articles[0].id,
            model_provider="ollama",
            model_name="llama3.1",
            classifier_version=1,
            prompt_version="news-v0",
            relevance="HIGH",
            materiality="LOW",
            sentiment="NEUTRAL",
            company_specific=False,
            categories=["macro"],
            confidence=Decimal("0.50000000"),
            rationale="Stale prompt version.",
            classified_at=QUOTE_TIMESTAMP,
        )
    )
    await db_session.flush()

    context = await AnalysisContextService(
        db_session,
        _market_client(),
    ).build_recommendation_context(
        "FCTY4",
        reference_year=2025,
        news_limit=1,
    )

    assert len(context.recent_news) == 1
    assert context.news_signals == ()


@pytest.mark.asyncio
async def test_history_provider_error_is_not_empty_metrics(
    db_session: AsyncSession,
) -> None:
    await _seed_company(
        db_session,
        ticker="FCTX3",
        cvm_code="99306",
        cnpj="93000000000306",
        isin="BRCTX3ACNOR1",
    )

    service = AnalysisContextService(
        db_session,
        _market_client(
            history={
                "1mo": _history_bars(),
                "3mo": RuntimeError("yahoo history down"),
                "1y": [],
            }
        ),
    )

    context = await service.build_recommendation_context(
        "FCTX3",
        reference_year=2025,
    )

    assert [item.period for item in context.market_metrics] == ["1mo"]
    reasons = {
        (item.reason, item.reference)
        for item in context.unavailable
        if item.section == "market_history"
    }
    assert ("provider_error", "FCTX3.SA 3mo") in reasons
    assert ("insufficient_price_history", "FCTX3.SA 1y") in reasons


def _unsupported_metrics(context) -> set[str]:
    return {
        item.reference
        for item in context.unavailable
        if item.reason == METRIC_UNSUPPORTED_FOR_PROFILE and item.reference
    }


@pytest.mark.asyncio
async def test_petr4_context_keeps_industrial_metrics(
    db_session: AsyncSession,
) -> None:
    await _seed_company(
        db_session,
        ticker="FPTR4",
        cvm_code="99512",
        cnpj="33000167000901",
        isin="BRFPTRACNPR6",
        setor_ativ="Petróleo e Gás",
        news_titles=("Petrobras anuncia guidance de producao",),
    )

    context = await AnalysisContextService(
        db_session,
        _market_client(),
    ).build_recommendation_context("FPTR4", reference_year=2025)

    assert context.financial_profile == "NON_FINANCIAL"
    assert context.financials.revenue == Decimal("100000.0000000000")
    assert context.financials.gross_profit == Decimal("40000.0000000000")
    assert context.financials.net_income == Decimal("10000.0000000000")
    assert context.valuation.gross_margin == Decimal("0.4")
    assert context.valuation.price_to_earnings == Decimal("20")
    assert _unsupported_metrics(context) == set()


@pytest.mark.asyncio
async def test_itub4_context_exposes_profile_aware_metrics(
    db_session: AsyncSession,
) -> None:
    await _seed_company(
        db_session,
        ticker="FITB4",
        cvm_code="99348",
        cnpj="60872504000923",
        isin="BRFITBACNPR1",
        setor_ativ="Bancos",
        trade_name="ITAÚ UNIBANCO",
        legal_name="ITAÚ UNIBANCO HOLDING S.A.",
        dre_accounts=(
            (
                "3.09",
                "Lucro/Prejuízo Consolidado do Período",
                "10.0000000000",
            ),
        ),
    )

    context = await AnalysisContextService(
        db_session,
        _market_client(),
    ).build_recommendation_context("FITB4", reference_year=2025)

    assert context.financial_profile == "FINANCIAL_INSTITUTION"
    assert context.financials.net_income == Decimal("10000.0000000000")
    assert context.financials.revenue is None
    assert context.financials.gross_profit is None
    assert context.valuation.gross_margin is None
    assert context.valuation.price_to_sales is None
    assert context.valuation.price_to_earnings == Decimal("20")
    unsupported = _unsupported_metrics(context)
    assert "gross_profit" in unsupported
    assert "revenue" in unsupported
    assert "gross_margin" in unsupported
    assert "price_to_sales" in unsupported
    assert "net_income" not in unsupported
    assert "price_to_earnings" not in unsupported


@pytest.mark.asyncio
async def test_bbdc4_context_exposes_profile_aware_metrics(
    db_session: AsyncSession,
) -> None:
    await _seed_company(
        db_session,
        ticker="FBBD4",
        cvm_code="99006",
        cnpj="60746948000912",
        isin="BRFBBDACNPR8",
        setor_ativ="Bancos",
        trade_name="BANCO BRADESCO S.A.",
        legal_name="BANCO BRADESCO S.A.",
        dre_accounts=(
            (
                "3.11",
                "Lucro ou Prejuízo Líquido Consolidado do Período",
                "10.0000000000",
            ),
        ),
    )

    context = await AnalysisContextService(
        db_session,
        _market_client(),
    ).build_recommendation_context("FBBD4", reference_year=2025)

    assert context.financial_profile == "FINANCIAL_INSTITUTION"
    assert context.financials.net_income == Decimal("10000.0000000000")
    assert context.financials.gross_profit is None
    assert "gross_profit" in _unsupported_metrics(context)
    assert context.valuation.price_to_earnings is not None
