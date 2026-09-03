from enum import StrEnum
from os import getenv


class EvalProfile(StrEnum):
    FAST = "fast"
    FULL = "full"


EVAL_PROFILE_ENV = "EVAL_PROFILE"
EVAL_EXPORT_ENV = "EVAL_EXPORT"
EVAL_FAIL_ON_REGRESSION_ENV = "EVAL_FAIL_ON_REGRESSION"
EVAL_WRITE_REPORT_ENV = "EVAL_WRITE_REPORT"
EVAL_LLM_CONCURRENCY_ENV = "EVAL_LLM_CONCURRENCY"

FAST_EVAL_FILES = frozenset(
    {
        "test_tool_selection_dataset.py",
        "test_news_classification_dataset.py",
        "test_recommendation_dataset.py",
        "test_grounding.py",
    }
)


def parse_eval_profile(value: str | None) -> EvalProfile:
    if value is None or not value.strip():
        return EvalProfile.FULL

    normalized = value.strip().lower()
    if normalized in {"fast", "full"}:
        return EvalProfile(normalized)

    raise ValueError(f"Unknown eval profile: {value}")


def current_eval_profile() -> EvalProfile:
    return parse_eval_profile(getenv(EVAL_PROFILE_ENV))


def export_eval_artifacts_enabled() -> bool:
    value = getenv(EVAL_EXPORT_ENV, "1").strip().lower()
    return value not in {"0", "false", "no"}


def fail_on_regression_enabled() -> bool:
    value = getenv(EVAL_FAIL_ON_REGRESSION_ENV, "").strip().lower()
    return value in {"1", "true", "yes"}


def write_eval_report_enabled() -> bool:
    value = getenv(EVAL_WRITE_REPORT_ENV, "1").strip().lower()
    return value not in {"0", "false", "no"}


def eval_llm_concurrency(default: int = 1) -> int:
    raw = getenv(EVAL_LLM_CONCURRENCY_ENV, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(1, min(8, value))
