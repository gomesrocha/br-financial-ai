from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError

from br_financial_ai.ai.tool_selection import (
    bind_quarter_financial_metric_tool,
    extract_selected_tool_call,
    select_quarter_financial_metric_tool,
)
from br_financial_ai.ai.tools.financial import (
    QUARTER_FINANCIAL_METRIC_TOOL_NAME,
    create_quarter_financial_metric_tool,
)


def test_bind_quarter_financial_metric_tool() -> None:
    model = Mock()
    bound = Mock(name="bound_model")
    model.bind_tools.return_value = bound
    tool = create_quarter_financial_metric_tool(Mock())

    result = bind_quarter_financial_metric_tool(model, tool)

    assert result is bound
    model.bind_tools.assert_called_once_with([tool])
    assert tool.name == QUARTER_FINANCIAL_METRIC_TOOL_NAME


def test_bind_rejects_unexpected_tool() -> None:
    model = Mock()
    tool = Mock()
    tool.name = "other_tool"

    with pytest.raises(
        ValueError,
        match="get_quarter_financial_metric",
    ):
        bind_quarter_financial_metric_tool(model, tool)

    model.bind_tools.assert_not_called()


def test_extract_selected_tool_call() -> None:
    message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "get_quarter_financial_metric",
                "args": {
                    "ticker": "PETR4",
                    "metric": "revenue",
                    "year": 2026,
                    "quarter": 2,
                },
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )

    selected = extract_selected_tool_call(message)

    assert selected == {
        "name": "get_quarter_financial_metric",
        "args": {
            "ticker": "PETR4",
            "metric": "revenue",
            "year": 2026,
            "quarter": 2,
        },
    }


def test_extract_coerces_two_digit_years() -> None:
    message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "get_quarter_financial_metric",
                "args": {
                    "ticker": "PETR4",
                    "metric": "revenue",
                    "year": 26,
                    "quarter": 2,
                },
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )

    selected = extract_selected_tool_call(message)

    assert selected["args"]["year"] == 2026
    assert selected["args"]["quarter"] == 2


def test_extract_coerces_numeric_args() -> None:
    message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "get_quarter_financial_metric",
                "args": {
                    "ticker": "PETR4",
                    "metric": "revenue",
                    "year": "2026",
                    "quarter": "2",
                },
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )

    selected = extract_selected_tool_call(message)

    assert selected["args"] == {
        "ticker": "PETR4",
        "metric": "revenue",
        "year": 2026,
        "quarter": 2,
    }


def test_extract_rejects_missing_tool_call() -> None:
    message = AIMessage(content="sem ferramenta")

    with pytest.raises(
        ValueError,
        match="Expected exactly one tool call",
    ):
        extract_selected_tool_call(message)


def test_extract_rejects_multiple_tool_calls() -> None:
    tool_call = {
        "name": "get_quarter_financial_metric",
        "args": {
            "ticker": "PETR4",
            "metric": "revenue",
            "year": 2026,
            "quarter": 2,
        },
        "id": "call_1",
        "type": "tool_call",
    }
    message = AIMessage(
        content="",
        tool_calls=[tool_call, {**tool_call, "id": "call_2"}],
    )

    with pytest.raises(
        ValueError,
        match="Expected exactly one tool call",
    ):
        extract_selected_tool_call(message)


def test_extract_rejects_non_ai_message() -> None:
    with pytest.raises(TypeError, match="AIMessage"):
        extract_selected_tool_call(HumanMessage(content="pergunta"))


def test_extract_rejects_unsupported_tool_name() -> None:
    message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "other_tool",
                "args": {
                    "ticker": "PETR4",
                    "metric": "revenue",
                    "year": 2026,
                    "quarter": 2,
                },
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )

    with pytest.raises(
        ValueError,
        match="Unsupported tool: other_tool",
    ):
        extract_selected_tool_call(message)


def test_extract_rejects_invalid_quarter() -> None:
    message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "get_quarter_financial_metric",
                "args": {
                    "ticker": "PETR4",
                    "metric": "revenue",
                    "year": 2026,
                    "quarter": 5,
                },
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )

    with pytest.raises(ValidationError):
        extract_selected_tool_call(message)


@pytest.mark.asyncio
async def test_select_expands_compact_quarter_before_invoking_model() -> None:
    message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "get_quarter_financial_metric",
                "args": {
                    "ticker": "PETR4",
                    "metric": "revenue",
                    "year": 2026,
                    "quarter": 2,
                },
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )
    bound = AsyncMock()
    bound.ainvoke = AsyncMock(return_value=message)
    model = Mock()
    model.bind_tools.return_value = bound
    tool = create_quarter_financial_metric_tool(Mock())

    selected = await select_quarter_financial_metric_tool(
        model,
        tool,
        "Qual a receita da PETR4 no 2T26?",
    )

    question = bound.ainvoke.await_args.args[0]
    assert "quarter 2 of 2026" in question
    assert selected["args"]["year"] == 2026
    assert selected["args"]["quarter"] == 2
