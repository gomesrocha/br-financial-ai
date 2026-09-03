import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from br_financial_ai.core.settings import Settings
from br_financial_ai.eval.datasets import dataset_cases, expected_min_cases
from br_financial_ai.eval.export import export_eval_artifacts
from br_financial_ai.eval.history import (
    INDEX_FILENAME,
    extract_run_dict,
    load_json_object,
    metric_deltas,
    previous_compatible_run,
    rebuild_history_index,
)
from br_financial_ai.eval.profile import EvalProfile, parse_eval_profile
from br_financial_ai.eval.report import (
    is_fast_report_incomplete,
    migrate_latest_report,
    write_evaluation_summary,
)
from br_financial_ai.eval.run import (
    build_eval_run,
    read_git_metadata,
    run_id_from_timestamp,
)
from br_financial_ai.eval.thresholds import evaluate_quality_gates, overall_status

SETTINGS = Settings(llm_provider="ollama", llm_model="test-model")
TS_FULL = datetime(2026, 9, 2, 17, 46, 58, tzinfo=UTC)
TS_FAST = datetime(2026, 9, 5, 9, 0, 1, tzinfo=UTC)


def _summary(**overrides: object) -> dict:
    payload: dict = {
        "tool_selection": {
            "cases": 5,
            "tool_name_accuracy": 1.0,
            "argument_accuracy": 1.0,
            "exact_call_accuracy": 1.0,
        },
        "news_classification": {
            "cases": 4,
            "relevance_accuracy": 1.0,
            "materiality_accuracy": 0.875,
            "company_specific_accuracy": 1.0,
            "sentiment_agreement": 0.875,
        },
        "recommendation": {
            "cases": 3,
            "stance_accuracy": 0.8889,
            "factual_consistency": 1.0,
            "evidence_grounding": 1.0,
            "true_hallucination_count": 0,
        },
        "performance": {
            "news_classification_latency": 10.2,
            "recommendation_latency": 20.4,
            "total_analysis_latency": 40.8,
        },
        "llm_usage": {
            "tool_selection": {
                "input_tokens": 10,
                "output_tokens": 2,
                "total_tokens": 12,
                "available": True,
                "estimated_cost": None,
                "provider": "ollama",
                "model": "test-model",
            },
            "news_classification": {
                "input_tokens": 20,
                "output_tokens": 4,
                "total_tokens": 24,
                "available": True,
                "estimated_cost": None,
            },
            "recommendation": {
                "input_tokens": 30,
                "output_tokens": 6,
                "total_tokens": 36,
                "available": True,
                "estimated_cost": None,
            },
        },
    }
    payload.update(overrides)
    return payload


def _write(
    tmp_path: Path,
    summary: dict,
    *,
    profile: EvalProfile,
    timestamp: datetime,
    git_reader=lambda: (None, None),
    settings: Settings = SETTINGS,
) -> Path:
    return write_evaluation_summary(
        summary,
        reports_dir=tmp_path,
        profile=profile,
        timestamp=timestamp,
        settings=settings,
        git_reader=git_reader,
        export=False,
    )


def test_run_id_generation_is_filesystem_safe() -> None:
    run_id = run_id_from_timestamp(TS_FULL)
    assert run_id == "2026-09-02T174658Z"
    assert "/" not in run_id
    assert ":" not in run_id


def test_model_comes_from_settings_not_hardcoded_llama() -> None:
    run = build_eval_run(
        profile=EvalProfile.FAST,
        timestamp=TS_FAST,
        settings=Settings(llm_provider="custom", llm_model="study-model"),
        git_reader=lambda: (None, None),
    )
    assert run.model_provider == "custom"
    assert run.model_name == "study-model"
    assert run.model_name != "llama3.1"


def test_git_metadata_absent() -> None:
    run = build_eval_run(
        profile=EvalProfile.FULL,
        timestamp=TS_FULL,
        settings=SETTINGS,
        git_reader=lambda: (None, None),
    )
    assert run.git_commit is None
    assert run.git_branch is None


