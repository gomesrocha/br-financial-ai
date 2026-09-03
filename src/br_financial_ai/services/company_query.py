from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import Company
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.security import SecurityRepository


class CompanyQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self.company_repository = CompanyRepository(session)
        self.security_repository = SecurityRepository(session)

    async def find_by_ticker(
        self,
        ticker: str,
    ) -> Company | None:
        security = await self.security_repository.get_by_ticker(ticker)

        if security is None:
            return None

        return await self.company_repository.get_by_id(
            security.company_id,
        )
