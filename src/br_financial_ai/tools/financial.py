from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.services.financial_query import (
    FinancialQueryService,
)


@dataclass(frozen=True, slots=True)
class FinancialMetricResult:
    ticker: str
    metric: str
    year: int
    quarter: int
    account_code: str
    account_name: str
    value: Decimal
    currency: str
    currency_scale: str


async def get_quarter_financial_metric(
    session: AsyncSession,
    *,
    ticker: str,
    metric: str,
    year: int,
    quarter: int,
) -> FinancialMetricResult | None:
    service = FinancialQueryService(session)

    item = await service.get_quarter_metric(
        ticker=ticker,
        year=year,
        quarter=quarter,
        metric_key=metric,
    )

    if item is None:
        return None

    return FinancialMetricResult(
        ticker=ticker.strip().upper(),
        metric=metric.strip().lower(),
        year=year,
        quarter=quarter,
        account_code=item.account_code,
        account_name=item.account_name,
        value=item.value,
        currency=item.currency,
        currency_scale=item.currency_scale,
    )
