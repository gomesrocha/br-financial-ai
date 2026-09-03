from calendar import monthrange
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import (
    Company,
    FinancialStatementItem,
)
from br_financial_ai.domain.financial_metrics import (
    FinancialMetric,
    get_financial_metric,
    is_known_metric_key,
    normalize_metric_key,
)
from br_financial_ai.domain.financial_profile import (
    FinancialProfile,
    financial_profile_from_setor_ativ,
)
from br_financial_ai.repositories.financial_statement_item import (
    FinancialStatementItemRepository,
)
from br_financial_ai.services.company_query import (
    CompanyQueryService,
)
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
    MetricUnsupportedForProfileError,
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


def annual_period(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


class FinancialQueryService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.company_query_service = CompanyQueryService(session)
        self.item_repository = FinancialStatementItemRepository(session)

    async def resolve_financial_profile(
        self,
        ticker: str,
    ) -> FinancialProfile:
        company = await self._require_company(ticker)
        return financial_profile_from_setor_ativ(company.setor_ativ)

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
        period_start, period_end = quarter_period(
            year,
            quarter,
        )

        company = await self._require_company(ticker)

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
        period_start, period_end = quarter_period(
            year,
            quarter,
        )
        company, metric = await self._resolve_metric(ticker, metric_key)

        return await self._select_metric_item(
            company_id=company.id,
            document_type="ITR",
            metric=metric,
            period_start=period_start,
            period_end=period_end,
        )

    async def get_annual_account(
        self,
        *,
        ticker: str,
        year: int,
        account_code: str,
        statement_type: str = "DRE",
        scope: str = "CONSOLIDATED",
    ) -> FinancialStatementItem | None:
        period_start, period_end = annual_period(year)

        company = await self._require_company(ticker)

        return await self.item_repository.get_latest_account_value(
            company_id=company.id,
            document_type="DFP",
            statement_type=statement_type,
            scope=scope,
            account_code=account_code,
            exercise_order="ÚLTIMO",
            period_start=period_start,
            period_end=period_end,
        )

    async def get_annual_metric(
        self,
        ticker: str,
        year: int,
        metric_key: str,
    ) -> FinancialStatementItem | None:
        period_start, period_end = annual_period(year)
        company, metric = await self._resolve_metric(ticker, metric_key)

        return await self._select_metric_item(
            company_id=company.id,
            document_type="DFP",
            metric=metric,
            period_start=period_start,
            period_end=period_end,
        )

    async def _require_company(self, ticker: str) -> Company:
        company = await self.company_query_service.find_by_ticker(ticker)

        if company is None:
            raise CompanyNotFoundError(ticker)

        return company

    async def _resolve_metric(
        self,
        ticker: str,
        metric_key: str,
    ) -> tuple[Company, FinancialMetric]:
        if not is_known_metric_key(metric_key):
            raise ValueError(f"Unknown financial metric: {metric_key}")

        company = await self._require_company(ticker)
        profile = financial_profile_from_setor_ativ(company.setor_ativ)
        metric = get_financial_metric(metric_key, profile)

        if metric is None:
            raise MetricUnsupportedForProfileError(
                normalize_metric_key(metric_key),
                profile.value,
            )

        return company, metric

    async def _select_metric_item(
        self,
        *,
        company_id: int | None,
        document_type: str,
        metric: FinancialMetric,
        period_start: date,
        period_end: date,
    ) -> FinancialStatementItem | None:
        if company_id is None:
            raise RuntimeError("Company ID was not generated.")

        for selector in metric.selectors:
            item = await self.item_repository.get_latest_account_value(
                company_id=company_id,
                document_type=document_type,
                statement_type=selector.statement_type,
                scope=selector.scope,
                account_code=selector.account_code,
                exercise_order="ÚLTIMO",
                period_start=period_start,
                period_end=period_end,
            )

            if item is None:
                continue

            if selector.matches_account_name(item.account_name):
                return item

        return None
