from dataclasses import replace
from decimal import Decimal

import pytest

from br_financial_ai.domain.analysis import EvidenceReference
from br_financial_ai.domain.recommendation import (
    RecommendationResult,
    RecommendationStance,
)
from br_financial_ai.eval.contexts import context_from_case
from br_financial_ai.eval.datasets import dataset_cases, load_json_dataset
from br_financial_ai.eval.factual import evaluate_factual_consistency
from br_financial_ai.eval.grounding import evaluate_evidence_grounding
from br_financial_ai.eval.hallucination import evaluate_hallucinations
from br_financial_ai.eval.timing import timed_eval_section

pytestmark = [pytest.mark.eval]


def _result(context) -> RecommendationResult:
    return RecommendationResult(
        ticker=context.ticker,
        stance=RecommendationStance.NEUTRAL,
        confidence=Decimal("0.50"),
        summary="Annual revenue remains disclosed in the CVM filing.",
        positives=("P/S is available.",),
        risks=("Commodity prices can reverse.",),
        fundamentals_view="Fundamentals are mixed.",
        valuation_view="Valuation multiples from the context are usable.",
        market_view="The 1-month return is part of the context.",
        news_view="News evidence is limited.",
        limitations=(),
        evidence=context.evidence,
        as_of=context.as_of,
    )


def test_grounding_and_hallucination_checks() -> None:
    with timed_eval_section("grounding_eval_seconds"):
        spec = load_json_dataset("grounding.json")
        case = dataset_cases("recommendation.json")[0]
        context = context_from_case(case)
        result = _result(context)

        grounding = evaluate_evidence_grounding(context, result)
        factual = evaluate_factual_consistency(context, result)
        hallucination = evaluate_hallucinations(context, result)

        assert grounding.fabricated_evidence_count == 0
        assert grounding.evidence_grounding_rate == Decimal("1")
        assert factual.score == Decimal("1")
        assert hallucination.hallucination_count == 0
        assert "BUY" in spec["forbidden_stances"]
        assert "P/B" in spec["unsupported_metrics"]

        fabricated = EvidenceReference(
            source="Imaginary Wire",
            kind="rumor",
            reference="not-in-context",
        )
        leaked = replace(result, evidence=(*result.evidence, fabricated))
        leaked_grounding = evaluate_evidence_grounding(context, leaked)
        hallucinated = evaluate_hallucinations(
            context,
            replace(
                result,
                valuation_view="P/B = 1.3 and EV/EBITDA = 4.2 look cheap.",
            ),
        )

        assert leaked_grounding.fabricated_evidence_count == 1
        assert leaked_grounding.evidence_grounding_rate < Decimal("1")
        assert "unsupported_metrics" in hallucinated.flags
