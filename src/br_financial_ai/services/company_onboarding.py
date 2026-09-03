from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from logging import getLogger
from typing import Protocol

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.clients.b3 import B3_REQUEST_HEADERS, B3Client
from br_financial_ai.clients.b3_instruments import B3InstrumentsClient
from br_financial_ai.clients.cvm import CvmClient
from br_financial_ai.clients.cvm_financial import CvmFinancialClient
from br_financial_ai.clients.yahoo_news import (
    YahooNewsClient,
    YahooNewsProviderError,
)
from br_financial_ai.db.models import CompanyOnboardingJob, Security
from br_financial_ai.db.session import async_session_factory
from br_financial_ai.domain.onboarding import (
    ONBOARDING_NEWS_LIMIT,
    OnboardingStatus,
    OnboardingStep,
    OnboardingWarning,
    OnboardingWarningCode,
    financial_periods_for_onboarding,
    normalize_requested_ticker,
)
from br_financial_ai.domain.ticker_discovery import (
    TickerDiscoveryAmbiguousError,
    TickerDiscoveryNotFoundError,
    TickerDiscoveryUnavailableError,
)
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.onboarding_job import OnboardingJobRepository
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.services.company_sync import CompanySyncService
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
    CvmCompanyNotFoundError,
    InvalidTickerError,
    OnboardingJobNotFoundError,
    OnboardingNotRetryableError,
    PreferredSecurityMismatchError,
    TickerNotFoundError,
)
from br_financial_ai.services.financial_ingestion import (
    FinancialIngestionService,
)
from br_financial_ai.services.news_ingestion import NewsIngestionService
from br_financial_ai.services.security_sync import SecuritySyncService
from br_financial_ai.services.ticker_discovery import (
    B3InstrumentsCvmDiscovery,
    B3ListedCompaniesDiscovery,
    CompositeTickerDiscovery,
    LocalSecurityDiscovery,
    TickerDiscoveryProvider,
)
from br_financial_ai.services.tracked_company import TrackedCompanyService

logger = getLogger(__name__)


class OnboardingJobScheduler(Protocol):
    def schedule(self, job_id: int) -> None: ...


@dataclass(frozen=True, slots=True)
class OnboardingSubmitResult:
    job: CompanyOnboardingJob | None
    ticker: str
    already_tracked: bool
    accepted: bool
    newly_created: bool = False
    company_id: int | None = None
    tracked_company_id: int | None = None


