from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.ai.news_classifier import create_news_classifier
from br_financial_ai.ai.recommendation import (
    RecommendationEngine,
    create_recommendation_engine,
)
from br_financial_ai.clients.b3 import B3_REQUEST_HEADERS
from br_financial_ai.clients.yahoo_market import YahooMarketClient
from br_financial_ai.db.session import get_session
from br_financial_ai.repositories.news_article_signal import (
    NewsArticleSignalRepository,
)
from br_financial_ai.services.analysis_context import (
    AnalysisContextService,
)
from br_financial_ai.services.company_analysis import (
    CompanyAnalysisService,
)
from br_financial_ai.services.company_onboarding import (
    CompanyOnboardingService,
    FastApiOnboardingScheduler,
    OnboardingJobScheduler,
    create_onboarding_service,
)
from br_financial_ai.services.company_query import CompanyQueryService
from br_financial_ai.services.financial_query import (
    FinancialQueryService,
)
from br_financial_ai.services.news_classification import (
    NewsClassificationService,
)
from br_financial_ai.services.tracked_company import TrackedCompanyService

SessionDep = Annotated[
    AsyncSession,
    Depends(get_session),
]


def get_company_query_service(
    session: SessionDep,
) -> CompanyQueryService:
    return CompanyQueryService(session)


CompanyQueryServiceDep = Annotated[
    CompanyQueryService,
    Depends(get_company_query_service),
]


def get_financial_query_service(
    session: SessionDep,
) -> FinancialQueryService:
    return FinancialQueryService(session)


FinancialQueryServiceDep = Annotated[
    FinancialQueryService,
    Depends(get_financial_query_service),
]


def get_yahoo_market_client() -> YahooMarketClient:
    return YahooMarketClient()


YahooMarketClientDep = Annotated[
    YahooMarketClient,
    Depends(get_yahoo_market_client),
]


def get_analysis_context_service(
    session: SessionDep,
    market_client: YahooMarketClientDep,
) -> AnalysisContextService:
    return AnalysisContextService(
        session,
        market_client,
    )


AnalysisContextServiceDep = Annotated[
    AnalysisContextService,
    Depends(get_analysis_context_service),
]


def get_recommendation_engine() -> RecommendationEngine:
    return create_recommendation_engine()


RecommendationEngineDep = Annotated[
    RecommendationEngine,
    Depends(get_recommendation_engine),
]


def get_company_analysis_service(
    session: SessionDep,
    analysis_context_service: AnalysisContextServiceDep,
    recommendation_engine: RecommendationEngineDep,
) -> CompanyAnalysisService:
    return CompanyAnalysisService(
        analysis_context_service,
        recommendation_engine,
        NewsClassificationService(
            NewsArticleSignalRepository(session),
            create_news_classifier(),
        ),
    )


CompanyAnalysisServiceDep = Annotated[
    CompanyAnalysisService,
    Depends(get_company_analysis_service),
]


def get_tracked_company_service(
    session: SessionDep,
) -> TrackedCompanyService:
    return TrackedCompanyService(session)


TrackedCompanyServiceDep = Annotated[
    TrackedCompanyService,
    Depends(get_tracked_company_service),
]


async def get_onboarding_http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=5.0,
            read=180.0,
            write=30.0,
            pool=5.0,
        ),
        follow_redirects=True,
        headers=B3_REQUEST_HEADERS,
    ) as client:
        yield client


OnboardingHttpClientDep = Annotated[
    httpx.AsyncClient,
    Depends(get_onboarding_http_client),
]


def get_onboarding_service(
    session: SessionDep,
    http_client: OnboardingHttpClientDep,
) -> CompanyOnboardingService:
    return create_onboarding_service(session, http_client)


OnboardingServiceDep = Annotated[
    CompanyOnboardingService,
    Depends(get_onboarding_service),
]


def get_onboarding_scheduler(
    background_tasks: BackgroundTasks,
) -> OnboardingJobScheduler:
    return FastApiOnboardingScheduler(background_tasks.add_task)


OnboardingJobSchedulerDep = Annotated[
    OnboardingJobScheduler,
    Depends(get_onboarding_scheduler),
]
