from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class LlmUsage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost: Decimal | None = None
    currency: str | None = None
    model: str | None = None
    provider: str | None = None


def usage_from_response(payload: object) -> LlmUsage:
    message = _raw_message(payload)
    usage_metadata = _mapping(getattr(message, "usage_metadata", None))
    response_metadata = _mapping(getattr(message, "response_metadata", None))
    token_usage = _mapping(response_metadata.get("token_usage"))
    merged = {**token_usage, **usage_metadata}

    input_tokens = _optional_int(
        merged.get("input_tokens"),
        merged.get("prompt_tokens"),
        response_metadata.get("prompt_eval_count"),
    )
    output_tokens = _optional_int(
        merged.get("output_tokens"),
        merged.get("completion_tokens"),
        response_metadata.get("eval_count"),
    )
    computed_total = (
        None
        if input_tokens is None or output_tokens is None
        else input_tokens + output_tokens
    )
    total_tokens = _optional_int(
        merged.get("total_tokens"),
        computed_total,
    )

    return LlmUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model=_optional_text(
            response_metadata.get("model_name"),
            response_metadata.get("model"),
        ),
        provider=_optional_text(response_metadata.get("model_provider")),
    )


def usage_as_dict(usage: LlmUsage | None) -> dict[str, object]:
    if usage is None:
        return {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "estimated_cost": None,
            "currency": None,
            "model": None,
            "provider": None,
            "available": False,
        }

    tokens_available = any(
        value is not None
        for value in (usage.input_tokens, usage.output_tokens, usage.total_tokens)
    )
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "estimated_cost": usage.estimated_cost,
        "currency": usage.currency,
        "model": usage.model,
        "provider": usage.provider,
        "available": tokens_available,
    }


def merge_usage(*usages: LlmUsage | None) -> LlmUsage | None:
    merged: LlmUsage | None = None
    for usage in usages:
        if usage is None:
            continue
        if merged is None:
            merged = usage
            continue
        merged = LlmUsage(
            input_tokens=_add_optional_int(merged.input_tokens, usage.input_tokens),
            output_tokens=_add_optional_int(merged.output_tokens, usage.output_tokens),
            total_tokens=_add_optional_int(merged.total_tokens, usage.total_tokens),
            estimated_cost=None,
            currency=merged.currency or usage.currency,
            model=merged.model or usage.model,
            provider=merged.provider or usage.provider,
        )
    return merged


def usage_as_dict_with_calls(
    usage: LlmUsage | None,
    calls: int,
) -> dict[str, object]:
    payload = usage_as_dict(usage)
    payload["calls"] = calls
    return payload


def unwrap_structured_output(payload: object) -> tuple[object, object | None]:
    if isinstance(payload, dict) and "parsed" in payload:
        parsed = payload.get("parsed")
        raw = payload.get("raw")

        if parsed is None:
            raise ValueError("Structured model returned no parsed output.")

        return parsed, raw

    return payload, payload


def _raw_message(payload: object) -> object:
    if isinstance(payload, dict) and "raw" in payload:
        return payload.get("raw")

    return payload


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value

    return {}


def _optional_int(*values: object) -> int | None:
    for value in values:
        if value is None:
            continue

        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue

    return None


def _optional_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def _add_optional_int(left: int | None, right: int | None) -> int | None:
    if left is None and right is None:
        return None
    return (left or 0) + (right or 0)
