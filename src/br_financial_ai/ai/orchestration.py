from collections.abc import Mapping, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from br_financial_ai.ai.tool_selection import (
    select_quarter_financial_metric_tool,
)


def resolve_tool(
    tools: Sequence[BaseTool],
    name: str,
) -> BaseTool:
    for tool in tools:
        if tool.name == name:
            return tool

    raise ValueError(f"Unsupported tool: {name}")


async def execute_selected_tool(
    tools: Sequence[BaseTool],
    selected: Mapping[str, object],
) -> object:
    name = selected["name"]
    args = selected["args"]

    if not isinstance(name, str):
        raise TypeError("Tool name must be a string.")

    if not isinstance(args, Mapping):
        raise TypeError("Tool arguments must be a mapping.")

    tool = resolve_tool(tools, name)
    return await tool.ainvoke(dict(args))


async def execute_quarter_financial_metric_question(
    model: BaseChatModel,
    tool: BaseTool,
    question: str,
) -> object:
    selected = await select_quarter_financial_metric_tool(
        model,
        tool,
        question,
    )
    return await execute_selected_tool([tool], selected)
