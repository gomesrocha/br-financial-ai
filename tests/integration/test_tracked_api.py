from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.api.dependencies import (
    get_onboarding_scheduler,
    get_onboarding_service,
    get_tracked_company_service,
    get_yahoo_market_client,
)
from br_financial_ai.clients.yahoo_market import YahooMarketProviderError
from br_financial_ai.db.models import Company, Security
from br_financial_ai.domain.market import MarketQuote
from br_financial_ai.domain.onboarding import OnboardingStatus
from br_financial_ai.main import app
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.services.company_onboarding import CompanyOnboardingService
from br_financial_ai.services.tracked_company import TrackedCompanyService


class RecordingScheduler:
    def __init__(self) -> None:
        self.scheduled: list[int] = []

    def schedule(self, job_id: int) -> None:
        self.scheduled.append(job_id)


async def _seed_tracked(session: AsyncSession) -> None:
    company = await CompanyRepository(session).add(
        Company(
            cvm_code="API193",
            cnpj="60872504000999",
            legal_name="EMPRESA TRACKED S.A.",
            trade_name="TRACKED CO",
        )
    )
    assert company.id is not None
    security = await SecurityRepository(session).add(
        Security(
            company_id=company.id,
            ticker="TRCK4",
            isin="BRTRCKACNPR1",
            security_type="PN",
        )
    )
    await TrackedCompanyService(session).track_company(
        company_id=company.id,
        preferred_security=security,
    )


@pytest.mark.asyncio
async def test_list_tracked_companies_api(
    db_session: AsyncSession,
) -> None:
    await _seed_tracked(db_session)

    app.dependency_overrides[get_tracked_company_service] = lambda: (
        TrackedCompanyService(db_session)
    )
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/companies/tracked")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    by_ticker = {item["ticker"]: item for item in payload}
    assert by_ticker["TRCK4"]["trade_name"] == "TRACKED CO"


@pytest.mark.asyncio
async def test_onboard_returns_202_and_reuses_active_job(
    db_session: AsyncSession,
) -> None:
    scheduler = RecordingScheduler()
    b3 = AsyncMock()
    service = CompanyOnboardingService(
        db_session,
        b3_client=b3,
        company_sync_service=AsyncMock(),
        security_sync_service=AsyncMock(),
        financial_ingestion_service=AsyncMock(),
        news_ingestion_service=AsyncMock(),
        tracked_company_service=TrackedCompanyService(db_session),
    )
    app.dependency_overrides[get_onboarding_service] = lambda: service
    app.dependency_overrides[get_onboarding_scheduler] = lambda: scheduler

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            first = await client.post(
                "/api/v1/companies/onboard",
                json={"ticker": " onbd4 "},
            )
            second = await client.post(
                "/api/v1/companies/onboard",
                json={"ticker": "ONBD4"},
            )
            job_id = first.json()["job_id"]
            fetched = await client.get(f"/api/v1/companies/onboarding/{job_id}")
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 202
    assert first.json()["ticker"] == "ONBD4"
    assert first.json()["status"] == OnboardingStatus.PENDING.value
    assert second.status_code == 202
    assert second.json()["job_id"] == first.json()["job_id"]
    assert scheduler.scheduled == [first.json()["job_id"]]
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "PENDING"


@pytest.mark.asyncio
async def test_onboard_already_tracked_returns_200(
    db_session: AsyncSession,
) -> None:
    await _seed_tracked(db_session)
    scheduler = RecordingScheduler()
    service = CompanyOnboardingService(
        db_session,
        b3_client=AsyncMock(),
        company_sync_service=AsyncMock(),
        security_sync_service=AsyncMock(),
        financial_ingestion_service=AsyncMock(),
        news_ingestion_service=AsyncMock(),
        tracked_company_service=TrackedCompanyService(db_session),
    )
    app.dependency_overrides[get_onboarding_service] = lambda: service
    app.dependency_overrides[get_onboarding_scheduler] = lambda: scheduler

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/companies/onboard",
                json={"ticker": "TRCK4"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["already_tracked"] is True
    assert scheduler.scheduled == []


@pytest.mark.asyncio
async def test_onboard_invalid_ticker_returns_400(
    db_session: AsyncSession,
) -> None:
    service = CompanyOnboardingService(
        db_session,
        b3_client=AsyncMock(),
        company_sync_service=AsyncMock(),
        security_sync_service=AsyncMock(),
        financial_ingestion_service=AsyncMock(),
        news_ingestion_service=AsyncMock(),
        tracked_company_service=TrackedCompanyService(db_session),
    )
    app.dependency_overrides[get_onboarding_service] = lambda: service
    app.dependency_overrides[get_onboarding_scheduler] = lambda: RecordingScheduler()

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/companies/onboard",
                json={"ticker": "ITAU"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_retry_failed_job_and_reject_ready(
    db_session: AsyncSession,
) -> None:
    scheduler = RecordingScheduler()
    b3 = AsyncMock()
    b3.discover_ticker_issuer = AsyncMock(return_value=None)
    service = CompanyOnboardingService(
        db_session,
        b3_client=b3,
        company_sync_service=AsyncMock(),
        security_sync_service=AsyncMock(),
        financial_ingestion_service=AsyncMock(),
        news_ingestion_service=AsyncMock(),
        tracked_company_service=TrackedCompanyService(db_session),
    )
    submitted = await service.submit("ONBD4")
    assert submitted.job is not None
    await service.run_job(submitted.job.id or 0)

    app.dependency_overrides[get_onboarding_service] = lambda: service
    app.dependency_overrides[get_onboarding_scheduler] = lambda: scheduler

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            retry = await client.post(
                f"/api/v1/companies/onboarding/{submitted.job.id}/retry",
            )
            ready_retry = await client.post(
                f"/api/v1/companies/onboarding/{submitted.job.id}/retry",
            )
    finally:
        app.dependency_overrides.clear()

    assert retry.status_code == 202
    assert scheduler.scheduled == [submitted.job.id]
    assert ready_retry.status_code == 409


@pytest.mark.asyncio
async def test_market_quote_api_success() -> None:
    quote = MarketQuote(
        ticker="PETR4",
        symbol="PETR4.SA",
        price=Decimal("46.87"),
        previous_close=Decimal("45.02"),
        currency="BRL",
        timestamp=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
    )
    client = AsyncMock()
    client.get_quote = AsyncMock(return_value=quote)
    app.dependency_overrides[get_yahoo_market_client] = lambda: client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as http_client:
            response = await http_client.get("/api/v1/market/quote/PETR4")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "PETR4"
    assert body["price"] == "46.87"
    assert body["percentage_change"] is not None


@pytest.mark.asyncio
async def test_market_quote_api_provider_failure() -> None:
    client = AsyncMock()
    client.get_quote = AsyncMock(side_effect=YahooMarketProviderError("down"))
    app.dependency_overrides[get_yahoo_market_client] = lambda: client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as http_client:
            response = await http_client.get("/api/v1/market/quote/PETR4")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
