from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.api.dependencies import (
    get_financial_query_service,
)
from br_financial_ai.db.models import (
    Company,
    FinancialFiling,
    FinancialStatementItem,
    Security,
)
from br_financial_ai.main import app
from br_financial_ai.repositories.company import (
    CompanyRepository,
)
from br_financial_ai.repositories.financial_filing import (
    FinancialFilingRepository,
)
from br_financial_ai.repositories.financial_statement_item import (
    FinancialStatementItemRepository,
)
from br_financial_ai.repositories.security import (
    SecurityRepository,
)
from br_financial_ai.services.financial_query import (
    FinancialQueryService,
)


@pytest.mark.asyncio
async def test_get_quarter_account_api(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)
    filing_repository = FinancialFilingRepository(db_session)

    item_repository = FinancialStatementItemRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="API900",
            cnpj="92000000000101",
            legal_name="EMPRESA FINANCIAL API S.A.",
            trade_name="FINANCIAL API",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="FAPI3",
            isin="BRFAPIACNOR1",
            security_type="ON",
        )
    )

    filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 6, 30),
            version=1,
            source_year=2026,
        )
    )

    assert filing.id is not None

    await item_repository.add_all(
        [
            FinancialStatementItem(
                filing_id=filing.id,
                statement_type="DRE",
                scope="CONSOLIDATED",
                exercise_order="ÚLTIMO",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 6, 30),
                statement_column=None,
                account_code="3.01",
                account_name="Receita",
                value=Decimal("169.0000000000"),
                currency="REAL",
                currency_scale="MIL",
                fixed_account_status="S",
                source_group="DF Consolidado - DRE",
            )
        ]
    )

    def override_financial_query_service() -> FinancialQueryService:
        return FinancialQueryService(db_session)

    app.dependency_overrides[get_financial_query_service] = (
        override_financial_query_service
    )

    try:
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/financials/by-ticker/FAPI3/quarterly/2026/2/accounts/3.01"
            )

    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()

    assert body["ticker"] == "FAPI3"
    assert body["year"] == 2026
    assert body["quarter"] == 2

    assert body["account_code"] == "3.01"
    assert body["account_name"] == "Receita"

    assert body["period_start"] == "2026-04-01"
    assert body["period_end"] == "2026-06-30"

    assert Decimal(str(body["value"])) == Decimal("169.0000000000")

    assert body["currency"] == "REAL"
    assert body["currency_scale"] == "MIL"


@pytest.mark.asyncio
async def test_invalid_quarter_returns_400(
    db_session: AsyncSession,
) -> None:
    def override_financial_query_service() -> FinancialQueryService:
        return FinancialQueryService(db_session)

    app.dependency_overrides[get_financial_query_service] = (
        override_financial_query_service
    )

    try:
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/financials/by-ticker/PETR4/quarterly/2026/5/accounts/3.01"
            )

    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400

    assert response.json() == {"detail": "Quarter must be between 1 and 4."}
