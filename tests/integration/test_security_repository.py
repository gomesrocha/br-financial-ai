import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import Company, Security
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.security import SecurityRepository


@pytest.mark.asyncio
async def test_add_and_find_security_by_ticker(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="TEST002",
            cnpj="98765432000199",
            legal_name="Empresa Teste Dois S.A.",
            trade_name="Empresa Teste Dois",
        )
    )

    assert company.id is not None

    security = await security_repository.add(
        Security(
            company_id=company.id,
            ticker="TEST3",
            isin="BRTESTACNOR1",
            security_type="ON",
        )
    )

    assert security.id is not None

    found_security = await security_repository.get_by_ticker("test3")

    assert found_security is not None
    assert found_security.ticker == "TEST3"
    assert found_security.isin == "BRTESTACNOR1"
    assert found_security.company_id == company.id

    found_by_isin = await security_repository.get_by_isin(
        "brtestacnor1",
    )

    assert found_by_isin is not None
    assert found_by_isin.id == security.id