class CompanyOnboardingService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        b3_client: B3Client,
        company_sync_service: CompanySyncService,
        security_sync_service: SecuritySyncService,
        financial_ingestion_service: FinancialIngestionService,
        news_ingestion_service: NewsIngestionService,
        tracked_company_service: TrackedCompanyService,
        ticker_discovery: TickerDiscoveryProvider | None = None,
        as_of: date | None = None,
        news_limit: int = ONBOARDING_NEWS_LIMIT,
    ) -> None:
        self.session = session
        self.b3_client = b3_client
        self.company_sync_service = company_sync_service
        self.security_sync_service = security_sync_service
        self.financial_ingestion_service = financial_ingestion_service
        self.news_ingestion_service = news_ingestion_service
        self.tracked_company_service = tracked_company_service
        self._as_of = as_of
        self.news_limit = news_limit
        self.jobs = OnboardingJobRepository(session)
        self.companies = CompanyRepository(session)
        self.securities = SecurityRepository(session)
        self.ticker_discovery = ticker_discovery or CompositeTickerDiscovery(
            (
                LocalSecurityDiscovery(self.companies, self.securities),
                B3ListedCompaniesDiscovery(b3_client),
            )
        )

    async def get_job(self, job_id: int) -> CompanyOnboardingJob:
        job = await self.jobs.get_by_id(job_id)
        if job is None:
            raise OnboardingJobNotFoundError(str(job_id))
        return job

    async def submit(self, ticker: str) -> OnboardingSubmitResult:
        try:
            normalized = normalize_requested_ticker(ticker)
        except ValueError as exc:
            raise InvalidTickerError("Ticker is invalid.") from exc

        existing_tracked = await self.tracked_company_service.get_by_ticker(
            normalized,
        )
        if existing_tracked is not None and existing_tracked.active:
            return OnboardingSubmitResult(
                job=None,
                ticker=normalized,
                already_tracked=True,
                accepted=False,
                company_id=existing_tracked.company_id,
                tracked_company_id=existing_tracked.id,
            )

        active = await self.jobs.get_active_by_ticker(normalized)
        if active is not None:
            return OnboardingSubmitResult(
                job=active,
                ticker=normalized,
                already_tracked=False,
                accepted=True,
                newly_created=False,
            )

        job = CompanyOnboardingJob(
            requested_ticker=normalized,
            status=OnboardingStatus.PENDING.value,
            step=OnboardingStep.RESOLVING_TICKER.value,
            warnings=[],
        )

        try:
            job = await self.jobs.add(job)
            await self.session.commit()
            await self.session.refresh(job)
        except IntegrityError:
            await self.session.rollback()
            reused = await self.jobs.get_active_by_ticker(normalized)
            if reused is None:
                raise
            return OnboardingSubmitResult(
                job=reused,
                ticker=normalized,
                already_tracked=False,
                accepted=True,
                newly_created=False,
            )

        return OnboardingSubmitResult(
            job=job,
            ticker=normalized,
            already_tracked=False,
            accepted=True,
            newly_created=True,
        )

    async def retry(self, job_id: int) -> OnboardingSubmitResult:
        job = await self.get_job(job_id)
        if job.status != OnboardingStatus.FAILED.value:
            raise OnboardingNotRetryableError(
                "Only failed onboarding jobs can be retried."
            )

        active = await self.jobs.get_active_by_ticker(job.requested_ticker)
        if active is not None:
            return OnboardingSubmitResult(
                job=active,
                ticker=job.requested_ticker,
                already_tracked=False,
                accepted=True,
                newly_created=False,
            )

        job.status = OnboardingStatus.PENDING.value
        job.step = OnboardingStep.RESOLVING_TICKER.value
        job.error_code = None
        job.error_message = None
        job.warnings = []
        job.started_at = None
        job.completed_at = None
        job.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(job)

        return OnboardingSubmitResult(
            job=job,
            ticker=job.requested_ticker,
            already_tracked=False,
            accepted=True,
            newly_created=True,
        )

    async def run_job(self, job_id: int) -> None:
        job = await self.get_job(job_id)
        if job.status not in {
            OnboardingStatus.PENDING.value,
            OnboardingStatus.FAILED.value,
        }:
            return

        job.status = OnboardingStatus.RUNNING.value
        job.started_at = datetime.now(UTC)
        job.error_code = None
        job.error_message = None
        job.updated_at = datetime.now(UTC)
        await self.session.commit()

        warnings: list[OnboardingWarning] = []

        try:
            await self._set_step(job, OnboardingStep.RESOLVING_TICKER)
            discovered = await self.ticker_discovery.discover(job.requested_ticker)

            await self._set_step(job, OnboardingStep.SYNCING_COMPANY)
            company = await self.company_sync_service.sync_by_cvm_code(
                discovered.cvm_code,
            )
            job.company_id = company.id
            await self.session.commit()

            await self._set_step(job, OnboardingStep.SYNCING_SECURITIES)
            if discovered.securities:
                await self.security_sync_service.upsert_discovered(
                    company,
                    discovered.securities,
                )
            try:
                securities = await self.security_sync_service.sync_by_cvm_code(
                    company.cvm_code,
                )
            except httpx.HTTPError:
                if company.id is None:
                    raise
                securities = await self.securities.list_by_company_id(company.id)
            preferred = _security_by_ticker(securities, job.requested_ticker)
            if (
                company.id is None
                or preferred is None
                or preferred.company_id != company.id
            ):
                raise PreferredSecurityMismatchError(
                    "Requested ticker does not belong to the resolved company."
                )

            await self._set_step(job, OnboardingStep.SYNCING_FINANCIALS)
            warnings.extend(
                await self._sync_financials(company.cvm_code),
            )

            await self._set_step(job, OnboardingStep.SYNCING_NEWS)
            warnings.extend(
                await self._sync_news(job.requested_ticker),
            )

            await self._set_step(job, OnboardingStep.TRACKING_COMPANY)
            tracked = await self.tracked_company_service.track_company(
                company_id=company.id,
                preferred_security=preferred,
            )
            job.tracked_company_id = tracked.id
            job.company_id = company.id

            await self._complete(job, warnings)
        except InvalidTickerError:
            await self._fail(
                job,
                "INVALID_TICKER",
                "Ticker is invalid.",
            )
        except TickerDiscoveryUnavailableError:
            logger.warning(
                "Onboarding discovery unavailable job_id=%s ticker=%s",
                job_id,
                job.requested_ticker,
            )
            await self._fail(
                job,
                "DISCOVERY_UNAVAILABLE",
                "Company discovery is unavailable.",
            )
        except TickerDiscoveryAmbiguousError:
            await self._fail(
                job,
                "DISCOVERY_AMBIGUOUS",
                "Ticker matched more than one CVM company.",
            )
        except (TickerDiscoveryNotFoundError, TickerNotFoundError):
            await self._fail(
                job,
                "TICKER_NOT_FOUND",
                "Ticker was not found on B3.",
            )
        except CvmCompanyNotFoundError:
            await self._fail(
                job,
                "COMPANY_NOT_FOUND",
                "Company could not be identified in CVM.",
            )
        except CompanyNotFoundError:
            await self._fail(
                job,
                "COMPANY_NOT_FOUND",
                "Company could not be identified.",
            )
        except PreferredSecurityMismatchError:
            await self._fail(
                job,
                "SECURITY_MISMATCH",
                "Requested ticker does not belong to the resolved company.",
            )
        except httpx.HTTPError:
            logger.exception(
                "Onboarding HTTP error job_id=%s ticker=%s",
                job_id,
                job.requested_ticker,
            )
            await self._fail(
                job,
                "DISCOVERY_UNAVAILABLE",
                "Company discovery is unavailable.",
            )
        except Exception:
            await self._fail(
                job,
                "ONBOARDING_FAILED",
                "Onboarding failed.",
            )

    async def _sync_financials(self, cvm_code: str) -> list[OnboardingWarning]:
        warnings: list[OnboardingWarning] = []
        as_of = self._as_of or datetime.now(UTC).date()

        for period in financial_periods_for_onboarding(as_of):
            try:
                result = await self.financial_ingestion_service.sync(
                    cvm_code=cvm_code,
                    document_type=period.document_type,
                    year=period.year,
                )
            except (httpx.HTTPError, ValueError, CompanyNotFoundError):
                warnings.append(
                    _financial_warning(period.document_type, period.year),
                )
                continue

            if result.files_processed == 0 and result.filings_created == 0:
                warnings.append(
                    _financial_warning(period.document_type, period.year),
                )

        return warnings

    async def _sync_news(self, ticker: str) -> list[OnboardingWarning]:
        try:
            result = await self.news_ingestion_service.sync_company_news(
                ticker,
                limit=self.news_limit,
            )
        except (YahooNewsProviderError, CompanyNotFoundError, ValueError):
            return [
                OnboardingWarning(
                    code=OnboardingWarningCode.NEWS_UNAVAILABLE.value,
                    message="Recent company news could not be imported.",
                )
            ]

        if result.created == 0 and result.fetched == 0:
            return [
                OnboardingWarning(
                    code=OnboardingWarningCode.NEWS_EMPTY.value,
                    message="No recent company news was available.",
                )
            ]

        return []

    async def _set_step(
        self,
        job: CompanyOnboardingJob,
        step: OnboardingStep,
    ) -> None:
        job.step = step.value
        job.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(job)

    async def _complete(
        self,
        job: CompanyOnboardingJob,
        warnings: list[OnboardingWarning],
    ) -> None:
        job.warnings = [item.to_dict() for item in warnings]
        job.step = OnboardingStep.COMPLETED.value
        job.status = (
            OnboardingStatus.READY_WITH_WARNINGS.value
            if warnings
            else OnboardingStatus.READY.value
        )
        job.completed_at = datetime.now(UTC)
        job.updated_at = datetime.now(UTC)
        job.error_code = None
        job.error_message = None
        await self.session.commit()

    async def _fail(
        self,
        job: CompanyOnboardingJob,
        error_code: str,
        error_message: str,
    ) -> None:
        job.status = OnboardingStatus.FAILED.value
        job.error_code = error_code
        job.error_message = error_message
        job.completed_at = datetime.now(UTC)
        job.updated_at = datetime.now(UTC)
        await self.session.commit()


