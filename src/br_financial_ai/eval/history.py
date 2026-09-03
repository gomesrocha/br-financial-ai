import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from br_financial_ai.eval.profile import EvalProfile
from br_financial_ai.eval.run import EvalRun, parse_eval_timestamp
from br_financial_ai.eval.thresholds import (
    INDEX_METRIC_PATHS,
    lookup_metric,
    reported_token_total,
)

HISTORY_DIRNAME = "history"
INDEX_FILENAME = "index.json"


def history_dir(reports_dir: Path) -> Path:
    path = reports_dir / HISTORY_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def unique_history_path(reports_dir: Path, run_id: str) -> Path:
    directory = history_dir(reports_dir)
    candidate = directory / f"{run_id}.json"
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        numbered = directory / f"{run_id}-{index}.json"
        if not numbered.exists():
            return numbered
        index += 1


def load_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def extract_run_dict(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    run = payload.get("run")
    if isinstance(run, Mapping) and isinstance(run.get("id"), str) and run["id"]:
        return dict(run)
    generated = payload.get("generated_at")
    if not isinstance(generated, str) or not generated.strip():
        return None
    try:
        timestamp = parse_eval_timestamp(generated)
    except ValueError:
        return None
    return {
        "id": timestamp.strftime("%Y-%m-%dT%H%M%SZ"),
        "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile": infer_legacy_profile(payload),
        "model_provider": _legacy_model_field(payload, "provider"),
        "model_name": _legacy_model_field(payload, "model"),
        "git_commit": None,
        "git_branch": None,
    }


def _legacy_model_field(payload: Mapping[str, Any], field: str) -> str | None:
    usage = payload.get("llm_usage")
    if not isinstance(usage, Mapping):
        return None
    for operation in (
        "recommendation",
        "news_classification",
        "tool_selection",
        "e2e_recommendation",
    ):
        block = usage.get(operation)
        if not isinstance(block, Mapping):
            continue
        value = block.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def infer_legacy_profile(payload: Mapping[str, Any]) -> str:
    tool_cases = lookup_metric(payload, ("tool_selection", "cases")) or 0
    news_cases = lookup_metric(payload, ("news_classification", "cases")) or 0
    rec_cases = lookup_metric(payload, ("recommendation", "cases")) or 0
    has_stability = isinstance(payload.get("stability"), Mapping) and bool(
        payload.get("stability")
    )
    has_e2e = isinstance(payload.get("e2e"), Mapping) and bool(payload.get("e2e"))
    if (
        tool_cases >= 12
        and news_cases >= 8
        and rec_cases >= 9
        and (has_stability or has_e2e)
    ):
        return EvalProfile.FULL.value
    if tool_cases or news_cases or rec_cases:
        return EvalProfile.FAST.value
    return EvalProfile.FULL.value


def index_summary(payload: Mapping[str, Any]) -> dict[str, float | None]:
    summary = {
        key: lookup_metric(payload, path) for key, path in INDEX_METRIC_PATHS.items()
    }
    summary["input_tokens"] = reported_token_total(payload, "input_tokens")
    summary["output_tokens"] = reported_token_total(payload, "output_tokens")
    summary["total_tokens"] = reported_token_total(payload, "total_tokens")
    return summary


def index_entry(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    run = extract_run_dict(payload)
    if run is None:
        return None
    return {
        **run,
        "status": payload.get("status"),
        "summary": index_summary(payload),
    }


def previous_compatible_run(
    reports_dir: Path,
    *,
    profile: EvalProfile | str,
    current_id: str,
) -> dict[str, Any] | None:
    wanted = (
        profile.value if isinstance(profile, EvalProfile) else profile.strip().lower()
    )
    matches: list[tuple[str, dict[str, Any]]] = []
    for path in history_dir(reports_dir).glob("*.json"):
        if path.name == INDEX_FILENAME:
            continue
        payload = load_json_object(path)
        if payload is None:
            continue
        run = extract_run_dict(payload)
        if run is None or run.get("id") == current_id:
            continue
        if str(run.get("profile") or "").lower() != wanted:
            continue
        matches.append((str(run.get("timestamp") or ""), payload))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def metric_deltas(
    current: Mapping[str, Any],
    previous: Mapping[str, Any],
) -> dict[str, dict[str, float | None]]:
    deltas: dict[str, dict[str, float | None]] = {}
    for key, path in INDEX_METRIC_PATHS.items():
        current_value = lookup_metric(current, path)
        previous_value = lookup_metric(previous, path)
        delta = None
        if current_value is not None and previous_value is not None:
            delta = round(current_value - previous_value, 6)
        deltas[key] = {
            "previous": previous_value,
            "current": current_value,
            "delta": delta,
        }
    for key, field in (
        ("input_tokens", "input_tokens"),
        ("output_tokens", "output_tokens"),
        ("total_tokens", "total_tokens"),
    ):
        current_value = reported_token_total(current, field)
        previous_value = reported_token_total(previous, field)
        delta = None
        if current_value is not None and previous_value is not None:
            delta = round(current_value - previous_value, 6)
        deltas[key] = {
            "previous": previous_value,
            "current": current_value,
            "delta": delta,
        }
    return deltas


def comparison_payload(
    reports_dir: Path,
    current: Mapping[str, Any],
    run: EvalRun,
) -> dict[str, Any] | None:
    previous = previous_compatible_run(
        reports_dir,
        profile=run.profile,
        current_id=run.id,
    )
    if previous is None:
        return None
    previous_run = extract_run_dict(previous)
    if previous_run is None:
        return None
    return {
        "previous_run_id": previous_run["id"],
        "metrics": metric_deltas(current, previous),
    }


def rebuild_history_index(reports_dir: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for path in history_dir(reports_dir).glob("*.json"):
        if path.name == INDEX_FILENAME:
            continue
        payload = load_json_object(path)
        if payload is None:
            continue
        entry = index_entry(payload)
        if entry is None:
            continue
        entries.append(entry)
    entries.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    index = {"runs": entries}
    destination = history_dir(reports_dir) / INDEX_FILENAME
    destination.write_text(
        json.dumps(index, indent=2) + "\n",
        encoding="utf-8",
    )
    return index


def archive_existing_latest(reports_dir: Path) -> Path | None:
    latest = reports_dir / "latest.json"
    if not latest.exists():
        return None
    payload = load_json_object(latest)
    if payload is None:
        return None
    run = extract_run_dict(payload)
    if run is None:
        return None
    destination = history_dir(reports_dir) / f"{run['id']}.json"
    if destination.exists():
        return destination
    archived = dict(payload)
    archived["run"] = run
    archived.setdefault("generated_at", run["timestamp"])
    destination.write_text(
        json.dumps(archived, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return destination
