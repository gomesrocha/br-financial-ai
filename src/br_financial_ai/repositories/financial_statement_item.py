from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import (
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
