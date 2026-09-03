from datetime import date
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.clients.b3 import B3TickerIssuer
from br_financial_ai.db.models import Company, Security
from br_financial_ai.domain.onboarding import OnboardingStatus, OnboardingStep
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.services.company_onboarding import CompanyOnboardingService
from br_financial_ai.services.financial_ingestion import FinancialIngestionResult
from br_financial_ai.services.news_ingestion import NewsIngestionResult
from br_financial_ai.services.tracked_company import TrackedCompanyService


async def _seed_itau_company(session: AsyncSession) -> Company:
    company = await CompanyRepository(session).add(
        Company(
            cvm_code="19999",
            cnpj="60999999000199",
            legal_name="EMPRESA ONBOARD S.A.",
            trade_name="ONBOARD CO",
        )
    )
    await session.flush()
    assert company.id is not None
    return company


async def _seed_itau(session: AsyncSession) -> tuple[Company, Security, Security]:
    company = await _seed_itau_company(session)
    repository = SecurityRepository(session)
    on = await repository.add(
        Security(
            company_id=company.id or 0,
            ticker="ONBD3",
            isin="BRONBDACNOR4",
            security_type="ON",
        )
    )
    pn = await repository.add(
        Security(
            company_id=company.id or 0,
            ticker="ONBD4",
            isin="BRONBDACNPR1",
            security_type="PN",
        )
    )
    await session.flush()
    return company, on, pn


def _ingestion_result(document_type: str, year: int) -> FinancialIngestionResult:
    return FinancialIngestionResult(
        cvm_code="19999",
        document_type=document_type,
        year=year,
        files_processed=1,
        filings_created=1,
        filings_skipped=0,
        items_created=10,
        items_skipped=0,
    )