def test_git_metadata_present_via_reader() -> None:
    run = build_eval_run(
        profile=EvalProfile.FULL,
        timestamp=TS_FULL,
        settings=SETTINGS,
        git_reader=lambda: ("abc123def456", "main"),
    )
    assert run.git_commit == "abc123def456"
    assert run.git_branch == "main"


def test_read_git_metadata_present(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        class Result:
            stdout = "main\n" if "--abbrev-ref" in command else "deadbeefcafebabe\n"

        return Result()

    monkeypatch.setattr("br_financial_ai.eval.run.run", fake_run)
    commit, branch = read_git_metadata()
    assert commit == "deadbeefcafebabe"
    assert branch == "main"


def test_read_git_metadata_absent(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr("br_financial_ai.eval.run.run", fake_run)
    commit, branch = read_git_metadata()
    assert commit is None
    assert branch is None


def test_timestamped_history_and_latest_and_index(tmp_path: Path) -> None:
    latest = _write(
        tmp_path,
        _summary(),
        profile=EvalProfile.FULL,
        timestamp=TS_FULL,
    )
    history = tmp_path / "history" / "2026-09-02T174658Z.json"
    index = tmp_path / "history" / INDEX_FILENAME
    assert latest.exists()
    assert latest.with_suffix(".md").exists()
    assert history.exists()
    assert index.exists()
    payload = load_json_object(history)
    assert payload is not None
    assert payload["run"]["id"] == "2026-09-02T174658Z"
    assert payload["run"]["profile"] == "full"
    assert payload["run"]["model_name"] == "test-model"
    listing = load_json_object(index)
    assert listing is not None
    assert listing["runs"][0]["id"] == "2026-09-02T174658Z"
    assert "tool_selection" not in listing["runs"][0]


def test_immutable_old_run_preservation(tmp_path: Path) -> None:
    _write(tmp_path, _summary(), profile=EvalProfile.FAST, timestamp=TS_FULL)
    first = tmp_path / "history" / "2026-09-02T174658Z.json"
    original = first.read_text(encoding="utf-8")
    first_payload = load_json_object(first)
    assert first_payload is not None
    first_payload["marker"] = "keep-me"
    first.write_text(json.dumps(first_payload, indent=2) + "\n", encoding="utf-8")
    original_marked = first.read_text(encoding="utf-8")
    _write(tmp_path, _summary(), profile=EvalProfile.FAST, timestamp=TS_FAST)
    assert first.read_text(encoding="utf-8") == original_marked
    assert original != original_marked
    latest = load_json_object(tmp_path / "latest.json")
    assert latest is not None
    assert latest["run"]["id"] == "2026-09-05T090001Z"
    index = load_json_object(tmp_path / "history" / INDEX_FILENAME)
    assert index is not None
    assert [item["id"] for item in index["runs"]] == [
        "2026-09-05T090001Z",
        "2026-09-02T174658Z",
    ]


def test_same_timestamp_does_not_overwrite_history(tmp_path: Path) -> None:
    _write(tmp_path, _summary(), profile=EvalProfile.FAST, timestamp=TS_FAST)
    first = tmp_path / "history" / "2026-09-05T090001Z.json"
    payload = load_json_object(first)
    assert payload is not None
    payload["marker"] = True
    first.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    _write(tmp_path, _summary(), profile=EvalProfile.FAST, timestamp=TS_FAST)
    kept = load_json_object(first)
    assert kept is not None
    assert kept["marker"] is True
    second = tmp_path / "history" / "2026-09-05T090001Z-2.json"
    assert second.exists()


def test_fast_versus_full_profile_metadata(tmp_path: Path) -> None:
    _write(tmp_path, _summary(), profile=EvalProfile.FAST, timestamp=TS_FAST)
    _write(tmp_path, _summary(), profile=EvalProfile.FULL, timestamp=TS_FULL)
    fast = load_json_object(tmp_path / "history" / "2026-09-05T090001Z.json")
    full = load_json_object(tmp_path / "history" / "2026-09-02T174658Z.json")
    assert fast is not None and full is not None
    assert fast["run"]["profile"] == "fast"
    assert full["run"]["profile"] == "full"


def test_previous_compatible_run_same_profile_only(tmp_path: Path) -> None:
    _write(tmp_path, _summary(), profile=EvalProfile.FULL, timestamp=TS_FULL)
    _write(tmp_path, _summary(), profile=EvalProfile.FAST, timestamp=TS_FAST)
    previous = previous_compatible_run(
        tmp_path,
        profile=EvalProfile.FAST,
        current_id="new-fast",
    )
    assert previous is not None
    assert previous["run"]["id"] == "2026-09-05T090001Z"
    missing = previous_compatible_run(
        tmp_path,
        profile=EvalProfile.FULL,
        current_id="2026-09-02T174658Z",
    )
    assert missing is None


def test_metric_delta_calculation() -> None:
    current = _summary(
        recommendation={"stance_accuracy": 0.90, "true_hallucination_count": 0}
    )
    previous = _summary()
    deltas = metric_deltas(current, previous)
    assert deltas["stance_accuracy"]["previous"] == 0.8889
    assert deltas["stance_accuracy"]["current"] == 0.90
    assert deltas["stance_accuracy"]["delta"] == 0.0111
    assert deltas["total_tokens"]["current"] == 72.0
    assert deltas["total_tokens"]["previous"] == 72.0
    assert deltas["total_tokens"]["delta"] == 0.0


def test_missing_metric_and_null_tokens_are_not_manufactured() -> None:
    current = {
        "recommendation": {"stance_accuracy": 0.9},
        "llm_usage": {
            "recommendation": {
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "available": False,
            }
        },
    }
    previous = _summary()
    deltas = metric_deltas(current, previous)
    assert deltas["exact_tool_call_accuracy"]["current"] is None
    assert deltas["exact_tool_call_accuracy"]["delta"] is None
    assert deltas["total_tokens"]["current"] is None
    assert deltas["total_tokens"]["delta"] is None


def test_threshold_pass() -> None:
    outcomes = evaluate_quality_gates(_summary())
    assert overall_status(outcomes, []) == "PASS"
    assert all(item.passed for item in outcomes if item.measured)


def test_decimal_metrics_are_measured() -> None:
    payload = {
        "tool_selection": {"exact_call_accuracy": Decimal("1.0000")},
        "news_classification": {
            "relevance_accuracy": Decimal("1.0000"),
            "company_specific_accuracy": Decimal("1.0000"),
        },
        "recommendation": {
            "stance_accuracy": Decimal("0.8889"),
            "factual_consistency": Decimal("1.0000"),
            "evidence_grounding": Decimal("1.0000"),
            "true_hallucination_count": 0,
        },
    }
    outcomes = evaluate_quality_gates(payload)
    assert all(item.measured for item in outcomes)
    assert overall_status(outcomes, []) == "PASS"


def test_write_report_status_pass_with_decimal_metrics(tmp_path: Path) -> None:
    summary = _summary()
    summary["tool_selection"]["exact_call_accuracy"] = Decimal("1.0000")
    summary["recommendation"]["stance_accuracy"] = Decimal("0.8889")
    latest = _write(
        tmp_path,
        summary,
        profile=EvalProfile.FAST,
        timestamp=TS_FAST,
    )
    payload = load_json_object(latest)
    assert payload is not None
    assert payload["status"] == "PASS"
    assert payload["gates"]["unmeasured"] == []


def test_threshold_fail() -> None:
    payload = _summary(
        recommendation={
            "stance_accuracy": 0.5,
            "factual_consistency": 1.0,
            "evidence_grounding": 1.0,
            "true_hallucination_count": 0,
        }
    )
    outcomes = evaluate_quality_gates(payload)
    assert overall_status(outcomes, []) == "FAIL"
    failed = [item for item in outcomes if item.measured and not item.passed]
    assert failed[0].key == "stance_accuracy"


def test_unmeasured_metrics_are_warnings_not_fail() -> None:
    outcomes = evaluate_quality_gates({"tool_selection": {}})
    assert overall_status(outcomes, []) == "PASS_WITH_WARNINGS"
    assert all(not item.measured or item.passed for item in outcomes)
    assert is_fast_report_incomplete({"tool_selection": {}}) is True
    assert is_fast_report_incomplete(_summary()) is False


def test_write_report_records_status_and_comparison(tmp_path: Path) -> None:
    _write(tmp_path, _summary(), profile=EvalProfile.FAST, timestamp=TS_FULL)
    improved = _summary(
        recommendation={
            "cases": 3,
            "stance_accuracy": 0.90,
            "factual_consistency": 1.0,
            "evidence_grounding": 1.0,
            "true_hallucination_count": 0,
        }
    )
    latest = _write(
        tmp_path,
        improved,
        profile=EvalProfile.FAST,
        timestamp=TS_FAST,
    )
    payload = load_json_object(latest)
    assert payload is not None
    assert payload["status"] == "PASS"
    assert payload["comparison"]["previous_run_id"] == "2026-09-02T174658Z"
    assert payload["comparison"]["metrics"]["stance_accuracy"]["delta"] == 0.0111


def test_malformed_historical_report_is_ignored(tmp_path: Path) -> None:
    history = tmp_path / "history"
    history.mkdir()
    (history / "broken.json").write_text("{not-json", encoding="utf-8")
    (history / "array.json").write_text("[]\n", encoding="utf-8")
    (history / "empty.json").write_text("{}\n", encoding="utf-8")
    index = rebuild_history_index(tmp_path)
    assert index == {"runs": []}


def test_migrate_latest_preserves_generated_at(tmp_path: Path) -> None:
    generated = "2026-09-02T17:46:58.809441+00:00"
    (tmp_path / "latest.json").write_text(
        json.dumps(
            {
                "generated_at": generated,
                **_summary(),
                "stability": {"runs": 5},
                "e2e": {"ticker": "PETR4"},
                "tool_selection": {
                    "cases": 12,
                    "exact_call_accuracy": 1.0,
                    "tool_name_accuracy": 1.0,
                    "argument_accuracy": 1.0,
                },
                "news_classification": {
                    "cases": 8,
                    "relevance_accuracy": 1.0,
                    "company_specific_accuracy": 1.0,
                },
                "recommendation": {
                    "cases": 9,
                    "stance_accuracy": 0.8889,
                    "factual_consistency": 1.0,
                    "evidence_grounding": 1.0,
                    "true_hallucination_count": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    migrate_latest_report(tmp_path)
    latest = load_json_object(tmp_path / "latest.json")
    history = load_json_object(tmp_path / "history" / "2026-09-02T174658Z.json")
    assert latest is not None and history is not None
    assert latest["generated_at"] == generated
    assert latest["run"]["id"] == "2026-09-02T174658Z"
    assert latest["run"]["profile"] == "full"
    assert latest["run"]["git_commit"] is None
    assert extract_run_dict(latest)["model_name"] == "test-model"
    assert history["run"]["id"] == latest["run"]["id"]


def test_export_copies_history(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    frontend = tmp_path / "web" / "public"
    frontend.mkdir(parents=True)
    _write(reports, _summary(), profile=EvalProfile.FULL, timestamp=TS_FULL)
    destination = export_eval_artifacts(reports, frontend_public_dir=frontend)
    assert destination == frontend / "evals"
    assert (frontend / "evals" / "latest.json").exists()
    assert (frontend / "evals" / "index.json").exists()
    assert (frontend / "evals" / "history" / "2026-09-02T174658Z.json").exists()
    assert (frontend / "evaluation-summary.json").exists()


def test_parse_eval_profile() -> None:
    assert parse_eval_profile("FAST") is EvalProfile.FAST
    assert parse_eval_profile(None) is EvalProfile.FULL


def test_fast_dataset_subset(monkeypatch) -> None:
    monkeypatch.setenv("EVAL_PROFILE", "fast")
    tool = dataset_cases("tool_selection.json")
    news = dataset_cases("news_classification.json")
    rec = dataset_cases("recommendation.json")
    assert 4 <= len(tool) <= 6
    assert 3 <= len(news) <= 4
    assert len(rec) == 3
    assert all(case.get("fast") is True for case in tool)
    assert expected_min_cases("recommendation.json") == 3
    monkeypatch.setenv("EVAL_PROFILE", "full")
    assert len(dataset_cases("recommendation.json")) >= 9
    assert expected_min_cases("recommendation.json") == 9
