import asyncio

import pytest

from br_financial_ai.eval.cache import EvalResultCache
from br_financial_ai.eval.concurrency import map_bounded
from br_financial_ai.eval.profile import eval_llm_concurrency
from br_financial_ai.eval.runtime import RESULTS
from br_financial_ai.eval.timing import record_eval_seconds, timed_eval_section
from br_financial_ai.observability.usage import (
    LlmUsage,
    merge_usage,
    usage_as_dict_with_calls,
)


@pytest.mark.asyncio
async def test_map_bounded_preserves_input_order() -> None:
    async def worker(item: int) -> int:
        await asyncio.sleep(0.02 if item == 1 else 0)
        return item * 10

    assert await map_bounded([1, 2, 3], worker, concurrency=2) == [10, 20, 30]


@pytest.mark.asyncio
async def test_map_bounded_respects_concurrency_limit() -> None:
    current = 0
    peak = 0

    async def worker(item: int) -> int:
        nonlocal current, peak
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(0.03)
        current -= 1
        return item

    await map_bounded(list(range(6)), worker, concurrency=2)
    assert peak <= 2
    assert peak >= 1


@pytest.mark.asyncio
async def test_map_bounded_identifies_failed_fixture() -> None:
    async def worker(case: dict) -> str:
        if case["id"] == "broken":
            raise ValueError("nope")
        return str(case["id"])

    with pytest.raises(ExceptionGroup) as captured:
        await map_bounded(
            [{"id": "ok"}, {"id": "broken"}],
            worker,
            concurrency=2,
        )

    assert "broken" in repr(captured.value)


@pytest.mark.asyncio
async def test_eval_result_cache_reuses_factory() -> None:
    cache = EvalResultCache()
    calls = 0

    async def factory() -> str:
        nonlocal calls
        calls += 1
        return "result"

    first = await cache.get_or_set("recommendation", "strong_favorable", factory)
    second = await cache.get_or_set("recommendation", "strong_favorable", factory)
    other = await cache.get_or_set("recommendation", "mixed", factory)

    assert first == second == "result"
    assert other == "result"
    assert calls == 2
    assert len(cache) == 2


def test_eval_llm_concurrency_is_bounded(monkeypatch) -> None:
    monkeypatch.delenv("EVAL_LLM_CONCURRENCY", raising=False)
    assert eval_llm_concurrency() == 1
    monkeypatch.setenv("EVAL_LLM_CONCURRENCY", "3")
    assert eval_llm_concurrency() == 3
    monkeypatch.setenv("EVAL_LLM_CONCURRENCY", "99")
    assert eval_llm_concurrency() == 8
    monkeypatch.setenv("EVAL_LLM_CONCURRENCY", "0")
    assert eval_llm_concurrency() == 1
    monkeypatch.setenv("EVAL_LLM_CONCURRENCY", "nope")
    assert eval_llm_concurrency() == 1


def test_timed_eval_section_records_seconds() -> None:
    previous = RESULTS.get("eval_performance")
    RESULTS["eval_performance"] = {}
    try:
        with timed_eval_section("tool_selection_eval_seconds") as extras:
            extras["tool_selection_llm_calls"] = 5
        block = RESULTS["eval_performance"]
        assert block["tool_selection_eval_seconds"] >= 0
        assert block["tool_selection_llm_calls"] == 5
        record_eval_seconds("fast_eval_total_seconds", 12.3456)
        assert RESULTS["eval_performance"]["fast_eval_total_seconds"] == 12.3456
    finally:
        if previous is None:
            RESULTS.pop("eval_performance", None)
        else:
            RESULTS["eval_performance"] = previous


def test_merge_usage_sums_tokens_and_keeps_nulls() -> None:
    first = LlmUsage(input_tokens=10, output_tokens=2, total_tokens=12, model="m")
    second = LlmUsage(
        input_tokens=5,
        output_tokens=3,
        total_tokens=8,
        provider="ollama",
    )
    merged = merge_usage(first, second, None)
    assert merged is not None
    assert merged.input_tokens == 15
    assert merged.output_tokens == 5
    assert merged.total_tokens == 20
    payload = usage_as_dict_with_calls(merged, 2)
    assert payload["calls"] == 2
    assert merge_usage(None, None) is None
    missing = merge_usage(
        LlmUsage(input_tokens=None, output_tokens=None, total_tokens=None),
        LlmUsage(input_tokens=4, output_tokens=None, total_tokens=None),
    )
    assert missing is not None
    assert missing.input_tokens == 4
    assert missing.output_tokens is None
