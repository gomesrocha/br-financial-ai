from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from br_financial_ai.db.models import Company


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, company: Company) -> Company:
        self.session.add(company)
        await self.session.flush()
        await self.session.refresh(company)

        return company

    async def get_by_id(self, company_id: int) -> Company | None:
        return await self.session.get(Company, company_id)

    async def get_by_cvm_code(self, cvm_code: str) -> Company | None:
        statement = select(Company).where(Company.cvm_code == cvm_code)

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def get_by_cnpj(self, cnpj: str) -> Company | None:
        statement = select(Company).where(Company.cnpj == cnpj)

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()
