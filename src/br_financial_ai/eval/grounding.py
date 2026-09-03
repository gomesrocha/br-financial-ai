from dataclasses import dataclass
from decimal import Decimal

from br_financial_ai.domain.analysis import EvidenceReference, RecommendationContext
from br_financial_ai.domain.recommendation import (
    RecommendationResult,
    evidence_identity,
)
from br_financial_ai.eval.metrics import ratio


@dataclass(frozen=True, slots=True)
class EvidenceGroundingResult:
    evidence_grounding_rate: Decimal
    fabricated_evidence_count: int
    fabricated_evidence: tuple[EvidenceReference, ...]
    unsupported_sources: tuple[str, ...]


def evaluate_evidence_grounding(
    context: RecommendationContext,
    result: RecommendationResult,
) -> EvidenceGroundingResult:
    allowed = {evidence_identity(item) for item in context.evidence}
    allowed_sources = {item.source for item in context.evidence}
    fabricated = tuple(
        item for item in result.evidence if evidence_identity(item) not in allowed
    )
    unsupported_sources = tuple(
        sorted(
            {
                item.source
                for item in result.evidence
                if item.source not in allowed_sources
            }
        )
    )
    grounded = len(result.evidence) - len(fabricated)

    return EvidenceGroundingResult(
        evidence_grounding_rate=ratio(grounded, len(result.evidence)),
        fabricated_evidence_count=len(fabricated),
        fabricated_evidence=fabricated,
        unsupported_sources=unsupported_sources,
    )
