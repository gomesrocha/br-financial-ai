from types import SimpleNamespace

from br_financial_ai.observability.tracing import tracing_enabled
from br_financial_ai.observability.usage import (
    unwrap_structured_output,
    usage_from_response,
)


def test_usage_from_langchain_metadata() -> None:
    message = SimpleNamespace(
        usage_metadata={
            "input_tokens": 11,
            "output_tokens": 7,
            "total_tokens": 18,
        },
        response_metadata={"model": "llama3.1"},
    )

    usage = usage_from_response(message)

    assert usage.input_tokens == 11
    assert usage.output_tokens == 7
    assert usage.total_tokens == 18
    assert usage.estimated_cost is None
    assert usage.currency is None


def test_missing_usage_is_unavailable() -> None:
    usage = usage_from_response(SimpleNamespace())

    assert usage.input_tokens is None
    assert usage.output_tokens is None
    assert usage.total_tokens is None


def test_usage_as_dict_marks_missing_tokens_unavailable() -> None:
    from br_financial_ai.observability.usage import usage_as_dict

    payload = usage_as_dict(None)

    assert payload["available"] is False
    assert payload["estimated_cost"] is None
    assert payload["currency"] is None


def test_unwrap_structured_output() -> None:
    parsed, raw = unwrap_structured_output(
        {"parsed": {"stance": "NEUTRAL"}, "raw": "raw-message"}
    )

    assert parsed == {"stance": "NEUTRAL"}
    assert raw == "raw-message"


def test_tracing_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)

    assert tracing_enabled() is False
