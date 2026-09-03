from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from br_financial_ai.ai.orchestration import (
    execute_quarter_financial_metric_question,
    execute_selected_tool,
    resolve_tool,
)
from br_financial_ai.ai.tools.financial import (
    QUARTER_FINANCIAL_METRIC_TOOL_NAME,
)

QUESTION = "Qual foi a receita da PETR4 no segundo trimestre de 2026?"

SELECTED_ARGS = {
    "ticker": "PETR4",
    "metric": "revenue",
    "year": 2026,
    "quarter": 2,
}

TOOL_RESULT = {
    "ticker": "PETR4",
    "metric": "revenue",
    "year": 2026,
    "quarter": 2,
    "account_code": "3.01",
    "account_name": "Receita de Venda de Bens e/ou Serviços",
    "value": "169000.0000000000",
    "currency": "REAL",
    "currency_scale": "MIL",
}


def _tool_call_message(
    *,
    name: str = QUARTER_FINANCIAL_METRIC_TOOL_NAME,
    args: dict[str, object] | None = None,
) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": args or SELECTED_ARGS,
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )


def _model_returning(message: AIMessage) -> Mock:
    bound = AsyncMock()
    bound.ainvoke = AsyncMock(return_value=message)
    model = Mock()
    model.bind_tools.return_value = bound
    return model


def _metric_tool() -> Mock:
    tool = Mock()
    tool.name = QUARTER_FINANCIAL_METRIC_TOOL_NAME
    tool.ainvoke = AsyncMock(return_value=TOOL_RESULT)
    return tool


def test_resolve_tool_returns_bound_tool() -> None:
    tool = _metric_tool()

    resolved = resolve_tool([tool], QUARTER_FINANCIAL_METRIC_TOOL_NAME)

    assert resolved is tool


def test_resolve_tool_rejects_unsupported_name() -> None:
    tool = _metric_tool()

    with pytest.raises(
        ValueError,
        match="Unsupported tool: other_tool",
    ):
        resolve_tool([tool], "other_tool")


@pytest.mark.asyncio
async def test_execute_selected_tool_forwards_args() -> None:
    tool = _metric_tool()

    result = await execute_selected_tool(
        [tool],
        {
            "name": QUARTER_FINANCIAL_METRIC_TOOL_NAME,
            "args": SELECTED_ARGS,
        },
    )

    tool.ainvoke.assert_awaited_once_with(SELECTED_ARGS)
    assert result is TOOL_RESULT


@pytest.mark.asyncio
async def test_execute_selected_tool_rejects_unsupported_name() -> None:
    tool = _metric_tool()

    with pytest.raises(
        ValueError,
        match="Unsupported tool: other_tool",
    ):
        await execute_selected_tool(
            [tool],
            {
                "name": "other_tool",
                "args": SELECTED_ARGS,
            },
        )

    tool.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_orchestration_executes_selected_tool() -> None:
    tool = _metric_tool()
    model = _model_returning(_tool_call_message())

    result = await execute_quarter_financial_metric_question(
        model,
        tool,
        QUESTION,
    )

    tool.ainvoke.assert_awaited_once_with(SELECTED_ARGS)
    assert result is TOOL_RESULT


@pytest.mark.asyncio
async def test_orchestration_rejects_missing_tool_call() -> None:
    tool = _metric_tool()
    model = _model_returning(AIMessage(content="sem ferramenta"))

    with pytest.raises(
        ValueError,
        match="Expected exactly one tool call",
    ):
        await execute_quarter_financial_metric_question(
            model,
            tool,
            QUESTION,
        )

    tool.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_orchestration_rejects_unsupported_tool_name() -> None:
    tool = _metric_tool()
    model = _model_returning(
        _tool_call_message(name="other_tool"),
    )

    with pytest.raises(
        ValueError,
        match="Unsupported tool: other_tool",
    ):
        await execute_quarter_financial_metric_question(
            model,
            tool,
            QUESTION,
        )

    tool.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_orchestration_rejects_invalid_arguments() -> None:
    tool = _metric_tool()
    model = _model_returning(
        _tool_call_message(
            args={
                "ticker": "PETR4",
                "metric": "revenue",
                "year": 2026,
                "quarter": 5,
            }
        )
    )

    with pytest.raises(ValidationError):
        await execute_quarter_financial_metric_question(
            model,
            tool,
            QUESTION,
        )

    tool.ainvoke.assert_not_called()
