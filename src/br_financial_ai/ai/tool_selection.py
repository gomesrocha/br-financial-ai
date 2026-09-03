from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from br_financial_ai.ai.quarter_text import (
    expand_quarter_expressions,
    normalize_quarter_tool_args,
)
from br_financial_ai.ai.tools.financial import (
    QUARTER_FINANCIAL_METRIC_TOOL_NAME,
    QuarterFinancialMetricInput,
)
from br_financial_ai.observability.tracing import invoke_config
from br_financial_ai.observability.usage import LlmUsage, usage_from_response

last_tool_selection_usage: LlmUsage | None = None


def bind_quarter_financial_metric_tool(
    model: BaseChatModel,
    tool: BaseTool,
) -> Runnable:
    if tool.name != QUARTER_FINANCIAL_METRIC_TOOL_NAME:
        raise ValueError("Only get_quarter_financial_metric can be bound.")

    return model.bind_tools([tool])


def extract_selected_tool_call(
    message: BaseMessage,
) -> dict[str, object]:
    if not isinstance(message, AIMessage):
        raise TypeError("Expected an AIMessage.")

    if len(message.tool_calls) != 1:
        raise ValueError("Expected exactly one tool call.")

    tool_call = message.tool_calls[0]
    name = tool_call["name"]

    if name != QUARTER_FINANCIAL_METRIC_TOOL_NAME:
        raise ValueError(f"Unsupported tool: {name}")

    parsed = QuarterFinancialMetricInput.model_validate(tool_call["args"])
    args = normalize_quarter_tool_args(parsed.model_dump())

    return {
        "name": name,
        "args": args,
    }


async def select_quarter_financial_metric_tool(
    model: BaseChatModel,
    tool: BaseTool,
    question: str,
) -> dict[str, object]:
    selected, _usage = await select_quarter_financial_metric_tool_with_usage(
        model,
        tool,
        question,
    )
    return selected


async def select_quarter_financial_metric_tool_with_usage(
    model: BaseChatModel,
    tool: BaseTool,
    question: str,
) -> tuple[dict[str, object], LlmUsage | None]:
    global last_tool_selection_usage

    bound = bind_quarter_financial_metric_tool(model, tool)
    message = await bound.ainvoke(
        expand_quarter_expressions(question),
        config=invoke_config("financial_tool_selection"),
    )
    last_tool_selection_usage = usage_from_response(message)
    return extract_selected_tool_call(message), last_tool_selection_usage
