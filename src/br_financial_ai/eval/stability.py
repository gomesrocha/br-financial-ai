from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from br_financial_ai.domain.recommendation import RecommendationStance
from br_financial_ai.eval.metrics import mean_or_none, ratio


@dataclass(frozen=True, slots=True)
class StabilityResult:
    stance_distribution: dict[str, int]
    dominant_stance: str | None
    stance_stability_ratio: Decimal
    confidence_mean: Decimal | None
    confidence_range: Decimal | None
    runs: int


def evaluate_stability(
    stances: list[RecommendationStance],
    confidences: list[Decimal],
) -> StabilityResult:
    counts = Counter(item.value for item in stances)
    dominant = None
    dominant_count = 0

    if counts:
        dominant, dominant_count = counts.most_common(1)[0]

    confidence_range = None
    if confidences:
        confidence_range = max(confidences) - min(confidences)

    return StabilityResult(
        stance_distribution=dict(counts),
        dominant_stance=dominant,
        stance_stability_ratio=ratio(dominant_count, len(stances)),
        confidence_mean=mean_or_none(confidences),
        confidence_range=confidence_range,
        runs=len(stances),
    )
