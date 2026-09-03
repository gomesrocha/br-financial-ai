import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

from br_financial_ai.core.settings import Settings
from br_financial_ai.eval.export import export_eval_artifacts
from br_financial_ai.eval.history import (
    archive_existing_latest,
    comparison_payload,
    extract_run_dict,
    history_dir,
    load_json_object,
    rebuild_history_index,
    unique_history_path,
)
from br_financial_ai.eval.metrics import ToolSelectionScores
from br_financial_ai.eval.profile import EvalProfile, current_eval_profile
from br_financial_ai.eval.run import (
    EvalRun,
    GitMetadataReader,
    build_eval_run,
    parse_eval_timestamp,
)
from br_financial_ai.eval.thresholds import (
    evaluate_quality_gates,
    overall_status,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = REPO_ROOT / "evals" / "reports"


def write_evaluation_summary(
    summary: dict[str, Any],
    path: Path | None = None,
    *,
    reports_dir: Path | None = None,
    profile: EvalProfile | None = None,
    timestamp: datetime | None = None,
    settings: Settings | None = None,
    git_reader: GitMetadataReader | None = None,
    export: bool = True,
    run: EvalRun | None = None,
) -> Path:
    report_started = perf_counter()
    destination_dir = reports_dir or REPORTS_DIR
    destination_dir.mkdir(parents=True, exist_ok=True)
    archive_existing_latest(destination_dir)

    eval_run = run or build_eval_run(
        profile=profile or current_eval_profile(),
        timestamp=timestamp,
        settings=settings,
        git_reader=git_reader,
    )
    history_path = unique_history_path(destination_dir, eval_run.id)
    if history_path.stem != eval_run.id:
        eval_run = EvalRun(
            id=history_path.stem,
            timestamp=eval_run.timestamp,
            profile=eval_run.profile,
            model_provider=eval_run.model_provider,
            model_name=eval_run.model_name,
            git_commit=eval_run.git_commit,
            git_branch=eval_run.git_branch,
        )

    payload = finalize_evaluation_report(
        summary,
        eval_run,
        reports_dir=destination_dir,
    )
    performance = payload.setdefault("eval_performance", {})
    if isinstance(performance, dict):
        performance["report_generation_seconds"] = round(
            perf_counter() - report_started,
            4,
        )
    serialized = json.dumps(payload, indent=2, default=_json_default)
    history_path.write_text(serialized + "\n", encoding="utf-8")

    latest = path or (destination_dir / "latest.json")
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(serialized + "\n", encoding="utf-8")
    latest.with_suffix(".md").write_text(_to_markdown(payload), encoding="utf-8")

    rebuild_history_index(destination_dir)
    if export:
        export_eval_artifacts(destination_dir)
    return latest


def migrate_latest_report(reports_dir: Path | None = None) -> Path | None:
    destination_dir = reports_dir or REPORTS_DIR
    latest = destination_dir / "latest.json"
    payload = load_json_object(latest)
    if payload is None:
        return None
    run_dict = extract_run_dict(payload)
    if run_dict is None:
        return None
    profile_value = str(run_dict.get("profile") or EvalProfile.FULL.value)
    try:
        profile = EvalProfile(profile_value)
    except ValueError:
        profile = EvalProfile.FULL
    eval_run = EvalRun(
        id=str(run_dict["id"]),
        timestamp=parse_eval_timestamp(str(run_dict["timestamp"])),
        profile=profile,
        model_provider=(
            run_dict["model_provider"]
            if isinstance(run_dict.get("model_provider"), str)
            else None
        ),
        model_name=(
            run_dict["model_name"]
            if isinstance(run_dict.get("model_name"), str)
            else None
        ),
        git_commit=(
            run_dict["git_commit"]
            if isinstance(run_dict.get("git_commit"), str)
            else None
        ),
        git_branch=(
            run_dict["git_branch"]
            if isinstance(run_dict.get("git_branch"), str)
            else None
        ),
    )
    original_generated = payload.get("generated_at")
    finalized = finalize_evaluation_report(
        payload,
        eval_run,
        reports_dir=destination_dir,
    )
    if isinstance(original_generated, str) and original_generated.strip():
        finalized["generated_at"] = original_generated
    serialized = json.dumps(finalized, indent=2, default=_json_default) + "\n"
    history_path = history_dir(destination_dir) / f"{eval_run.id}.json"
    if not history_path.exists():
        history_path.write_text(serialized, encoding="utf-8")
    latest.write_text(serialized, encoding="utf-8")
    latest.with_suffix(".md").write_text(_to_markdown(finalized), encoding="utf-8")
    rebuild_history_index(destination_dir)
    return latest


def refresh_report_file(path: Path, reports_dir: Path | None = None) -> Path | None:
    destination_dir = reports_dir or path.parent.parent
    payload = load_json_object(path)
    if payload is None:
        return None
    run_dict = extract_run_dict(payload)
    if run_dict is None:
        return None
    try:
        profile = EvalProfile(str(run_dict.get("profile") or EvalProfile.FULL.value))
    except ValueError:
        profile = EvalProfile.FULL
    eval_run = EvalRun(
        id=str(run_dict["id"]),
        timestamp=parse_eval_timestamp(str(run_dict["timestamp"])),
        profile=profile,
        model_provider=(
            run_dict["model_provider"]
            if isinstance(run_dict.get("model_provider"), str)
            else None
        ),
        model_name=(
            run_dict["model_name"]
            if isinstance(run_dict.get("model_name"), str)
            else None
        ),
        git_commit=(
            run_dict["git_commit"]
            if isinstance(run_dict.get("git_commit"), str)
            else None
        ),
        git_branch=(
            run_dict["git_branch"]
            if isinstance(run_dict.get("git_branch"), str)
            else None
        ),
    )
    original_generated = payload.get("generated_at")
    finalized = finalize_evaluation_report(
        payload,
        eval_run,
        reports_dir=destination_dir,
    )
    if isinstance(original_generated, str) and original_generated.strip():
        finalized["generated_at"] = original_generated
    serialized = json.dumps(finalized, indent=2, default=_json_default) + "\n"
    path.write_text(serialized, encoding="utf-8")
    latest = destination_dir / "latest.json"
    if latest.exists():
        current = load_json_object(latest)
        current_run = extract_run_dict(current) if current else None
        if current_run and current_run.get("id") == eval_run.id:
            latest.write_text(serialized, encoding="utf-8")
            latest.with_suffix(".md").write_text(
                _to_markdown(finalized),
                encoding="utf-8",
            )
    rebuild_history_index(destination_dir)
    return path


def finalize_evaluation_report(
    summary: dict[str, Any],
    run: EvalRun,
    *,
    reports_dir: Path,
) -> dict[str, Any]:
    payload = {key: value for key, value in summary.items() if key != "run"}
    gates = evaluate_quality_gates(payload)
    warnings = list(_collect_warnings(payload, gates))
    failed = [item.message for item in gates if item.measured and not item.passed]
    payload["run"] = run.as_dict()
    payload["generated_at"] = run.as_dict()["timestamp"]
    payload["status"] = overall_status(gates, warnings)
    payload["gates"] = {
        "passed": [item.message for item in gates if item.measured and item.passed],
        "failed": failed,
        "unmeasured": [item.message for item in gates if not item.measured],
    }
    payload["warnings"] = warnings
    payload["comparison"] = comparison_payload(reports_dir, payload, run)
    return payload


def is_fast_report_incomplete(summary: dict[str, Any]) -> bool:
    required = {
        "exact_tool_call_accuracy",
        "news_relevance_accuracy",
        "stance_accuracy",
        "factual_consistency",
        "evidence_grounding",
        "true_hallucination_count",
    }
    outcomes = evaluate_quality_gates(summary)
    return any(not item.measured and item.key in required for item in outcomes)


def empty_evaluation_summary() -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "tool_selection": {
            "cases": 0,
            "tool_name_accuracy": None,
            "argument_accuracy": None,
            "exact_call_accuracy": None,
        },
        "news_classification": {},
        "recommendation": {},
        "stability": {},
        "performance": {},
        "llm_usage": {},
        "e2e": {},
        "eval_performance": {},
    }


