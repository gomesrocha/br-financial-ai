from dataclasses import replace
from decimal import Decimal

from br_financial_ai.domain.analysis import EvidenceReference
from br_financial_ai.domain.recommendation import (
    RecommendationResult,
    RecommendationStance,
)
from br_financial_ai.eval.contexts import context_from_case
from br_financial_ai.eval.datasets import dataset_cases
from br_financial_ai.eval.factual import evaluate_factual_consistency
from br_financial_ai.eval.grounding import evaluate_evidence_grounding
from br_financial_ai.eval.hallucination import evaluate_hallucinations
from br_financial_ai.eval.metrics import tool_selection_scores
from br_financial_ai.eval.stability import evaluate_stability


def _result(context) -> RecommendationResult:
    return RecommendationResult(
        ticker=context.ticker,
        stance=RecommendationStance.FAVORABLE,
        confidence=Decimal("0.78"),
        summary="Revenue of 490829000000 remains constructive.",
        positives=("P/E 5.0x is usable.",),
        risks=("Commodity prices can reverse.",),
        fundamentals_view="Net income is 80000000000.",
        valuation_view="P/S 0.81 is available.",
        market_view="The 1-month return is 0.12.",
        news_view="Recent news is constructive.",
        limitations=(),
        evidence=context.evidence,
        as_of=context.as_of,
    )


def test_tool_selection_scores_require_exact_args() -> None:
    scores = tool_selection_scores(
        tool_name_matches=[True, True],
        argument_matches=[True, False],
        exact_matches=[True, False],
    )

    assert scores.tool_name_accuracy == Decimal("1.0000")
    assert scores.argument_accuracy == Decimal("0.5000")
    assert scores.exact_call_accuracy == Decimal("0.5000")


def test_factual_consistency_accepts_context_numbers() -> None:
    context = context_from_case(dataset_cases("recommendation.json")[0])
    result = evaluate_factual_consistency(context, _result(context))

    assert result.checked_claims >= 1
    assert result.inconsistent_claims == ()
    assert result.score == Decimal("1")


def test_factual_consistency_accepts_equivalent_display_formats() -> None:
    context = context_from_case(dataset_cases("recommendation.json")[0])
    metric = context.market_metrics[0]
    context = replace(
        context,
        market_quote=replace(
            context.market_quote,
            price=Decimal("46.869998931884766"),
        ),
        market_metrics=(replace(metric, period_return=Decimal("0.1229")),),
    )
    result = replace(
        _result(context),
        market_view="The 1-month return is 12.29% and also 12,29%. Price is R$ 46,87.",
        summary="Yahoo last is 46.869998931884766, displayed as 46.87.",
        positives=("Return of 12% is consistent with the 1-month metric.",),
    )

    factual = evaluate_factual_consistency(context, result)

    assert factual.inconsistent_claims == ()
    assert factual.score == Decimal("1")


def test_factual_consistency_ignores_iso_and_calendar_dates() -> None:
    context = context_from_case(dataset_cases("recommendation.json")[0])
    published = context.recent_news[0].published_at.isoformat()
    result = replace(
        _result(context),
        news_view=(
            f"Article timestamp {published} "
            "and 15 August 2026 remain constructive. "
            "Portuguese date 15 de agosto de 2026."
        ),
        summary=f"As of {context.as_of.isoformat()} revenue is 490829000000.",
    )

    factual = evaluate_factual_consistency(context, result)
    hallucination = evaluate_hallucinations(context, result)

    assert factual.inconsistent_claims == ()
    assert factual.score == Decimal("1")
    assert hallucination.hallucination_count == 0


def test_dropped_billion_digit_is_an_ungrounded_numeric_claim() -> None:
    context = context_from_case(
        next(
            case
            for case in dataset_cases("recommendation.json")
            if case["id"] == "conflicting_market_vs_fundamentals"
        )
    )
    result = replace(
        _result(context),
        fundamentals_view=(
            "Revenue is BRL 490,829 million, with a net income of BRL 8 billion."
        ),
    )

    factual = evaluate_factual_consistency(context, result)
    hallucination = evaluate_hallucinations(context, result)

    assert "8" in factual.inconsistent_claims
    assert "unsupported_numbers" in hallucination.flags


def test_factual_consistency_rejects_unrelated_numbers() -> None:
    context = context_from_case(dataset_cases("recommendation.json")[0])
    result = replace(
        _result(context),
        valuation_view="An invented multiple of 17.4 is cheap.",
    )

    factual = evaluate_factual_consistency(context, result)

    assert factual.inconsistent_claims
    assert factual.score < Decimal("1")


def test_evidence_grounding_flags_fabricated_items() -> None:
    context = context_from_case(dataset_cases("recommendation.json")[0])
    result = _result(context)
    leaked = replace(
        result,
        evidence=(
            *result.evidence,
            EvidenceReference(source="Made Up", kind="note", reference="x"),
        ),
    )

    clean = evaluate_evidence_grounding(context, result)
    dirty = evaluate_evidence_grounding(context, leaked)

    assert clean.fabricated_evidence_count == 0
    assert dirty.fabricated_evidence_count == 1
    assert dirty.unsupported_sources == ("Made Up",)


def test_hallucination_flags_unsupported_valuation_metrics() -> None:
    context = context_from_case(dataset_cases("recommendation.json")[0])
    result = replace(
        _result(context),
        valuation_view="P/B = 1.3 and EV/EBITDA = 4.2 look cheap.",
    )
    hallucination = evaluate_hallucinations(context, result)

    assert "unsupported_metrics" in hallucination.flags
    assert hallucination.hallucination_count >= 1


def test_unavailable_metric_mentions_are_not_hallucinations() -> None:
    context = context_from_case(dataset_cases("recommendation.json")[0])
    result = replace(
        _result(context),
        valuation_view="P/B is not supported and EV/EBITDA is unavailable.",
    )
    hallucination = evaluate_hallucinations(context, result)

    assert "unsupported_metrics" not in hallucination.flags


def test_lack_of_support_for_unlisted_multiples_is_not_a_hallucination() -> None:
    context = context_from_case(dataset_cases("recommendation.json")[0])
    result = replace(
        _result(context),
        valuation_view=(
            "The price-to-sales and price-to-earnings ratios suggest that "
            "Petrobras is reasonably valued, but this view is limited by "
            "the lack of support for other valuation metrics such as P/B "
            "and EV/EBITDA."
        ),
    )
    hallucination = evaluate_hallucinations(context, result)

    assert "unsupported_metrics" not in hallucination.flags
    assert evaluate_factual_consistency(context, result).inconsistent_claims == ()


def test_stability_ratio() -> None:
    result = evaluate_stability(
        [
            RecommendationStance.FAVORABLE,
            RecommendationStance.FAVORABLE,
            RecommendationStance.FAVORABLE,
            RecommendationStance.FAVORABLE,
            RecommendationStance.NEUTRAL,
        ],
        [
            Decimal("0.70"),
            Decimal("0.72"),
            Decimal("0.74"),
            Decimal("0.71"),
            Decimal("0.60"),
        ],
    )

    assert result.dominant_stance == "FAVORABLE"
    assert result.stance_stability_ratio == Decimal("0.8000")
    assert result.confidence_range == Decimal("0.14")
