from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

GateOp = Literal["gte", "eq"]


@dataclass(frozen=True, slots=True)
class QualityThreshold:
    key: str
    path: tuple[str, ...]
    op: GateOp
    limit: float
    label: str


@dataclass(frozen=True, slots=True)
class GateOutcome:
    key: str
    label: str
    passed: bool
    measured: bool
    value: float | None
    limit: float
    message: str


# Headroom below the accepted FULL baseline in evals/reports/latest.json
# (2026-09-02). Materiality 0.875 and sentiment 0.875 are not hard gates.
QUALITY_THRESHOLDS: tuple[QualityThreshold, ...] = (
    QualityThreshold(
        key="exact_tool_call_accuracy",
        path=("tool_selection", "exact_call_accuracy"),
        op="gte",
        limit=0.95,
        label="exact tool-call accuracy",
    ),
    QualityThreshold(
        key="news_relevance_accuracy",
        path=("news_classification", "relevance_accuracy"),
        op="gte",
        limit=0.90,
        label="news relevance accuracy",
    ),
    QualityThreshold(
        key="company_specific_accuracy",
        path=("news_classification", "company_specific_accuracy"),
        op="gte",
        limit=0.90,
        label="company-specific accuracy",
    ),
    QualityThreshold(
        key="stance_accuracy",
        path=("recommendation", "stance_accuracy"),
        op="gte",
        limit=0.80,
        label="stance accuracy",
    ),
    QualityThreshold(
        key="factual_consistency",
        path=("recommendation", "factual_consistency"),
        op="gte",
        limit=0.95,
        label="factual consistency",
    ),
    QualityThreshold(
        key="evidence_grounding",
        path=("recommendation", "evidence_grounding"),
        op="gte",
        limit=1.00,
        label="evidence grounding",
    ),
    QualityThreshold(
        key="true_hallucination_count",
        path=("recommendation", "true_hallucination_count"),
        op="eq",
        limit=0.0,
        label="true hallucinations",
    ),
)

INDEX_METRIC_PATHS: dict[str, tuple[str, ...]] = {
    "tool_name_accuracy": ("tool_selection", "tool_name_accuracy"),
    "argument_accuracy": ("tool_selection", "argument_accuracy"),
    "exact_tool_call_accuracy": ("tool_selection", "exact_call_accuracy"),
    "news_relevance_accuracy": ("news_classification", "relevance_accuracy"),
    "news_materiality_accuracy": ("news_classification", "materiality_accuracy"),
    "company_specific_accuracy": ("news_classification", "company_specific_accuracy"),
    "sentiment_agreement": ("news_classification", "sentiment_agreement"),
    "stance_accuracy": ("recommendation", "stance_accuracy"),
    "factual_consistency": ("recommendation", "factual_consistency"),
    "evidence_grounding": ("recommendation", "evidence_grounding"),
    "true_hallucination_count": ("recommendation", "true_hallucination_count"),
    "news_classification_latency": ("performance", "news_classification_latency"),
    "recommendation_latency": ("performance", "recommendation_latency"),
    "total_analysis_latency_seconds": ("performance", "total_analysis_latency"),
    "tool_selection_input_tokens": ("llm_usage", "tool_selection", "input_tokens"),
    "tool_selection_output_tokens": ("llm_usage", "tool_selection", "output_tokens"),
    "news_classification_input_tokens": (
        "llm_usage",
        "news_classification",
        "input_tokens",
    ),
    "news_classification_output_tokens": (
        "llm_usage",
        "news_classification",
        "output_tokens",
    ),
    "recommendation_input_tokens": ("llm_usage", "recommendation", "input_tokens"),
    "recommendation_output_tokens": ("llm_usage", "recommendation", "output_tokens"),
    "fast_eval_total_seconds": ("eval_performance", "fast_eval_total_seconds"),
    "tool_selection_eval_seconds": (
        "eval_performance",
        "tool_selection_eval_seconds",
    ),
    "news_eval_seconds": ("eval_performance", "news_eval_seconds"),
    "recommendation_eval_seconds": (
        "eval_performance",
        "recommendation_eval_seconds",
    ),
}

USAGE_OPERATIONS = (
    "tool_selection",
    "news_classification",
    "recommendation",
)


def reported_token_total(
    payload: Mapping[str, Any],
    field: str = "total_tokens",
) -> float | None:
    usage = payload.get("llm_usage")
    if not isinstance(usage, Mapping):
        return None
    totals: list[float] = []
    for operation in USAGE_OPERATIONS:
        block = usage.get(operation)
        if not isinstance(block, Mapping):
            continue
        value = coerce_metric_number(block.get(field))
        if value is not None:
            totals.append(value)
    if not totals:
        return None
    return sum(totals)


def lookup_metric(payload: Mapping[str, Any], path: tuple[str, ...]) -> float | None:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return coerce_metric_number(current)


def coerce_metric_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def evaluate_quality_gates(payload: Mapping[str, Any]) -> list[GateOutcome]:
    outcomes: list[GateOutcome] = []
    for spec in QUALITY_THRESHOLDS:
        value = lookup_metric(payload, spec.path)
        if value is None:
            outcomes.append(
                GateOutcome(
                    key=spec.key,
                    label=spec.label,
                    passed=True,
                    measured=False,
                    value=None,
                    limit=spec.limit,
                    message=f"{spec.label} not measured",
                )
            )
            continue
        passed = value >= spec.limit if spec.op == "gte" else value == spec.limit
        comparator = ">=" if spec.op == "gte" else "=="
        outcomes.append(
            GateOutcome(
                key=spec.key,
                label=spec.label,
                passed=passed,
                measured=True,
                value=value,
                limit=spec.limit,
                message=(
                    f"{spec.label} {value} {comparator} {spec.limit}"
                    if passed
                    else f"{spec.label} {value} failed {comparator} {spec.limit}"
                ),
            )
        )
    return outcomes


def overall_status(outcomes: list[GateOutcome], warnings: list[str]) -> str:
    if any(item.measured and not item.passed for item in outcomes):
        return "FAIL"
    if warnings or any(not item.measured for item in outcomes):
        return "PASS_WITH_WARNINGS"
    return "PASS"
