from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from br_financial_ai.db.models import Company, Security, TrackedCompany


@dataclass(frozen=True, slots=True)
class TrackedCompanyRecord:
    tracked: TrackedCompany
    company: Company
    security: Security


class TrackedCompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, tracked: TrackedCompany) -> TrackedCompany:
        self.session.add(tracked)
        await self.session.flush()
        await self.session.refresh(tracked)
        return tracked

    async def get_by_id(self, tracked_id: int) -> TrackedCompany | None:
        return await self.session.get(TrackedCompany, tracked_id)

    async def get_by_company_id(self, company_id: int) -> TrackedCompany | None:
        statement = select(TrackedCompany).where(
            TrackedCompany.company_id == company_id,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_active_records(self) -> list[TrackedCompanyRecord]:
        statement = (
            select(TrackedCompany, Company, Security)
            .join(Company, Company.id == TrackedCompany.company_id)
            .join(Security, Security.id == TrackedCompany.preferred_security_id)
            .where(TrackedCompany.active.is_(True))
            .order_by(Security.ticker)
        )
        result = await self.session.execute(statement)
        return [
            TrackedCompanyRecord(
                tracked=tracked,
                company=company,
                security=security,
            )
            for tracked, company, security in result.all()
        ]
