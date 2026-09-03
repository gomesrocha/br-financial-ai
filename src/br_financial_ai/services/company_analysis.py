from br_financial_ai.ai.recommendation import RecommendationEngine
from br_financial_ai.domain.recommendation import RecommendationResult
from br_financial_ai.services.analysis_context import (
    AnalysisContextService,
)
from br_financial_ai.services.news_classification import (
    NewsClassificationService,
)


class CompanyAnalysisService:
    def __init__(
        self,
        analysis_context_service: AnalysisContextService,
        recommendation_engine: RecommendationEngine,
        news_classification_service: NewsClassificationService,
    ) -> None:
        self.analysis_context_service = analysis_context_service
        self.recommendation_engine = recommendation_engine
        self.news_classification_service = news_classification_service

    async def analyze_company(
        self,
        ticker: str,
        *,
        news_limit: int = 10,
        reference_year: int | None = None,
    ) -> RecommendationResult:
        context = await self.analysis_context_service.build_recommendation_context(
            ticker,
            news_limit=news_limit,
            reference_year=reference_year,
        )
        enriched = await self.news_classification_service.enrich_context(context)

        return await self.recommendation_engine.generate_recommendation(
            enriched,
        )
