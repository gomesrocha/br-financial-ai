from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import Company, Security
from br_financial_ai.domain.news import NewsArticleRecord
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.security import (
    SecurityRepository,
)
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
)
from br_financial_ai.services.news_ingestion import (
    NewsIngestionService,
)
from br_financial_ai.services.news_query import NewsQueryService

PUBLISHED_AT = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

TRACKED_ARTICLE = NewsArticleRecord(
    yahoo_symbol="PETR4.SA",
    title="Petrobras anuncia resultado trimestral",
    summary="Receita permanece resiliente no segundo trimestre.",
    publisher="Reuters",
    published_at=PUBLISHED_AT,
    url=("https://example.com/petrobras-resultado?siteid=yhoof2&yptr=yahoo"),
    provider_article_id="yahoo-petr-1",
)


async def _seed_company_with_securities(
    session: AsyncSession,
) -> Company:
    company_repository = CompanyRepository(session)
    security_repository = SecurityRepository(session)

    company = await company_repository.add(
        Company(
            cvm_code="NEWS201",
            cnpj="94000000000201",
            legal_name="PETROLEO BRASILEIRO S.A. PETROBRAS",
            trade_name="PETROBRAS",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="TEST3",
            isin="BRNWS3ACNOR1",
            security_type="ON",
        )
    )
    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="TEST4",
            isin="BRNWS4ACNPR6",
            security_type="PN",
        )
    )

    return company


def _news_client(
    records: list[NewsArticleRecord],
) -> AsyncMock:
    client = AsyncMock()
    client.get_company_news = AsyncMock(return_value=records)
    return client


@pytest.mark.asyncio
async def test_ingest_company_news_from_ticker(
    db_session: AsyncSession,
) -> None:
    company = await _seed_company_with_securities(db_session)
    client = _news_client([TRACKED_ARTICLE])
    service = NewsIngestionService(db_session, client)

    result = await service.sync_company_news("TEST4", limit=20)

    assert result.ticker == "TEST4"
    assert result.company_id == company.id
    assert result.fetched == 1
    assert result.created == 1
    assert result.skipped == 0

    client.get_company_news.assert_awaited_once_with(
        "TEST4",
        limit=20,
    )


@pytest.mark.asyncio
async def test_news_ingestion_is_idempotent(
    db_session: AsyncSession,
) -> None:
    await _seed_company_with_securities(db_session)
    client = _news_client([TRACKED_ARTICLE])
    service = NewsIngestionService(db_session, client)

    first = await service.sync_company_news("TEST4")
    second = await service.sync_company_news("TEST4")

    assert first.created == 1
    assert first.skipped == 0
    assert second.created == 0
    assert second.skipped == 1
    assert second.fetched == 1


@pytest.mark.asyncio
async def test_query_news_through_sibling_security(
    db_session: AsyncSession,
) -> None:
    await _seed_company_with_securities(db_session)
    client = _news_client([TRACKED_ARTICLE])
    ingestion = NewsIngestionService(db_session, client)

    await ingestion.sync_company_news("TEST4")

    query = NewsQueryService(db_session)
    articles = await query.get_recent_company_news("TEST3")

    assert len(articles) == 1
    assert articles[0].title == ("Petrobras anuncia resultado trimestral")
    assert articles[0].canonical_url == ("https://example.com/petrobras-resultado")
    assert articles[0].url == TRACKED_ARTICLE.url


@pytest.mark.asyncio
async def test_ingest_unknown_ticker_raises(
    db_session: AsyncSession,
) -> None:
    service = NewsIngestionService(db_session, _news_client([]))

    with pytest.raises(CompanyNotFoundError):
        await service.sync_company_news("NONE3")


@pytest.mark.asyncio
async def test_query_unknown_ticker_raises(
    db_session: AsyncSession,
) -> None:
    query = NewsQueryService(db_session)

    with pytest.raises(CompanyNotFoundError):
        await query.get_recent_company_news("NONE3")


@pytest.mark.asyncio
async def test_query_rejects_invalid_limit(
    db_session: AsyncSession,
) -> None:
    query = NewsQueryService(db_session)

    with pytest.raises(ValueError, match="News limit"):
        await query.get_recent_company_news("TEST4", limit=0)
