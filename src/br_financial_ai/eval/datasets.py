import json
from pathlib import Path
from typing import Any

from br_financial_ai.eval.profile import EvalProfile, current_eval_profile

REPO_ROOT = Path(__file__).resolve().parents[3]
DATASETS_DIR = REPO_ROOT / "evals" / "datasets"


def load_json_dataset(name: str) -> dict[str, Any]:
    path = DATASETS_DIR / name

    if not path.exists():
        raise FileNotFoundError(f"Eval dataset not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError(f"Eval dataset must be an object: {path}")

    return payload


def dataset_cases(name: str) -> list[dict[str, Any]]:
    payload = load_json_dataset(name)
    cases = payload.get("cases")

    if not isinstance(cases, list):
        raise ValueError(f"Eval dataset has no cases: {name}")

    typed = [case for case in cases if isinstance(case, dict)]
    if current_eval_profile() is EvalProfile.FAST:
        return [case for case in typed if case.get("fast") is True]
    return typed


def expected_min_cases(name: str) -> int:
    if current_eval_profile() is EvalProfile.FAST:
        minimums = {
            "tool_selection.json": 4,
            "news_classification.json": 3,
            "recommendation.json": 3,
        }
    else:
        minimums = {
            "tool_selection.json": 8,
            "news_classification.json": 8,
            "recommendation.json": 9,
        }
    return minimums[name]
