from collections.abc import Iterator
from pathlib import Path
from time import perf_counter

import pytest

from br_financial_ai.ai.llm import create_chat_model
from br_financial_ai.eval.cache import EvalResultCache
from br_financial_ai.eval.history import load_json_object
from br_financial_ai.eval.profile import (
    FAST_EVAL_FILES,
    EvalProfile,
    current_eval_profile,
    export_eval_artifacts_enabled,
    fail_on_regression_enabled,
    write_eval_report_enabled,
)
from br_financial_ai.eval.report import (
    is_fast_report_incomplete,
    write_evaluation_summary,
)
from br_financial_ai.eval.runtime import RESULTS
from br_financial_ai.eval.timing import record_eval_seconds


@pytest.fixture(scope="session", autouse=True)
def persist_eval_report() -> Iterator[None]:
    started = perf_counter()
    yield
    if current_eval_profile() is EvalProfile.FAST:
        record_eval_seconds("fast_eval_total_seconds", perf_counter() - started)
        if is_fast_report_incomplete(RESULTS):
            return
    if not write_eval_report_enabled():
        return
    path = write_evaluation_summary(
        RESULTS,
        profile=current_eval_profile(),
        export=export_eval_artifacts_enabled(),
    )
    if not fail_on_regression_enabled():
        return
    payload = load_json_object(path)
    if payload is None or payload.get("status") != "FAIL":
        return
    failed = []
    gates = payload.get("gates")
    if isinstance(gates, dict):
        raw = gates.get("failed")
        if isinstance(raw, list):
            failed = [str(item) for item in raw]
    detail = (
        "; ".join(failed) if failed else "required quality thresholds were violated"
    )
    pytest.fail(f"Quality gates failed: {detail}", pytrace=False)


@pytest.fixture(scope="function")
def eval_chat_model():
    return create_chat_model()


@pytest.fixture(scope="session")
def eval_result_cache() -> EvalResultCache:
    return EvalResultCache()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "eval: external evaluation suite")
    config.addinivalue_line("markers", "slow: slow evaluation")
    config.addinivalue_line(
        "markers",
        "external: requires network or local providers",
    )
    config.addinivalue_line("markers", "ollama: requires local Ollama")
    config.addinivalue_line("markers", "yahoo: requires Yahoo Finance")


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    del config
    if current_eval_profile().value != "fast":
        return
    skip_fast = pytest.mark.skip(reason="excluded from FAST eval profile")
    for item in items:
        path = Path(str(item.fspath)).name
        if path not in FAST_EVAL_FILES:
            item.add_marker(skip_fast)
