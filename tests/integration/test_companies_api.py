import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.api.dependencies import get_company_query_service
from br_financial_ai.db.models import Company, Security
from br_financial_ai.main import app
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.services.company_query import CompanyQueryService


@pytest.mark.asyncio
async def test_get_company_by_ticker(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="API001",
            cnpj="77000000000101",
            legal_name="EMPRESA API S.A.",
            trade_name="EMPRESA API",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="APIT3",
            isin="BRAPITACNOR1",
            security_type="ON",
        )
    )

    def override_company_query_service() -> CompanyQueryService:
        return CompanyQueryService(db_session)

    app.dependency_overrides[get_company_query_service] = override_company_query_service

    try:
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get("/companies/by-ticker/apit3")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    assert response.json() == {
        "id": company.id,
        "cvm_code": "API001",
        "cnpj": "77000000000101",
        "legal_name": "EMPRESA API S.A.",
        "trade_name": "EMPRESA API",
        "active": True,
    }


@pytest.mark.asyncio
async def test_get_company_by_unknown_ticker_returns_404(
    db_session: AsyncSession,
) -> None:
    def override_company_query_service() -> CompanyQueryService:
        return CompanyQueryService(db_session)

    app.dependency_overrides[get_company_query_service] = override_company_query_service

    try:
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get("/companies/by-ticker/NONE3")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Company not found.",
    }
