from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from br_financial_ai.db.models import Security


class SecurityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, security: Security) -> Security:
        self.session.add(security)
        await self.session.flush()
        await self.session.refresh(security)

        return security

    async def get_by_ticker(self, ticker: str) -> Security | None:
        normalized_ticker = ticker.strip().upper()

        statement = select(Security).where(
            Security.ticker == normalized_ticker,
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def get_by_isin(self, isin: str) -> Security | None:
        normalized_isin = isin.strip().upper()

        statement = select(Security).where(
            Security.isin == normalized_isin,
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_company_id(self, company_id: int) -> list[Security]:
        statement = (
            select(Security)
            .where(Security.company_id == company_id)
            .order_by(Security.ticker)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
