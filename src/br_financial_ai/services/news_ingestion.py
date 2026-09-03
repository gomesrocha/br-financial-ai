from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.clients.yahoo_news import YahooNewsClient
from br_financial_ai.db.models import NewsArticle
from br_financial_ai.domain.news import (
    NEWS_PROVIDER_YAHOO,
    NewsArticleRecord,
    news_content_hash,
)
from br_financial_ai.repositories.news_article import (
    NewsArticleRepository,
)
from br_financial_ai.services.company_query import (
    CompanyQueryService,
)
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
)
from br_financial_ai.utils.urls import canonicalize_url


@dataclass(frozen=True, slots=True)
class NewsIngestionResult:
    ticker: str
    company_id: int
    fetched: int
    created: int
    skipped: int


class NewsIngestionService:
    def __init__(
        self,
        session: AsyncSession,
        news_client: YahooNewsClient,
    ) -> None:
        self.session = session
        self.news_client = news_client
        self.company_query_service = CompanyQueryService(session)
        self.news_repository = NewsArticleRepository(session)

    async def sync_company_news(
        self,
        ticker: str,
        *,
        limit: int = 20,
    ) -> NewsIngestionResult:
        normalized_ticker = ticker.strip().upper()

        company = await self.company_query_service.find_by_ticker(
            normalized_ticker,
        )

        if company is None or company.id is None:
            raise CompanyNotFoundError(normalized_ticker)

        records = await self.news_client.get_company_news(
            normalized_ticker,
            limit=limit,
        )

        created = 0
        skipped = 0
        pending: list[NewsArticle] = []
        seen_identities: set[tuple[str, str, str | None]] = set()

        try:
            for record in records:
                article = self._build_article(
                    company_id=company.id,
                    record=record,
                )
                identity = (
                    article.canonical_url,
                    article.content_hash,
                    article.provider_article_id,
                )

                if identity in seen_identities:
                    skipped += 1
                    continue

                existing = await self.news_repository.find_existing(
                    company_id=company.id,
                    provider=article.provider,
                    provider_article_id=article.provider_article_id,
                    canonical_url=article.canonical_url,
                    content_hash=article.content_hash,
                )

                if existing is not None:
                    skipped += 1
                    continue

                seen_identities.add(identity)
                pending.append(article)
                created += 1

            if pending:
                await self.news_repository.add_all(pending)

            await self.session.commit()

        except Exception:
            await self.session.rollback()
            raise

        return NewsIngestionResult(
            ticker=normalized_ticker,
            company_id=company.id,
            fetched=len(records),
            created=created,
            skipped=skipped,
        )

    def _build_article(
        self,
        *,
        company_id: int,
        record: NewsArticleRecord,
    ) -> NewsArticle:
        canonical_url = canonicalize_url(record.url)

        return NewsArticle(
            company_id=company_id,
            provider=NEWS_PROVIDER_YAHOO,
            provider_article_id=record.provider_article_id,
            title=record.title,
            summary=record.summary,
            publisher=record.publisher,
            url=record.url,
            canonical_url=canonical_url,
            published_at=record.published_at,
            fetched_at=datetime.now(UTC),
            content_hash=news_content_hash(
                title=record.title,
                publisher=record.publisher,
                published_at=record.published_at,
                canonical_url=canonical_url,
            ),
        )
