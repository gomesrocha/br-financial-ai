from dataclasses import dataclass

from br_financial_ai.domain.analysis import RecommendationContext
from br_financial_ai.domain.recommendation import (
    RecommendationResult,
    RecommendationStance,
)
from br_financial_ai.eval.factual import (
    evaluate_factual_consistency,
    mentions_unsupported_valuation,
)
from br_financial_ai.eval.grounding import evaluate_evidence_grounding

FORBIDDEN_STANCES = frozenset({"BUY", "SELL", "HOLD", "STRONG_BUY", "STRONG_SELL"})


@dataclass(frozen=True, slots=True)
class HallucinationResult:
    unsupported_evidence_count: int
    unsupported_ticker: bool
    unsupported_metrics: tuple[str, ...]
    unsupported_numbers: tuple[str, ...]
    invalid_stance: bool
    forbidden_stance_language: tuple[str, ...]
    hallucination_count: int
    flags: tuple[str, ...]


def evaluate_hallucinations(
    context: RecommendationContext,
    result: RecommendationResult,
) -> HallucinationResult:
    grounding = evaluate_evidence_grounding(context, result)
    factual = evaluate_factual_consistency(context, result)
    combined_text = "\n".join(
        [
            result.summary,
            result.fundamentals_view,
            result.valuation_view,
            result.market_view,
            result.news_view,
            *result.positives,
            *result.risks,
            result.stance.value,
        ]
    )
    unsupported_metrics = mentions_unsupported_valuation(combined_text)
    invalid_stance = result.stance not in RecommendationStance
    forbidden = tuple(
        token for token in FORBIDDEN_STANCES if token in combined_text.upper().split()
    )
    unsupported_ticker = result.ticker.strip().upper() != context.ticker
    flags: list[str] = []

    if grounding.fabricated_evidence_count:
        flags.append("fabricated_evidence")
    if unsupported_ticker:
        flags.append("unsupported_ticker")
    if unsupported_metrics:
        flags.append("unsupported_metrics")
    if factual.inconsistent_claims:
        flags.append("unsupported_numbers")
    if invalid_stance:
        flags.append("invalid_stance")
    if forbidden:
        flags.append("forbidden_stance_language")

    return HallucinationResult(
        unsupported_evidence_count=grounding.fabricated_evidence_count,
        unsupported_ticker=unsupported_ticker,
        unsupported_metrics=unsupported_metrics,
        unsupported_numbers=factual.inconsistent_claims,
        invalid_stance=invalid_stance,
        forbidden_stance_language=forbidden,
        hallucination_count=len(flags),
        flags=tuple(flags),
    )
