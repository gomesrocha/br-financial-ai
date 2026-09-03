import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import Company
from br_financial_ai.repositories.company import CompanyRepository


@pytest.mark.asyncio
async def test_add_and_find_company(
    db_session: AsyncSession,
) -> None:
    repository = CompanyRepository(db_session)

    company = Company(
        cvm_code="TEST001",
        cnpj="12345678000199",
        legal_name="Empresa Teste S.A.",
        trade_name="Empresa Teste",
    )

    saved_company = await repository.add(company)

    assert saved_company.id is not None

    found_company = await repository.get_by_cvm_code("TEST001")

    assert found_company is not None
    assert found_company.id == saved_company.id
    assert found_company.trade_name == "Empresa Teste"