def tool_selection_section(scores: ToolSelectionScores) -> dict[str, Any]:
    return {
        "cases": scores.cases,
        "tool_name_accuracy": scores.tool_name_accuracy,
        "argument_accuracy": scores.argument_accuracy,
        "exact_call_accuracy": scores.exact_call_accuracy,
    }


def _collect_warnings(payload: dict[str, Any], gates: list) -> list[str]:
    warnings: list[str] = []
    for item in gates:
        if not item.measured:
            warnings.append(item.message)
    usage = payload.get("llm_usage")
    if isinstance(usage, dict):
        for name, block in usage.items():
            if not isinstance(block, dict):
                continue
            if block.get("available") is False:
                warnings.append(f"{name} token usage unavailable")
    return warnings


def _json_default(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")

    if isinstance(value, datetime):
        return value.isoformat()

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _display(value: object) -> object:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, default=_json_default)

    return _json_default(value) if isinstance(value, Decimal | datetime) else value


def _to_markdown(summary: dict[str, Any]) -> str:
    lines = ["# BR Financial AI evaluation summary", ""]
    run = summary.get("run")
    if isinstance(run, dict):
        lines.append(
            f"Run `{run.get('id')}` ({run.get('profile')}) at `{run.get('timestamp')}`."
        )
        lines.append("")
        lines.append(
            f"Model `{run.get('model_provider')} / {run.get('model_name')}`. "
            f"Status `{summary.get('status')}`."
        )
        lines.append("")
    elif summary.get("generated_at"):
        lines.append(f"Generated at `{summary['generated_at']}`.")
        lines.append("")

    for section, payload in summary.items():
        if section in {"generated_at", "run"} or not isinstance(payload, dict):
            if section in {"status"} and isinstance(payload, str):
                continue
            if section == "warnings" and isinstance(payload, list):
                lines.append("## Warnings")
                lines.append("")
                if not payload:
                    lines.append("None.")
                else:
                    for warning in payload:
                        lines.append(f"- {warning}")
                lines.append("")
            continue

        lines.append(f"## {section.replace('_', ' ').title()}")
        lines.append("")

        if not payload:
            lines.append("No results recorded.")
            lines.append("")
            continue

        for key, value in payload.items():
            lines.append(f"- **{key}**: `{_display(value)}`")

        lines.append("")

    return "\n".join(lines)
