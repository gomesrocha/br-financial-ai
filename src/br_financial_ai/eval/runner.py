import json
import os
import subprocess
import sys

from br_financial_ai.eval.export import export_eval_artifacts
from br_financial_ai.eval.profile import (
    EVAL_EXPORT_ENV,
    EVAL_FAIL_ON_REGRESSION_ENV,
    EVAL_PROFILE_ENV,
    EvalProfile,
    parse_eval_profile,
)
from br_financial_ai.eval.report import REPO_ROOT, REPORTS_DIR


def run_eval(
    profile: EvalProfile | str,
    *,
    fail_on_regression: bool = False,
    export: bool = True,
) -> int:
    resolved = (
        profile if isinstance(profile, EvalProfile) else parse_eval_profile(profile)
    )
    env = os.environ.copy()
    env[EVAL_PROFILE_ENV] = resolved.value
    env[EVAL_EXPORT_ENV] = "1" if export else "0"
    if fail_on_regression:
        env[EVAL_FAIL_ON_REGRESSION_ENV] = "1"
    else:
        env.pop(EVAL_FAIL_ON_REGRESSION_ENV, None)

    print(f"Running {resolved.value} evaluation: pytest evals -q", flush=True)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "evals", "-q"],
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        return completed.returncode
    if fail_on_regression and _latest_status_failed():
        print("Quality gates failed.")
        return 1
    return 0


def export_eval_history() -> int:
    destination = export_eval_artifacts(REPORTS_DIR)
    if destination is None:
        print("Frontend public/ directory was not found; nothing exported.")
        return 1
    print(f"Exported evaluation artifacts to {destination}")
    return 0


def _latest_status_failed() -> bool:
    latest = REPORTS_DIR / "latest.json"
    if not latest.exists():
        return False
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and payload.get("status") == "FAIL"
