from unittest.mock import Mock

import pytest

from br_financial_ai.ai.llm import create_chat_model
from br_financial_ai.ai.tool_selection import (
    select_quarter_financial_metric_tool,
)
from br_financial_ai.ai.tools.financial import (
    create_quarter_financial_metric_tool,
)

pytestmark = [
    pytest.mark.eval,
    pytest.mark.external,
    pytest.mark.ollama,
]

QUESTION = "Qual foi a receita da PETR4 no segundo trimestre de 2026?"

EXPECTED_TOOL_CALL = {
    "name": "get_quarter_financial_metric",
    "args": {
        "ticker": "PETR4",
        "metric": "revenue",
        "year": 2026,
        "quarter": 2,
    },
}


@pytest.mark.asyncio
async def test_llm_selects_quarter_financial_metric_tool() -> None:
    model = create_chat_model()
    tool = create_quarter_financial_metric_tool(Mock())

    selected = await select_quarter_financial_metric_tool(
        model,
        tool,
        QUESTION,
    )

    assert selected == EXPECTED_TOOL_CALL
