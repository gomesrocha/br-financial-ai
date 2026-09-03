from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from br_financial_ai.ai.tools.financial import (
    QuarterFinancialMetricInput,
    create_quarter_financial_metric_tool,
)


def test_quarter_financial_metric_input() -> None:
    data = QuarterFinancialMetricInput(
        ticker="PETR4",
        metric="revenue",
        year=2026,
        quarter=2,
    )

    assert data.ticker == "PETR4"
    assert data.metric == "revenue"
    assert data.year == 2026
    assert data.quarter == 2


def test_quarter_financial_metric_input_rejects_invalid_quarter() -> None:
    with pytest.raises(ValidationError):
        QuarterFinancialMetricInput(
            ticker="PETR4",
            metric="revenue",
            year=2026,
            quarter=5,
        )


def test_quarter_financial_metric_tool_contract() -> None:
    session = Mock()

    tool = create_quarter_financial_metric_tool(session)

    assert tool.name == ("get_quarter_financial_metric")

    schema = tool.args_schema.model_json_schema()

    assert set(schema["properties"]) == {
        "ticker",
        "metric",
        "year",
        "quarter",
    }

    assert schema["properties"]["quarter"]["minimum"] == 1

    assert schema["properties"]["quarter"]["maximum"] == 4
