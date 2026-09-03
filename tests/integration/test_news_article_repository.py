from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import Company, NewsArticle, Security
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.news_article import (
    NewsArticleRepository,
)
from br_financial_ai.repositories.security import (
    SecurityRepository,
)


async def _add_company(
    session: AsyncSession,
    *,
    cvm_code: str,
    cnpj: str,
) -> Company:
    company_repository = CompanyRepository(session)

    return await company_repository.add(
        Company(
            cvm_code=cvm_code,
            cnpj=cnpj,
            legal_name=f"EMPRESA {cvm_code} S.A.",
            trade_name=f"EMPRESA {cvm_code}",
        )
    )


def _article(
    *,
    company_id: int,
    title: str,
    canonical_url: str,
    published_at: datetime,
    content_hash: str,
    provider_article_id: str | None = "yahoo-1",
) -> NewsArticle:
    return NewsArticle(
        company_id=company_id,
        provider="yahoo",
        provider_article_id=provider_article_id,
        title=title,
        summary="Resumo",
        publisher="Reuters",
        url=canonical_url,
        canonical_url=canonical_url,
        published_at=published_at,
        content_hash=content_hash,
    )


@pytest.mark.asyncio
async def test_news_article_persistence(
    db_session: AsyncSession,
) -> None:
    company = await _add_company(
        db_session,
        cvm_code="NEWS101",
        cnpj="94000000000101",
    )

    assert company.id is not None

    repository = NewsArticleRepository(db_session)
    published_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    article = await repository.add(
        _article(
            company_id=company.id,
            title="Petrobras anuncia resultado",
            canonical_url="https://example.com/resultado",
            published_at=published_at,
            content_hash="a" * 64,
        )
    )

    assert article.id is not None
    assert article.company_id == company.id
    assert article.provider == "yahoo"
    assert article.published_at.tzinfo is not None
    assert article.fetched_at.tzinfo is not None


@pytest.mark.asyncio
async def test_list_recent_news_newest_first(
    db_session: AsyncSession,
) -> None:
    company = await _add_company(
        db_session,
        cvm_code="NEWS102",
        cnpj="94000000000102",
    )

    assert company.id is not None

    repository = NewsArticleRepository(db_session)
    newer = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
    older = newer - timedelta(days=1)

    await repository.add_all(
        [
            _article(
                company_id=company.id,
                title="Noticia antiga",
                canonical_url="https://example.com/antiga",
                published_at=older,
                content_hash="b" * 64,
                provider_article_id="old",
            ),
            _article(
                company_id=company.id,
                title="Noticia nova",
                canonical_url="https://example.com/nova",
                published_at=newer,
                content_hash="c" * 64,
                provider_article_id="new",
            ),
        ]
    )

    recent = await repository.list_recent_by_company(
        company_id=company.id,
        limit=10,
    )

    assert [article.title for article in recent] == [
        "Noticia nova",
        "Noticia antiga",
    ]


@pytest.mark.asyncio
async def test_list_recent_news_filters_by_company(
    db_session: AsyncSession,
) -> None:
    first = await _add_company(
        db_session,
        cvm_code="NEWS103",
        cnpj="94000000000103",
    )
    second = await _add_company(
        db_session,
        cvm_code="NEWS104",
        cnpj="94000000000104",
    )

    assert first.id is not None
    assert second.id is not None

    repository = NewsArticleRepository(db_session)
    published_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    await repository.add_all(
        [
            _article(
                company_id=first.id,
                title="Empresa um",
                canonical_url="https://example.com/um",
                published_at=published_at,
                content_hash="d" * 64,
                provider_article_id="one",
            ),
            _article(
                company_id=second.id,
                title="Empresa dois",
                canonical_url="https://example.com/dois",
                published_at=published_at,
                content_hash="e" * 64,
                provider_article_id="two",
            ),
        ]
    )

    recent = await repository.list_recent_by_company(
        company_id=first.id,
        limit=10,
    )

    assert [article.title for article in recent] == ["Empresa um"]


@pytest.mark.asyncio
async def test_find_existing_news_article_identity(
    db_session: AsyncSession,
) -> None:
    company = await _add_company(
        db_session,
        cvm_code="NEWS105",
        cnpj="94000000000105",
    )

    assert company.id is not None

    repository = NewsArticleRepository(db_session)
    published_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    await repository.add(
        _article(
            company_id=company.id,
            title="Petrobras anuncia resultado",
            canonical_url="https://example.com/resultado",
            published_at=published_at,
            content_hash="f" * 64,
            provider_article_id="yahoo-dup",
        )
    )

    found = await repository.find_existing(
        company_id=company.id,
        provider="yahoo",
        provider_article_id="yahoo-dup",
        canonical_url="https://example.com/other",
        content_hash="0" * 64,
    )

    assert found is not None
    assert found.title == "Petrobras anuncia resultado"


@pytest.mark.asyncio
async def test_news_belongs_to_company_not_security(
    db_session: AsyncSession,
) -> None:
    company = await _add_company(
        db_session,
        cvm_code="NEWS106",
        cnpj="94000000000106",
    )

    assert company.id is not None

    security_repository = SecurityRepository(db_session)

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="TEST3",
            isin="BRTESTACNOR1",
            security_type="ON",
        )
    )
    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="TEST4",
            isin="BRTESTACNPR6",
            security_type="PN",
        )
    )

    repository = NewsArticleRepository(db_session)

    article = await repository.add(
        _article(
            company_id=company.id,
            title="Noticia da empresa",
            canonical_url="https://example.com/empresa",
            published_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
            content_hash="1" * 64,
        )
    )

    assert article.company_id == company.id
    assert not hasattr(article, "security_id")
    assert not hasattr(article, "ticker")
