from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from br_financial_ai.domain.analysis import (
    EvidenceReference,
    RecommendationContext,
    UnavailableSection,
)
from br_financial_ai.domain.financial_profile import (
    METRIC_UNSUPPORTED_FOR_PROFILE,
)

ANALYSIS_DISCLAIMER = (
    "This analysis is informational and is not personalized financial advice."
)

UNSUPPORTED_VALUATION_LIMITATIONS = (
    "P/B not supported",
    "EV/EBITDA not supported",
)


class RecommendationStance(StrEnum):
    FAVORABLE = "FAVORABLE"
    NEUTRAL = "NEUTRAL"
    UNFAVORABLE = "UNFAVORABLE"


@dataclass(frozen=True, slots=True)
class RecommendationResult:
    ticker: str
    stance: RecommendationStance
    confidence: Decimal
    summary: str
    positives: tuple[str, ...]
    risks: tuple[str, ...]
    fundamentals_view: str
    valuation_view: str
    market_view: str
    news_view: str
    limitations: tuple[str, ...]
    evidence: tuple[EvidenceReference, ...]
    as_of: datetime
    disclaimer: str = ANALYSIS_DISCLAIMER


UNSUPPORTED_CONTEXT_METRIC_LABELS = {
    "revenue": "revenue",
    "gross_profit": "gross profit",
    "operating_result": "operating result",
    "net_income": "net income",
    "gross_margin": "gross margin",
    "operating_margin": "operating margin",
    "net_margin": "net margin",
    "price_to_sales": "P/S",
    "price_to_earnings": "P/E",
}


def limitations_from_context(
    context: RecommendationContext,
) -> tuple[str, ...]:
    items: list[str] = []
    valuation = context.valuation
    unsupported_metrics = {
        section.reference
        for section in context.unavailable
        if section.reason == METRIC_UNSUPPORTED_FOR_PROFILE and section.reference
    }

    if "price_to_earnings" in unsupported_metrics:
        items.append("P/E unsupported for this financial profile")
    elif valuation.net_income is not None and valuation.net_income <= 0:
        items.append("P/E unavailable because annual net income is non-positive")
    elif valuation.price_to_earnings is None:
        items.append("P/E unavailable")

    if "price_to_sales" in unsupported_metrics:
        items.append("P/S unsupported for this financial profile")
    elif valuation.price_to_sales is None:
        items.append("P/S unavailable")

    if valuation.market_cap is None:
        items.append("market cap unavailable")

    if not context.recent_news:
        items.append("no recent company news")

    classification_failures = sum(
        1 for section in context.unavailable if section.section == "news_classification"
    )

    if classification_failures == 1:
        items.append("one news classification failed")
    elif classification_failures > 1:
        items.append(f"{classification_failures} news classifications failed")

    for section in context.unavailable:
        limitation = _unavailable_limitation(section)

        if limitation is not None and limitation not in items:
            items.append(limitation)

    for limitation in UNSUPPORTED_VALUATION_LIMITATIONS:
        if limitation not in items:
            items.append(limitation)

    return tuple(items)


def evidence_identity(
    item: EvidenceReference,
) -> tuple[str, str, str]:
    return (item.source, item.kind, item.reference)


def _unavailable_limitation(
    section: UnavailableSection,
) -> str | None:
    if section.section == "market_history":
        reference = section.reference or ""

        if "1y" in reference:
            return "1y market history unavailable"

        if "3mo" in reference:
            return "3mo market history unavailable"

        if "1mo" in reference:
            return "1mo market history unavailable"

        return "market history unavailable"

    if section.section == "market_valuation":
        return "market valuation multiples unavailable"

    if section.section == "news_classification":
        return None

    if section.reason == METRIC_UNSUPPORTED_FOR_PROFILE:
        label = UNSUPPORTED_CONTEXT_METRIC_LABELS.get(
            section.reference or "",
            section.reference or "metric",
        )
        return f"{label} unsupported for this financial profile"

    return f"{section.section} unavailable"
