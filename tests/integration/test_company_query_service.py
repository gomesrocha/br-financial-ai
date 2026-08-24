import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import Company, Security
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.services.company_query import CompanyQueryService


@pytest.mark.asyncio
async def test_find_company_by_ticker(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="QUERY001",
            cnpj="88000000000101",
            legal_name="EMPRESA QUERY S.A.",
            trade_name="EMPRESA QUERY",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="QURY3",
            isin="BRQURYACNOR1",
            security_type="ON",
        )
    )

    service = CompanyQueryService(db_session)

    found = await service.find_by_ticker("qury3")

    assert found is not None
    assert found.id == company.id
    assert found.trade_name == "EMPRESA QUERY"


@pytest.mark.asyncio
async def test_find_company_by_unknown_ticker(
    db_session: AsyncSession,
) -> None:
    service = CompanyQueryService(db_session)

    found = await service.find_by_ticker("NONE3")

    assert found is None
