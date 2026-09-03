from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import NewsArticle


class NewsArticleRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def add(
        self,
        article: NewsArticle,
    ) -> NewsArticle:
        self.session.add(article)
        await self.session.flush()
        await self.session.refresh(article)

        return article

    async def add_all(
        self,
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        self.session.add_all(articles)
        await self.session.flush()

        return articles

    async def find_existing(
        self,
        *,
        company_id: int,
        provider: str,
        provider_article_id: str | None,
        canonical_url: str,
        content_hash: str,
    ) -> NewsArticle | None:
        conditions = [
            (
                (NewsArticle.company_id == company_id)
                & (NewsArticle.provider == provider)
                & (NewsArticle.canonical_url == canonical_url)
            ),
            (
                (NewsArticle.company_id == company_id)
                & (NewsArticle.content_hash == content_hash)
            ),
        ]

        if provider_article_id is not None:
            conditions.append(
                (NewsArticle.company_id == company_id)
                & (NewsArticle.provider == provider)
                & (NewsArticle.provider_article_id == provider_article_id)
            )

        statement = select(NewsArticle).where(or_(*conditions)).limit(1)

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_recent_by_company(
        self,
        *,
        company_id: int,
        limit: int,
    ) -> list[NewsArticle]:
        statement = (
            select(NewsArticle)
            .where(NewsArticle.company_id == company_id)
            .order_by(
                NewsArticle.published_at.desc(),
                NewsArticle.id.desc(),
            )
            .limit(limit)
        )

        result = await self.session.execute(statement)

        return list(result.scalars().all())
