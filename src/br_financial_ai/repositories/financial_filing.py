from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import FinancialFiling


class FinancialFilingRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def add(
        self,
        filing: FinancialFiling,
    ) -> FinancialFiling:
        self.session.add(filing)

        await self.session.flush()
        await self.session.refresh(filing)

        return filing

    async def get_by_identity(
        self,
        *,
        company_id: int,
        document_type: str,
        reference_date: date,
        version: int,
    ) -> FinancialFiling | None:
        statement = select(FinancialFiling).where(
            FinancialFiling.company_id == company_id,
            FinancialFiling.document_type == document_type.strip().upper(),
            FinancialFiling.reference_date == reference_date,
            FinancialFiling.version == version,
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()
