from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import Security, TrackedCompany
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.repositories.tracked_company import (
    TrackedCompanyRecord,
    TrackedCompanyRepository,
)
from br_financial_ai.services.exceptions import (
    PreferredSecurityMismatchError,
)


class TrackedCompanyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tracked_repository = TrackedCompanyRepository(session)
        self.security_repository = SecurityRepository(session)

    async def list_active(self) -> list[TrackedCompanyRecord]:
        return await self.tracked_repository.list_active_records()

    async def get_by_company_id(
        self,
        company_id: int,
    ) -> TrackedCompany | None:
        return await self.tracked_repository.get_by_company_id(company_id)

    async def get_by_ticker(self, ticker: str) -> TrackedCompany | None:
        security = await self.security_repository.get_by_ticker(ticker)
        if security is None:
            return None

        return await self.tracked_repository.get_by_company_id(
            security.company_id,
        )

    async def track_company(
        self,
        *,
        company_id: int,
        preferred_security: Security,
    ) -> TrackedCompany:
        if preferred_security.company_id != company_id:
            raise PreferredSecurityMismatchError(
                "Preferred security does not belong to the company."
            )

        if preferred_security.id is None:
            raise PreferredSecurityMismatchError(
                "Preferred security is missing an identifier."
            )

        existing = await self.tracked_repository.get_by_company_id(company_id)
        if existing is not None:
            return existing

        tracked = await self.tracked_repository.add(
            TrackedCompany(
                company_id=company_id,
                preferred_security_id=preferred_security.id,
                active=True,
            )
        )
        await self.session.commit()
        await self.session.refresh(tracked)
        return tracked
