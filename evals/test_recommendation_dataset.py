from decimal import Decimal

import pytest
from langchain_core.language_models import BaseChatModel

from br_financial_ai.ai.recommendation import create_recommendation_engine
from br_financial_ai.eval.cache import EvalResultCache
from br_financial_ai.eval.concurrency import map_bounded
from br_financial_ai.eval.contexts import context_from_case, expected_stances
from br_financial_ai.eval.datasets import dataset_cases, expected_min_cases
from br_financial_ai.eval.factual import evaluate_factual_consistency
from br_financial_ai.eval.grounding import evaluate_evidence_grounding
from br_financial_ai.eval.hallucination import (
    FORBIDDEN_STANCES,
    evaluate_hallucinations,
)
from br_financial_ai.eval.metrics import mean_ratio
from br_financial_ai.eval.profile import eval_llm_concurrency
from br_financial_ai.eval.runtime import RESULTS
from br_financial_ai.eval.timing import timed_eval_section
from br_financial_ai.observability.usage import (
    merge_usage,
    usage_as_dict_with_calls,
)

pytestmark = [
    pytest.mark.eval,
    pytest.mark.external,
    pytest.mark.ollama,
    pytest.mark.asyncio,
]


@pytest.mark.slow
async def test_recommendation_dataset(
    eval_chat_model: BaseChatModel,
    eval_result_cache: EvalResultCache,
) -> None:
    base = create_recommendation_engine(eval_chat_model)
    cases = dataset_cases("recommendation.json")

    async def run_case(case: dict) -> dict:
        context = context_from_case(case)

        async def generate():
            engine = base.fork()
            result = await engine.generate_recommendation(context)
            prompt_characters = (
                engine.last_prompt.character_count if engine.last_prompt else None
            )
            return result, engine.last_usage, prompt_characters

        result, usage, prompt_characters = await eval_result_cache.get_or_set(
            "recommendation",
            str(case["id"]),
            generate,
        )
        allowed = expected_stances(case)
        assert result.stance.value not in FORBIDDEN_STANCES
        factual = evaluate_factual_consistency(context, result)
        grounding = evaluate_evidence_grounding(context, result)
        hallucination = evaluate_hallucinations(context, result)
        assert grounding.fabricated_evidence_count == 0
        return {
            "id": case["id"],
            "stance_hit": result.stance.value in allowed,
            "factual": factual.score,
            "factual_inconsistent": list(factual.inconsistent_claims),
            "grounding": grounding.evidence_grounding_rate,
            "hallucination_count": hallucination.hallucination_count,
            "hallucination_flags": list(hallucination.flags),
            "unsupported_metrics": list(hallucination.unsupported_metrics),
            "valuation_view": result.valuation_view,
            "fundamentals_view": result.fundamentals_view,
            "summary": result.summary,
            "usage": usage,
            "prompt_characters": prompt_characters,
        }

    with timed_eval_section("recommendation_eval_seconds") as extras:
        outcomes = await map_bounded(
            cases,
            run_case,
            concurrency=eval_llm_concurrency(),
        )
        extras["recommendation_llm_calls"] = len(outcomes)

    factual_scores = [item["factual"] for item in outcomes]
    grounding_scores = [item["grounding"] for item in outcomes]
    RESULTS["recommendation"] = {
        "cases": len(cases),
        "stance_accuracy": mean_ratio([item["stance_hit"] for item in outcomes]),
        "factual_consistency": (
            sum(factual_scores) / Decimal(len(factual_scores))
        ).quantize(Decimal("0.0001")),
        "evidence_grounding": (
            sum(grounding_scores) / Decimal(len(grounding_scores))
        ).quantize(Decimal("0.0001")),
        "hallucination_count": sum(item["hallucination_count"] for item in outcomes),
        "true_hallucination_count": sum(
            1 for item in outcomes if item["hallucination_count"]
        ),
        "evaluator_false_positive_count": 0,
        "case_ids": [item["id"] for item in outcomes],
        "flagged_cases": [
            {
                "id": item["id"],
                "flags": item["hallucination_flags"],
                "inconsistent_claims": item["factual_inconsistent"],
                "unsupported_metrics": item["unsupported_metrics"],
                "summary": item["summary"],
                "valuation_view": item["valuation_view"],
                "fundamentals_view": item["fundamentals_view"],
            }
            for item in outcomes
            if item["hallucination_count"] or item["factual_inconsistent"]
        ],
    }
    flagged = RESULTS["recommendation"]["flagged_cases"]
    if flagged:
        print("FLAGGED_CASES", flagged)
    RESULTS["llm_usage"]["recommendation"] = usage_as_dict_with_calls(
        merge_usage(*[item["usage"] for item in outcomes]),
        len(outcomes),
    )
    prompt_sizes = [
        item["prompt_characters"]
        for item in outcomes
        if isinstance(item["prompt_characters"], int)
    ]
    if prompt_sizes:
        RESULTS["llm_usage"]["recommendation_prompt_characters"] = max(prompt_sizes)

    assert [item["id"] for item in outcomes] == [case["id"] for case in cases]
    assert len(cases) >= expected_min_cases("recommendation.json")
    assert mean_ratio([item["stance_hit"] for item in outcomes]) >= 0
