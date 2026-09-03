from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.domain.financial_profile import (
    METRIC_UNSUPPORTED_FOR_PROFILE,
)
from br_financial_ai.services.exceptions import (
    MetricUnsupportedForProfileError,
)
from br_financial_ai.tools.financial import (
    get_quarter_financial_metric,
)

QUARTER_FINANCIAL_METRIC_TOOL_NAME = "get_quarter_financial_metric"


class QuarterFinancialMetricInput(BaseModel):
    ticker: str = Field(description="B3 ticker, for example PETR4.")
    metric: str = Field(
        description=(
            "Canonical metric key. Allowed values depend on the "
            "company financial profile. Non-financial companies: "
            "revenue, gross_profit, operating_result, net_income. "
            "Financial institutions: net_income, "
            "financial_intermediation_revenue, "
            "financial_intermediation_result. "
            "Use gross_profit for lucro bruto, not gross_income. "
            "Use operating_result for resultado operacional, "
            "not operational_result. Do not map industrial revenue "
            "onto bank intermediation accounts."
        )
    )
    year: int = Field(
        description=(
            "Four-digit calendar year, for example 2026. "
            "Compact forms such as 2T26 use year 2026, not 26."
        )
    )
    quarter: int = Field(
        ge=1,
        le=4,
        description=(
            "Calendar quarter from 1 to 4. "
            "2T26, 2T 2026, Q2 2026, and "
            "'segundo trimestre de 2026' all mean quarter 2."
        ),
    )


def create_quarter_financial_metric_tool(
    session: AsyncSession,
) -> StructuredTool:
    async def execute(
        ticker: str,
        metric: str,
        year: int,
        quarter: int,
    ) -> dict[str, object] | None:
        try:
            result = await get_quarter_financial_metric(
                session,
                ticker=ticker,
                metric=metric,
                year=year,
                quarter=quarter,
            )
        except MetricUnsupportedForProfileError as exc:
            return {
                "unsupported": True,
                "reason": METRIC_UNSUPPORTED_FOR_PROFILE,
                "metric": exc.metric_key,
                "financial_profile": exc.financial_profile,
            }

        if result is None:
            return None

        return {
            "ticker": result.ticker,
            "metric": result.metric,
            "year": result.year,
            "quarter": result.quarter,
            "account_code": result.account_code,
            "account_name": result.account_name,
            "value": str(result.value),
            "currency": result.currency,
            "currency_scale": result.currency_scale,
        }

    return StructuredTool.from_function(
        coroutine=execute,
        name=QUARTER_FINANCIAL_METRIC_TOOL_NAME,
        description=(
            "Returns a deterministic quarterly "
            "financial metric for a Brazilian "
            "listed company."
        ),
        args_schema=QuarterFinancialMetricInput,
    )
