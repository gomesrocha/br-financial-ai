from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from br_financial_ai.db.models import CompanyOnboardingJob
from br_financial_ai.domain.onboarding import ACTIVE_ONBOARDING_STATUSES


class OnboardingJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        job: CompanyOnboardingJob,
    ) -> CompanyOnboardingJob:
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: int) -> CompanyOnboardingJob | None:
        return await self.session.get(CompanyOnboardingJob, job_id)

    async def get_active_by_ticker(
        self,
        ticker: str,
    ) -> CompanyOnboardingJob | None:
        statement = select(CompanyOnboardingJob).where(
            CompanyOnboardingJob.requested_ticker == ticker.strip().upper(),
            CompanyOnboardingJob.status.in_(ACTIVE_ONBOARDING_STATUSES),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()