def create_onboarding_service(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    *,
    as_of: date | None = None,
    news_client: YahooNewsClient | None = None,
) -> CompanyOnboardingService:
    b3_client = B3Client(http_client)
    cvm_client = CvmClient(http_client)
    companies = CompanyRepository(session)
    securities = SecurityRepository(session)
    ticker_discovery = CompositeTickerDiscovery(
        (
            LocalSecurityDiscovery(companies, securities),
            B3ListedCompaniesDiscovery(b3_client),
            B3InstrumentsCvmDiscovery(
                B3InstrumentsClient(http_client, as_of=as_of),
                cvm_client,
            ),
        )
    )
    return CompanyOnboardingService(
        session,
        b3_client=b3_client,
        company_sync_service=CompanySyncService(session, cvm_client),
        security_sync_service=SecuritySyncService(session, b3_client),
        financial_ingestion_service=FinancialIngestionService(
            session,
            CvmFinancialClient(http_client),
        ),
        news_ingestion_service=NewsIngestionService(
            session,
            news_client or YahooNewsClient(),
        ),
        tracked_company_service=TrackedCompanyService(session),
        ticker_discovery=ticker_discovery,
        as_of=as_of,
    )


async def execute_onboarding_job(job_id: int) -> None:
    """In-process executor for local/single-instance use.

    Job state is persisted in PostgreSQL, but this coroutine is not
    durable across process crashes. A later worker can call
    ``CompanyOnboardingService.run_job`` with a fresh session.
    """

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=5.0,
            read=180.0,
            write=30.0,
            pool=5.0,
        ),
        follow_redirects=True,
        headers=B3_REQUEST_HEADERS,
    ) as http_client:
        async with async_session_factory() as session:
            service = create_onboarding_service(session, http_client)
            await service.run_job(job_id)


class FastApiOnboardingScheduler:
    def __init__(self, add_task: Callable[..., None]) -> None:
        self._add_task = add_task

    def schedule(self, job_id: int) -> None:
        self._add_task(execute_onboarding_job, job_id)


def _security_by_ticker(
    securities: list[Security],
    ticker: str,
) -> Security | None:
    normalized = ticker.strip().upper()
    for security in securities:
        if security.ticker == normalized:
            return security
    return None


def _financial_warning(document_type: str, year: int) -> OnboardingWarning:
    if document_type == "DFP":
        return OnboardingWarning(
            code=OnboardingWarningCode.DFP_UNAVAILABLE.value,
            message=f"Annual DFP {year} could not be imported.",
        )

    return OnboardingWarning(
        code=OnboardingWarningCode.ITR_UNAVAILABLE.value,
        message=f"Quarterly ITR {year} could not be imported.",
    )
