from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from br_financial_ai.eval.runtime import RESULTS


def record_eval_seconds(name: str, seconds: float, **extra: Any) -> None:
    block = RESULTS.setdefault("eval_performance", {})
    if not isinstance(block, dict):
        block = {}
        RESULTS["eval_performance"] = block
    block[name] = round(seconds, 4)
    for key, value in extra.items():
        block[key] = value


@contextmanager
def timed_eval_section(name: str, **extra: Any) -> Iterator[dict[str, Any]]:
    started = perf_counter()
    extras: dict[str, Any] = dict(extra)
    yield extras
    record_eval_seconds(name, perf_counter() - started, **extras)
