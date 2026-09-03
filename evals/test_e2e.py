from time import perf_counter

import httpx
import pytest

from br_financial_ai.ai.news_classifier import create_news_classifier
from br_financial_ai.ai.recommendation import create_recommendation_engine
from br_financial_ai.clients.yahoo_market import YahooMarketClient
from br_financial_ai.db.session import async_session_factory
from br_financial_ai.eval.factual import evaluate_factual_consistency
from br_financial_ai.eval.grounding import evaluate_evidence_grounding
from br_financial_ai.eval.hallucination import (
    FORBIDDEN_STANCES,
    evaluate_hallucinations,
)
from br_financial_ai.eval.runtime import RESULTS
from br_financial_ai.main import app
from br_financial_ai.observability.timing import (
    LatencyTracker,
    TimedNewsClassifier,
    TimedYahooMarketClient,
)
from br_financial_ai.observability.usage import usage_as_dict
from br_financial_ai.repositories.news_article_signal import (
    NewsArticleSignalRepository,
)
from br_financial_ai.services.analysis_context import AnalysisContextService
from br_financial_ai.services.company_analysis import CompanyAnalysisService
from br_financial_ai.services.company_query import CompanyQueryService
from br_financial_ai.services.exceptions import CompanyNotFoundError
from br_financial_ai.services.news_classification import NewsClassificationService

pytestmark = [
    pytest.mark.eval,
    pytest.mark.external,
    pytest.mark.ollama,
    pytest.mark.yahoo,
    pytest.mark.slow,
    pytest.mark.asyncio,
]


async def test_petr4_http_e2e() -> None:
    async with async_session_factory() as session:
        company = await CompanyQueryService(session).find_by_ticker("PETR4")
        if company is None:
            pytest.skip("PETR4 is not present in the local database.")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        started = perf_counter()
        context_response = await client.get(
            "/api/v1/analysis/context/PETR4?news_limit=5"
        )
        context_seconds = perf_counter() - started
        assert context_response.status_code == 200, context_response.text
        context_payload = context_response.json()
        assert context_payload["ticker"] == "PETR4"
        assert "financials" in context_payload
        assert "valuation" in context_payload
        assert "market_quote" in context_payload
        assert "recent_news" in context_payload

        started = perf_counter()
        analysis_response = await client.post(
            "/api/v1/analysis",
            json={"ticker": "PETR4", "news_limit": 5},
        )
        analysis_seconds = perf_counter() - started
        assert analysis_response.status_code == 200, analysis_response.text
        payload = analysis_response.json()

    assert payload["ticker"] == "PETR4"
    assert payload["stance"] not in FORBIDDEN_STANCES
    assert payload["confidence"] is not None
    assert payload["evidence"]
    assert payload["limitations"]

    RESULTS.setdefault("e2e", {}).update(
        {
            "ticker": "PETR4",
            "stance": payload["stance"],
            "confidence": payload["confidence"],
            "limitations": payload["limitations"],
            "evidence_count": len(payload["evidence"]),
            "total_latency_seconds": round(context_seconds + analysis_seconds, 4),
            "context_http_latency_seconds": round(context_seconds, 4),
            "analysis_http_latency_seconds": round(analysis_seconds, 4),
        }
    )
    RESULTS.setdefault("performance", {})["total_analysis_latency"] = round(
        context_seconds + analysis_seconds,
        4,
    )


async def test_petr4_instrumented_latency_and_quality() -> None:
    tracker = LatencyTracker()
    async with async_session_factory() as session:
        company = await CompanyQueryService(session).find_by_ticker("PETR4")
        if company is None:
            pytest.skip("PETR4 is not present in the local database.")

        service = CompanyAnalysisService(
            AnalysisContextService(
                session,
                TimedYahooMarketClient(YahooMarketClient(), tracker),
            ),
            create_recommendation_engine(),
            NewsClassificationService(
                NewsArticleSignalRepository(session),
                TimedNewsClassifier(create_news_classifier(), tracker),
            ),
        )

        try:
            async with tracker.measure("context_build_latency"):
                context = (
                    await service.analysis_context_service.build_recommendation_context(
                        "PETR4",
                        news_limit=5,
                    )
                )
            context = await service.news_classification_service.enrich_context(
                context,
            )
            async with tracker.measure("recommendation_latency"):
                result = await service.recommendation_engine.generate_recommendation(
                    context,
                )
        except CompanyNotFoundError:
            pytest.skip("PETR4 is not present in the local database.")

    tracker.samples["total_analysis_latency"] = (
        tracker.samples.get("context_build_latency", 0.0)
        + tracker.samples.get("news_classification_latency", 0.0)
        + tracker.samples.get("recommendation_latency", 0.0)
    )
    grounding = evaluate_evidence_grounding(context, result)
    factual = evaluate_factual_consistency(context, result)
    hallucination = evaluate_hallucinations(context, result)

    RESULTS.setdefault("performance", {}).update(
        {name: round(value, 4) for name, value in tracker.samples.items()}
    )
    RESULTS.setdefault("e2e", {})["instrumented"] = {
        "stance": result.stance.value,
        "confidence": format(result.confidence, "f"),
        "factual_consistency": factual.score,
        "evidence_grounding": grounding.evidence_grounding_rate,
        "hallucination_count": hallucination.hallucination_count,
        "fabricated_evidence_count": grounding.fabricated_evidence_count,
        "news_articles": len(context.recent_news),
        "recommendation_prompt_characters": (
            None
            if service.recommendation_engine.last_prompt is None
            else service.recommendation_engine.last_prompt.character_count
        ),
    }
    RESULTS.setdefault("llm_usage", {})["e2e_recommendation"] = usage_as_dict(
        service.recommendation_engine.last_usage
    )

    assert result.ticker == "PETR4"
    assert grounding.fabricated_evidence_count == 0
    assert result.stance.value not in FORBIDDEN_STANCES
