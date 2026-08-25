from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import (
    FinancialFiling,
    FinancialStatementItem,
)


class FinancialStatementItemRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def add_all(
        self,
        items: list[FinancialStatementItem],
    ) -> list[FinancialStatementItem]:
        self.session.add_all(items)

        await self.session.flush()

        return items

    async def list_by_filing_id(
        self,
        filing_id: int,
    ) -> list[FinancialStatementItem]:
        statement = (
            select(FinancialStatementItem)
            .where(FinancialStatementItem.filing_id == filing_id)
            .order_by(
                FinancialStatementItem.statement_type,
                FinancialStatementItem.account_code,
            )
        )

        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def get_latest_account_value(
        self,
        *,
        company_id: int,
        document_type: str,
        statement_type: str,
        scope: str,
        account_code: str,
        exercise_order: str,
        period_start: date | None,
        period_end: date,
    ) -> FinancialStatementItem | None:
        statement = (
            select(FinancialStatementItem)
            .join(
                FinancialFiling,
                FinancialStatementItem.filing_id == FinancialFiling.id,
            )
            .where(
                FinancialFiling.company_id == company_id,
                FinancialFiling.document_type == document_type.strip().upper(),
                FinancialStatementItem.statement_type == statement_type.strip().upper(),
                FinancialStatementItem.scope == scope.strip().upper(),
                FinancialStatementItem.account_code == account_code.strip(),
                FinancialStatementItem.exercise_order == exercise_order.strip().upper(),
                FinancialStatementItem.period_start == period_start,
                FinancialStatementItem.period_end == period_end,
            )
            .order_by(
                FinancialFiling.reference_date.desc(),
                FinancialFiling.version.desc(),
            )
            .limit(1)
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()
