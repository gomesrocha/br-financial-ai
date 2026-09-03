import os
from decimal import Decimal

import pytest

from br_financial_ai.ai.recommendation import create_recommendation_engine
from br_financial_ai.eval.contexts import context_from_case
from br_financial_ai.eval.datasets import dataset_cases
from br_financial_ai.eval.runtime import RESULTS
from br_financial_ai.eval.stability import evaluate_stability

pytestmark = [
    pytest.mark.eval,
    pytest.mark.external,
    pytest.mark.ollama,
    pytest.mark.slow,
    pytest.mark.asyncio,
]


async def test_recommendation_stability() -> None:
    runs = int(os.getenv("EVAL_STABILITY_RUNS", "5"))
    case = next(
        item for item in dataset_cases("recommendation.json") if item["id"] == "mixed"
    )
    context = context_from_case(case)
    engine = create_recommendation_engine()
    stances = []
    confidences: list[Decimal] = []

    for _ in range(runs):
        result = await engine.generate_recommendation(context)
        stances.append(result.stance)
        confidences.append(result.confidence)

    stability = evaluate_stability(stances, confidences)
    RESULTS["stability"] = {
        "runs": stability.runs,
        "stance_distribution": stability.stance_distribution,
        "dominant_stance": stability.dominant_stance,
        "stance_stability_ratio": stability.stance_stability_ratio,
        "confidence_mean": stability.confidence_mean,
        "confidence_range": stability.confidence_range,
    }

    assert stability.runs == runs
    assert stability.dominant_stance is not None
