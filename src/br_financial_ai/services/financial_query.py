from calendar import monthrange
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import (
    FinancialStatementItem,
)
from br_financial_ai.domain.financial_metrics import (
    get_financial_metric,
)
from br_financial_ai.repositories.financial_statement_item import (
    FinancialStatementItemRepository,
)
from br_financial_ai.services.company_query import (
    CompanyQueryService,
)
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
)


def quarter_period(
    year: int,
    quarter: int,
) -> tuple[date, date]:
    if quarter not in {1, 2, 3, 4}:
        raise ValueError("Quarter must be between 1 and 4.")

    start_month = ((quarter - 1) * 3) + 1
    end_month = quarter * 3

    start = date(
        year,
        start_month,
        1,
    )

    end = date(
        year,
        end_month,
        monthrange(year, end_month)[1],
    )

    return start, end


class FinancialQueryService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.company_query_service = CompanyQueryService(session)

        self.item_repository = FinancialStatementItemRepository(session)

    async def get_quarter_account(
        self,
        *,
        ticker: str,
        year: int,
        quarter: int,
        account_code: str,
        statement_type: str = "DRE",
        scope: str = "CONSOLIDATED",
    ) -> FinancialStatementItem | None:
        company = await self.company_query_service.find_by_ticker(ticker)

        if company is None or company.id is None:
            raise CompanyNotFoundError(f"Company for ticker {ticker} not found.")

        period_start, period_end = quarter_period(
            year,
            quarter,
        )

        return await self.item_repository.get_latest_account_value(
            company_id=company.id,
            document_type="ITR",
            statement_type=statement_type,
            scope=scope,
            account_code=account_code,
            exercise_order="ÚLTIMO",
            period_start=period_start,
            period_end=period_end,
        )

    async def get_quarter_metric(
        self,
        *,
        ticker: str,
        year: int,
        quarter: int,
        metric_key: str,
    ) -> FinancialStatementItem | None:
        metric = get_financial_metric(metric_key)

        if metric is None:
            raise ValueError(f"Unknown financial metric: {metric_key}")

        return await self.get_quarter_account(
            ticker=ticker,
            year=year,
            quarter=quarter,
            account_code=metric.account_code,
            statement_type=metric.statement_type,
            scope=metric.scope,
        )