def _build_service(
    session: AsyncSession,
    *,
    b3_client: object,
    company: Company | None = None,
    securities: list[Security] | None = None,
    news_classifier: object | None = None,
    recommendation_engine: object | None = None,
) -> tuple[CompanyOnboardingService, AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    company_sync = AsyncMock()
    security_sync = AsyncMock()
    financial_sync = AsyncMock()
    news_sync = AsyncMock()

    if company is not None:
        company_sync.sync_by_cvm_code = AsyncMock(return_value=company)
    if securities is not None:
        security_sync.sync_by_cvm_code = AsyncMock(return_value=securities)

    financial_sync.sync = AsyncMock(
        side_effect=lambda **kwargs: _ingestion_result(
            kwargs["document_type"],
            kwargs["year"],
        )
    )
    news_sync.sync_company_news = AsyncMock(
        return_value=NewsIngestionResult(
            ticker="ONBD4",
            company_id=company.id if company and company.id else 1,
            fetched=3,
            created=3,
            skipped=0,
        )
    )

    service = CompanyOnboardingService(
        session,
        b3_client=b3_client,
        company_sync_service=company_sync,
        security_sync_service=security_sync,
        financial_ingestion_service=financial_sync,
        news_ingestion_service=news_sync,
        tracked_company_service=TrackedCompanyService(session),
        as_of=date(2026, 9, 2),
    )
    service._news_classifier = news_classifier
    service._recommendation_engine = recommendation_engine
    return service, company_sync, security_sync, financial_sync, news_sync


@pytest.mark.asyncio
async def test_onboarding_reuses_local_security(
    db_session: AsyncSession,
) -> None:
    company, _on, pn = await _seed_itau(db_session)
    b3 = Mock()
    b3.discover_ticker_issuer = AsyncMock(return_value=None)
    service, company_sync, security_sync, financial_sync, news_sync = _build_service(
        db_session,
        b3_client=b3,
        company=company,
        securities=[_on, pn],
    )

    result = await service.submit(" onbd4 ")
    assert result.job is not None
    await service.run_job(result.job.id or 0)

    b3.discover_ticker_issuer.assert_not_called()
    company_sync.sync_by_cvm_code.assert_awaited()
    security_sync.sync_by_cvm_code.assert_awaited()
    years = [call.kwargs["year"] for call in financial_sync.sync.await_args_list]
    types = [
        call.kwargs["document_type"] for call in financial_sync.sync.await_args_list
    ]
    assert types == ["DFP", "ITR"]
    assert years == [2025, 2026]
    news_sync.sync_company_news.assert_awaited()
    job = await service.get_job(result.job.id or 0)
    assert job.status == OnboardingStatus.READY.value
    assert job.tracked_company_id is not None


@pytest.mark.asyncio
async def test_unknown_ticker_uses_b3_discovery(
    db_session: AsyncSession,
) -> None:
    company = await _seed_itau_company(db_session)
    issuer = B3TickerIssuer(
        ticker="ONBD4",
        cvm_code="19999",
        issuing_company="ONBD",
        company_name="ITAU UNIBANCO HOLDING S.A.",
        trading_name="ITAUUNIBANCO",
    )
    b3 = Mock()
    b3.discover_ticker_issuer = AsyncMock(return_value=issuer)
    service, company_sync, security_sync, _financial, news_sync = _build_service(
        db_session,
        b3_client=b3,
        company=company,
    )

    async def sync_securities(_cvm_code: str) -> list[Security]:
        repository = SecurityRepository(db_session)
        assert company.id is not None
        on = await repository.add(
            Security(
                company_id=company.id,
                ticker="ONBD3",
                isin="BRONBDACNOR4",
                security_type="ON",
            )
        )
        pn = await repository.add(
            Security(
                company_id=company.id,
                ticker="ONBD4",
                isin="BRONBDACNPR1",
                security_type="PN",
            )
        )
        await db_session.flush()
        return [on, pn]

    security_sync.sync_by_cvm_code = AsyncMock(side_effect=sync_securities)

    result = await service.submit("ONBD4")
    assert result.job is not None
    await service.run_job(result.job.id or 0)

    b3.discover_ticker_issuer.assert_awaited_once_with("ONBD4")
    company_sync.sync_by_cvm_code.assert_awaited_with("19999")
    security_sync.sync_by_cvm_code.assert_awaited()
    news_sync.sync_company_news.assert_awaited()
    job = await service.get_job(result.job.id or 0)
    assert job.status == OnboardingStatus.READY.value


@pytest.mark.asyncio
async def test_second_onboarding_does_not_duplicate(
    db_session: AsyncSession,
) -> None:
    company, on, pn = await _seed_itau(db_session)
    b3 = Mock()
    b3.discover_ticker_issuer = AsyncMock(return_value=None)
    service, *_rest = _build_service(
        db_session,
        b3_client=b3,
        company=company,
        securities=[on, pn],
    )
    first = await service.submit("ONBD4")
    assert first.job is not None
    await service.run_job(first.job.id or 0)

    second = await service.submit("ONBD4")
    assert second.already_tracked is True
    assert second.accepted is False
    records = await TrackedCompanyService(db_session).list_active()
    itau = [item for item in records if item.tracked.company_id == company.id]
    assert len(itau) == 1


@pytest.mark.asyncio
async def test_active_job_prevents_duplicate_ingestion(
    db_session: AsyncSession,
) -> None:
    b3 = Mock()
    b3.discover_ticker_issuer = AsyncMock(return_value=None)
    service, company_sync, *_rest = _build_service(
        db_session,
        b3_client=b3,
    )
    first = await service.submit("ONBD4")
    second = await service.submit("ONBD4")

    assert first.job is not None
    assert second.job is not None
    assert first.job.id == second.job.id
    company_sync.sync_by_cvm_code.assert_not_called()


@pytest.mark.asyncio
async def test_discovery_failure_records_failed_step(
    db_session: AsyncSession,
) -> None:
    b3 = Mock()
    b3.discover_ticker_issuer = AsyncMock(return_value=None)
    service, *_rest = _build_service(db_session, b3_client=b3)
    result = await service.submit("ONBD4")
    assert result.job is not None
    await service.run_job(result.job.id or 0)

    job = await service.get_job(result.job.id or 0)
    assert job.status == OnboardingStatus.FAILED.value
    assert job.step == OnboardingStep.RESOLVING_TICKER.value
    assert job.error_code == "TICKER_NOT_FOUND"


@pytest.mark.asyncio
async def test_retry_resumes_failed_job(
    db_session: AsyncSession,
) -> None:
    company = await _seed_itau_company(db_session)
    issuer = B3TickerIssuer(
        ticker="ONBD4",
        cvm_code="19999",
        issuing_company="ONBD",
        company_name="ITAU UNIBANCO HOLDING S.A.",
        trading_name="ITAUUNIBANCO",
    )
    b3 = Mock()
    b3.discover_ticker_issuer = AsyncMock(side_effect=[None, issuer])
    service, *_rest = _build_service(
        db_session,
        b3_client=b3,
        company=company,
    )

    async def sync_securities(_cvm_code: str) -> list[Security]:
        repository = SecurityRepository(db_session)
        assert company.id is not None
        on = await repository.add(
            Security(
                company_id=company.id,
                ticker="ONBD3",
                isin="BRONBDACNOR4",
                security_type="ON",
            )
        )
        pn = await repository.add(
            Security(
                company_id=company.id,
                ticker="ONBD4",
                isin="BRONBDACNPR1",
                security_type="PN",
            )
        )
        await db_session.flush()
        return [on, pn]

    service.security_sync_service.sync_by_cvm_code = AsyncMock(
        side_effect=sync_securities,
    )

    submitted = await service.submit("ONBD4")
    assert submitted.job is not None
    await service.run_job(submitted.job.id or 0)
    failed = await service.get_job(submitted.job.id or 0)
    assert failed.status == OnboardingStatus.FAILED.value

    retried = await service.retry(submitted.job.id or 0)
    assert retried.job is not None
    await service.run_job(retried.job.id or 0)
    ready = await service.get_job(retried.job.id or 0)
    assert ready.status == OnboardingStatus.READY.value
    records = await TrackedCompanyService(db_session).list_active()
    itau = [item for item in records if item.tracked.company_id == company.id]
    assert len(itau) == 1


@pytest.mark.asyncio
async def test_onboarding_does_not_call_news_classifier_or_recommendation(
    db_session: AsyncSession,
) -> None:
    company, on, pn = await _seed_itau(db_session)
    classifier = Mock()
    engine = Mock()
    b3 = Mock()
    b3.discover_ticker_issuer = AsyncMock(return_value=None)
    service, *_rest = _build_service(
        db_session,
        b3_client=b3,
        company=company,
        securities=[on, pn],
        news_classifier=classifier,
        recommendation_engine=engine,
    )
    result = await service.submit("ONBD4")
    assert result.job is not None
    await service.run_job(result.job.id or 0)

    classifier.assert_not_called()
    engine.assert_not_called()
    assert not hasattr(service, "news_classifier")
