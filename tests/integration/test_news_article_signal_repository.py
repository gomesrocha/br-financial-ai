from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import Company, NewsArticle, NewsArticleSignal
from br_financial_ai.domain.news import NEWS_PROVIDER_YAHOO, news_content_hash
from br_financial_ai.domain.news_signals import (
    NewsClassifierIdentity,
    NewsMateriality,
    NewsRelevance,
    NewsSentiment,
    NewsSignal,
)
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.news_article import NewsArticleRepository
from br_financial_ai.repositories.news_article_signal import (
    NewsArticleSignalRepository,
)

PUBLISHED_AT = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
IDENTITY = NewsClassifierIdentity(
    model_provider="ollama",
    model_name="llama3.1",
    classifier_version=1,
    prompt_version="news-v1",
)


async def _seed_article(session: AsyncSession) -> NewsArticle:
    company = await CompanyRepository(session).add(
        Company(
            cvm_code="SIG101",
            cnpj="95000000000101",
            legal_name="EMPRESA SINAL S.A.",
            trade_name="SINAL",
        )
    )
    assert company.id is not None
    url = "https://example.com/signal-1"
    return await NewsArticleRepository(session).add(
        NewsArticle(
            company_id=company.id,
            provider=NEWS_PROVIDER_YAHOO,
            provider_article_id="yahoo-signal-1",
            title="Petrobras anuncia resultado",
            summary="Resumo",
            publisher="Reuters",
            url=url,
            canonical_url=url,
            published_at=PUBLISHED_AT,
            content_hash=news_content_hash(
                title="Petrobras anuncia resultado",
                publisher="Reuters",
                published_at=PUBLISHED_AT,
                canonical_url=url,
            ),
        )
    )


def _domain_signal(article_id: int) -> NewsSignal:
    return NewsSignal(
        article_id=article_id,
        relevance=NewsRelevance.HIGH,
        materiality=NewsMateriality.MEDIUM,
        sentiment=NewsSentiment.POSITIVE,
        company_specific=True,
        categories=("production",),
        confidence=Decimal("0.86"),
        rationale="Company production guidance.",
    )


@pytest.mark.asyncio
async def test_persist_news_article_signal(
    db_session: AsyncSession,
) -> None:
    article = await _seed_article(db_session)
    assert article.id is not None
    repository = NewsArticleSignalRepository(db_session)

    stored = await repository.upsert_signal(_domain_signal(article.id), IDENTITY)

    assert stored.id is not None
    assert stored.news_article_id == article.id
    assert stored.model_provider == "ollama"
    assert stored.prompt_version == "news-v1"
    loaded = await repository.get_by_article_and_identity(article.id, IDENTITY)
    assert loaded is not None
    assert loaded.relevance == "HIGH"
    assert loaded.categories == ["production"]


@pytest.mark.asyncio
async def test_classification_identity_uniqueness(
    db_session: AsyncSession,
) -> None:
    article = await _seed_article(db_session)
    assert article.id is not None
    repository = NewsArticleSignalRepository(db_session)
    await repository.add(
        NewsArticleSignal(
            news_article_id=article.id,
            model_provider=IDENTITY.model_provider,
            model_name=IDENTITY.model_name,
            classifier_version=IDENTITY.classifier_version,
            prompt_version=IDENTITY.prompt_version,
            relevance="LOW",
            materiality="LOW",
            sentiment="NEUTRAL",
            company_specific=False,
            categories=[],
            confidence=Decimal("0.10"),
            rationale="first",
            classified_at=PUBLISHED_AT,
        )
    )

    with pytest.raises(IntegrityError):
        await repository.add(
            NewsArticleSignal(
                news_article_id=article.id,
                model_provider=IDENTITY.model_provider,
                model_name=IDENTITY.model_name,
                classifier_version=IDENTITY.classifier_version,
                prompt_version=IDENTITY.prompt_version,
                relevance="HIGH",
                materiality="HIGH",
                sentiment="POSITIVE",
                company_specific=True,
                categories=["earnings"],
                confidence=Decimal("0.90"),
                rationale="duplicate",
                classified_at=PUBLISHED_AT,
            )
        )


@pytest.mark.asyncio
async def test_load_cached_classification_and_version_mismatch(
    db_session: AsyncSession,
) -> None:
    article = await _seed_article(db_session)
    assert article.id is not None
    repository = NewsArticleSignalRepository(db_session)
    await repository.upsert_signal(_domain_signal(article.id), IDENTITY)

    cached = await repository.list_by_article_ids_and_identity(
        [article.id],
        IDENTITY,
    )
    assert article.id in cached

    mismatched = await repository.list_by_article_ids_and_identity(
        [article.id],
        NewsClassifierIdentity(
            model_provider="ollama",
            model_name="llama3.1",
            classifier_version=1,
            prompt_version="news-v0",
        ),
    )
    assert mismatched == {}
