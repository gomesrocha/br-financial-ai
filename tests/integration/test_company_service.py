import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.schemas.company import CompanyCreate, SecurityCreate
from br_financial_ai.services.company import CompanyService
from br_financial_ai.services.exceptions import CompanyAlreadyExistsError


@pytest.mark.asyncio
async def test_create_company_with_securities(
    db_session: AsyncSession,
) -> None:
    service = CompanyService(db_session)

    data = CompanyCreate(
        cvm_code="TEST100",
        cnpj="11111111000199",
        legal_name="Empresa Financeira Teste S.A.",
        trade_name="Financeira Teste",
        securities=[
            SecurityCreate(
                ticker="TEST3",
                security_type="ON",
            ),
            SecurityCreate(
                ticker="TEST4",
                security_type="PN",
            ),
        ],
    )

    company = await service.create_company(data)

    assert company.id is not None
    assert company.trade_name == "Financeira Teste"

    security_repository = SecurityRepository(db_session)

    security_on = await security_repository.get_by_ticker("TEST3")
    security_pn = await security_repository.get_by_ticker("TEST4")

    assert security_on is not None
    assert security_pn is not None
    assert security_on.company_id == company.id
    assert security_pn.company_id == company.id


@pytest.mark.asyncio
async def test_reject_duplicate_company_cvm_code(
    db_session: AsyncSession,
) -> None:
    service = CompanyService(db_session)

    first = CompanyCreate(
        cvm_code="TEST200",
        cnpj="22222222000199",
        legal_name="Empresa Um S.A.",
        trade_name="Empresa Um",
    )

    second = CompanyCreate(
        cvm_code="TEST200",
        cnpj="33333333000199",
        legal_name="Empresa Dois S.A.",
        trade_name="Empresa Dois",
    )

    await service.create_company(first)

    with pytest.raises(CompanyAlreadyExistsError):
        await service.create_company(second)
