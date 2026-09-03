from decimal import Decimal

import pytest

from br_financial_ai.ai.news_classifier import create_news_classifier
from br_financial_ai.ai.recommendation import create_recommendation_engine
from br_financial_ai.clients.yahoo_market import YahooMarketClient
from br_financial_ai.db.session import async_session_factory
from br_financial_ai.repositories.news_article_signal import (
    NewsArticleSignalRepository,
)
from br_financial_ai.services.analysis_context import (
    AnalysisContextService,
)
from br_financial_ai.services.company_analysis import (
    CompanyAnalysisService,
)
from br_financial_ai.services.company_query import CompanyQueryService
from br_financial_ai.services.exceptions import CompanyNotFoundError
from br_financial_ai.services.news_classification import (
    NewsClassificationService,
)

pytestmark = [
    pytest.mark.eval,
    pytest.mark.external,
    pytest.mark.ollama,
    pytest.mark.yahoo,
    pytest.mark.slow,
]


@pytest.mark.asyncio
async def test_live_petr4_recommendation() -> None:
    async with async_session_factory() as session:
        company = await CompanyQueryService(session).find_by_ticker("PETR4")

        if company is None:
            pytest.skip("PETR4 is not present in the local database.")

        service = CompanyAnalysisService(
            AnalysisContextService(
                session,
                YahooMarketClient(),
            ),
            create_recommendation_engine(),
            NewsClassificationService(
                NewsArticleSignalRepository(session),
                create_news_classifier(),
            ),
        )

        try:
            result = await service.analyze_company("PETR4", news_limit=5)
        except CompanyNotFoundError:
            pytest.skip("PETR4 is not present in the local database.")

        assert result.ticker == "PETR4"
        assert result.as_of.tzinfo is not None
        assert result.confidence >= Decimal("0")
        assert result.confidence <= Decimal("1")
        assert result.summary
        assert result.fundamentals_view
        print(result.stance)
        print(result.confidence)
        print(result.summary)
        print(result.limitations)
