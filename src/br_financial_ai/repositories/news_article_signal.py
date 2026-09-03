from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from br_financial_ai.db.models import NewsArticleSignal
from br_financial_ai.domain.news_signals import NewsClassifierIdentity, NewsSignal


class NewsArticleSignalRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def add(
        self,
        signal: NewsArticleSignal,
    ) -> NewsArticleSignal:
        self.session.add(signal)
        await self.session.flush()
        await self.session.refresh(signal)
        return signal

    async def get_by_article_and_identity(
        self,
        news_article_id: int,
        identity: NewsClassifierIdentity,
    ) -> NewsArticleSignal | None:
        statement = select(NewsArticleSignal).where(
            *_identity_filters(news_article_id, identity)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_article_ids_and_identity(
        self,
        article_ids: Sequence[int],
        identity: NewsClassifierIdentity,
    ) -> dict[int, NewsArticleSignal]:
        if not article_ids:
            return {}

        statement = select(NewsArticleSignal).where(
            NewsArticleSignal.news_article_id.in_(list(article_ids)),
            NewsArticleSignal.model_provider == identity.model_provider,
            NewsArticleSignal.model_name == identity.model_name,
            NewsArticleSignal.classifier_version == identity.classifier_version,
            NewsArticleSignal.prompt_version == identity.prompt_version,
        )
        result = await self.session.execute(statement)
        return {row.news_article_id: row for row in result.scalars().all()}

    async def upsert_signal(
        self,
        signal: NewsSignal,
        identity: NewsClassifierIdentity,
        *,
        classified_at: datetime | None = None,
    ) -> NewsArticleSignal:
        if signal.article_id is None:
            raise ValueError("Persisted news signals require an article id.")

        existing = await self.get_by_article_and_identity(
            signal.article_id,
            identity,
        )
        timestamp = classified_at or datetime.now(UTC)
        if existing is None:
            return await self.add(
                _row_from_signal(signal, identity, classified_at=timestamp)
            )

        existing.relevance = signal.relevance.value
        existing.materiality = signal.materiality.value
        existing.sentiment = signal.sentiment.value
        existing.company_specific = signal.company_specific
        existing.categories = list(signal.categories)
        existing.confidence = signal.confidence
        existing.rationale = signal.rationale
        existing.classified_at = timestamp
        existing.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(existing)
        return existing


def _identity_filters(
    news_article_id: int,
    identity: NewsClassifierIdentity,
) -> tuple[object, ...]:
    return (
        NewsArticleSignal.news_article_id == news_article_id,
        NewsArticleSignal.model_provider == identity.model_provider,
        NewsArticleSignal.model_name == identity.model_name,
        NewsArticleSignal.classifier_version == identity.classifier_version,
        NewsArticleSignal.prompt_version == identity.prompt_version,
    )


def _row_from_signal(
    signal: NewsSignal,
    identity: NewsClassifierIdentity,
    *,
    classified_at: datetime,
) -> NewsArticleSignal:
    assert signal.article_id is not None
    return NewsArticleSignal(
        news_article_id=signal.article_id,
        model_provider=identity.model_provider,
        model_name=identity.model_name,
        classifier_version=identity.classifier_version,
        prompt_version=identity.prompt_version,
        relevance=signal.relevance.value,
        materiality=signal.materiality.value,
        sentiment=signal.sentiment.value,
        company_specific=signal.company_specific,
        categories=list(signal.categories),
        confidence=signal.confidence,
        rationale=signal.rationale,
        classified_at=classified_at,
    )
