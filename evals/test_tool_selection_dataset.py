from unittest.mock import Mock

import pytest
from langchain_core.language_models import BaseChatModel

from br_financial_ai.ai.tool_selection import (
    select_quarter_financial_metric_tool_with_usage,
)
from br_financial_ai.ai.tools.financial import create_quarter_financial_metric_tool
from br_financial_ai.eval.concurrency import map_bounded
from br_financial_ai.eval.datasets import dataset_cases, expected_min_cases
from br_financial_ai.eval.metrics import tool_selection_scores
from br_financial_ai.eval.profile import eval_llm_concurrency
from br_financial_ai.eval.runtime import RESULTS
from br_financial_ai.eval.timing import timed_eval_section
from br_financial_ai.observability.usage import (
    merge_usage,
    usage_as_dict_with_calls,
)

pytestmark = [
    pytest.mark.eval,
    pytest.mark.external,
    pytest.mark.ollama,
    pytest.mark.asyncio,
]


@pytest.mark.slow
async def test_tool_selection_dataset(eval_chat_model: BaseChatModel) -> None:
    tool = create_quarter_financial_metric_tool(Mock())
    cases = dataset_cases("tool_selection.json")

    async def run_case(case: dict) -> dict:
        expected = case["expected"]
        selected, usage = await select_quarter_financial_metric_tool_with_usage(
            eval_chat_model,
            tool,
            str(case["question"]),
        )
        tool_ok = selected["name"] == expected["name"]
        args_ok = selected["args"] == expected["args"]
        return {
            "id": case["id"],
            "tool_ok": tool_ok,
            "args_ok": args_ok,
            "exact": tool_ok and args_ok,
            "usage": usage,
        }

    with timed_eval_section("tool_selection_eval_seconds") as extras:
        outcomes = await map_bounded(
            cases,
            run_case,
            concurrency=eval_llm_concurrency(),
        )
        extras["tool_selection_llm_calls"] = len(outcomes)

    scores = tool_selection_scores(
        tool_name_matches=[item["tool_ok"] for item in outcomes],
        argument_matches=[item["args_ok"] for item in outcomes],
        exact_matches=[item["exact"] for item in outcomes],
    )
    RESULTS["tool_selection"] = {
        "cases": scores.cases,
        "tool_name_accuracy": scores.tool_name_accuracy,
        "argument_accuracy": scores.argument_accuracy,
        "exact_call_accuracy": scores.exact_call_accuracy,
        "case_ids": [item["id"] for item in outcomes],
    }
    RESULTS["llm_usage"]["tool_selection"] = usage_as_dict_with_calls(
        merge_usage(*[item["usage"] for item in outcomes]),
        len(outcomes),
    )

    assert [item["id"] for item in outcomes] == [case["id"] for case in cases]
    assert scores.cases == len(cases)
    assert len(cases) >= expected_min_cases("tool_selection.json")
    assert scores.exact_call_accuracy >= 0
