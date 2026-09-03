from fastapi import APIRouter, HTTPException, Response, status

from br_financial_ai.api.dependencies import (
    OnboardingJobSchedulerDep,
    OnboardingServiceDep,
    TrackedCompanyServiceDep,
)
from br_financial_ai.db.models import CompanyOnboardingJob
from br_financial_ai.domain.onboarding import OnboardingStatus, OnboardingStep
from br_financial_ai.schemas.tracked import (
    OnboardCompanyRequest,
    OnboardingJobRead,
    OnboardingWarningRead,
    TrackedCompanyRead,
)
from br_financial_ai.services.company_onboarding import OnboardingSubmitResult
from br_financial_ai.services.exceptions import (
    InvalidTickerError,
    OnboardingJobNotFoundError,
    OnboardingNotRetryableError,
)

router = APIRouter(
    prefix="/api/v1/companies",
    tags=["companies"],
)


@router.get(
    "/tracked",
    response_model=list[TrackedCompanyRead],
)
async def list_tracked_companies(
    service: TrackedCompanyServiceDep,
) -> list[TrackedCompanyRead]:
    records = await service.list_active()
    return [
        TrackedCompanyRead(
            company_id=record.company.id or 0,
            legal_name=record.company.legal_name,
            trade_name=record.company.trade_name,
            ticker=record.security.ticker,
            active=record.tracked.active,
        )
        for record in records
        if record.company.id is not None
    ]


@router.post(
    "/onboard",
    response_model=OnboardingJobRead,
)
async def onboard_company(
    payload: OnboardCompanyRequest,
    service: OnboardingServiceDep,
    scheduler: OnboardingJobSchedulerDep,
    response: Response,
) -> OnboardingJobRead:
    try:
        result = await service.submit(payload.ticker)
    except InvalidTickerError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticker is invalid.",
        ) from exc

    if result.accepted:
        response.status_code = status.HTTP_202_ACCEPTED
        if (
            result.newly_created
            and result.job is not None
            and result.job.id is not None
        ):
            scheduler.schedule(result.job.id)

    return _submit_to_read(result)


@router.get(
    "/onboarding/{job_id}",
    response_model=OnboardingJobRead,
)
async def get_onboarding_job(
    job_id: int,
    service: OnboardingServiceDep,
) -> OnboardingJobRead:
    try:
        job = await service.get_job(job_id)
    except OnboardingJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding job not found.",
        ) from exc

    return _job_to_read(job, already_tracked=False)


@router.post(
    "/onboarding/{job_id}/retry",
    response_model=OnboardingJobRead,
)
async def retry_onboarding_job(
    job_id: int,
    service: OnboardingServiceDep,
    scheduler: OnboardingJobSchedulerDep,
    response: Response,
) -> OnboardingJobRead:
    try:
        result = await service.retry(job_id)
    except OnboardingJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding job not found.",
        ) from exc
    except OnboardingNotRetryableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed onboarding jobs can be retried.",
        ) from exc

    if result.accepted:
        response.status_code = status.HTTP_202_ACCEPTED
        if (
            result.newly_created
            and result.job is not None
            and result.job.id is not None
        ):
            scheduler.schedule(result.job.id)

    return _submit_to_read(result)


def _submit_to_read(result: OnboardingSubmitResult) -> OnboardingJobRead:
    if result.job is not None:
        return _job_to_read(
            result.job,
            already_tracked=result.already_tracked,
        )

    return OnboardingJobRead(
        job_id=None,
        ticker=result.ticker,
        status=OnboardingStatus.READY.value,
        step=OnboardingStep.COMPLETED.value,
        already_tracked=True,
        company_id=result.company_id,
        tracked_company_id=result.tracked_company_id,
        warnings=[],
    )


def _job_to_read(
    job: CompanyOnboardingJob,
    *,
    already_tracked: bool,
) -> OnboardingJobRead:
    warnings = [
        OnboardingWarningRead(code=item["code"], message=item["message"])
        for item in job.warnings
        if "code" in item and "message" in item
    ]
    return OnboardingJobRead(
        job_id=job.id,
        ticker=job.requested_ticker,
        status=job.status,
        step=job.step,
        already_tracked=already_tracked,
        company_id=job.company_id,
        tracked_company_id=job.tracked_company_id,
        error_code=job.error_code,
        error_message=job.error_message,
        warnings=warnings,
    )
