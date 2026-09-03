import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.clients.cvm import CvmClient
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.services.company_sync import CompanySyncService
from br_financial_ai.services.exceptions import CvmCompanyNotFoundError


def create_cvm_transport() -> httpx.MockTransport:
    csv_content = (
        "CNPJ_CIA;DENOM_SOCIAL;DENOM_COMERC;SIT;CD_CVM;SETOR_ATIV\n"
        "33.000.167/0001-01;"
        "PETRÓLEO BRASILEIRO S.A. - PETROBRAS;"
        "PETROBRAS;"
        "ATIVO;"
        "9512;"
        "Petróleo e Gás\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=csv_content.encode(),
            request=request,
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_sync_company_from_cvm(
    db_session: AsyncSession,
) -> None:
    transport = create_cvm_transport()

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        cvm_client = CvmClient(http_client)

        service = CompanySyncService(
            db_session,
            cvm_client,
        )

        company = await service.sync_by_cvm_code("9512")

    assert company.id is not None
    assert company.cvm_code == "9512"
    assert company.cnpj == "33000167000101"
    assert company.trade_name == "PETROBRAS"
    assert company.active is True
    assert company.setor_ativ == "Petróleo e Gás"

    repository = CompanyRepository(db_session)

    saved_company = await repository.get_by_cvm_code("9512")

    assert saved_company is not None
    assert saved_company.id == company.id


def create_bank_cvm_transport() -> httpx.MockTransport:
    csv_content = (
        "CNPJ_CIA;DENOM_SOCIAL;DENOM_COMERC;SIT;CD_CVM;SETOR_ATIV\n"
        "00.000.000/0001-91;"
        "BANCO TESTE S.A.;"
        "BANCO TESTE;"
        "ATIVO;"
        "88001;"
        "Bancos\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=csv_content.encode(),
            request=request,
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_sync_existing_company_refreshes_null_setor_ativ(
    db_session: AsyncSession,
) -> None:
    from br_financial_ai.db.models import Company

    db_session.add(
        Company(
            cvm_code="88001",
            cnpj="00000000000191",
            legal_name="BANCO TESTE S.A.",
            trade_name="BANCO TESTE",
            setor_ativ=None,
            active=True,
        )
    )
    await db_session.flush()

    transport = create_bank_cvm_transport()

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        cvm_client = CvmClient(http_client)
        service = CompanySyncService(
            db_session,
            cvm_client,
        )
        company = await service.sync_by_cvm_code("88001")

    assert company.setor_ativ == "Bancos"

    repository = CompanyRepository(db_session)
    saved = await repository.get_by_cvm_code("88001")
    assert saved is not None
    assert saved.setor_ativ == "Bancos"


@pytest.mark.asyncio
async def test_sync_existing_company_does_not_duplicate(
    db_session: AsyncSession,
) -> None:
    transport = create_cvm_transport()

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        cvm_client = CvmClient(http_client)

        service = CompanySyncService(
            db_session,
            cvm_client,
        )

        first = await service.sync_by_cvm_code("9512")
        second = await service.sync_by_cvm_code("9512")

    assert first.id is not None
    assert second.id == first.id


@pytest.mark.asyncio
async def test_sync_unknown_cvm_company(
    db_session: AsyncSession,
) -> None:
    transport = create_cvm_transport()

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        cvm_client = CvmClient(http_client)

        service = CompanySyncService(
            db_session,
            cvm_client,
        )

        with pytest.raises(CvmCompanyNotFoundError):
            await service.sync_by_cvm_code("999999")
