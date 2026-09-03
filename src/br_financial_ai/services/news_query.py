from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import NewsArticle
from br_financial_ai.repositories.news_article import (
    NewsArticleRepository,
)
from br_financial_ai.services.company_query import (
    CompanyQueryService,
)
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
)


class NewsQueryService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.company_query_service = CompanyQueryService(session)
        self.news_repository = NewsArticleRepository(session)

    async def get_recent_company_news(
        self,
        ticker: str,
        *,
        limit: int = 10,
    ) -> list[NewsArticle]:
        if limit < 1:
            raise ValueError("News limit must be at least 1.")

        company = await self.company_query_service.find_by_ticker(ticker)

        if company is None or company.id is None:
            raise CompanyNotFoundError(ticker.strip().upper())

        return await self.news_repository.list_recent_by_company(
            company_id=company.id,
            limit=limit,
        )
