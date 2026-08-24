import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.clients.b3 import B3Client
from br_financial_ai.db.models import Company
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.services.exceptions import CompanyNotFoundError
from br_financial_ai.services.security_sync import SecuritySyncService


def create_b3_transport(
    cvm_code: str,
) -> httpx.MockTransport:
    response_data = {
        "codeCVM": cvm_code,
        "otherCodes": [
            {
                "code": "TSTA3",
                "isin": "BRTSTAACNOR1",
            },
            {
                "code": "TSTA4",
                "isin": "BRTSTAACNPR2",
            },
            {
                "code": "TSTA-DEB62",
                "isin": "BRTSTADBS092",
            },
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=response_data,
            request=request,
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_sync_company_securities_from_b3(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="TEST9512",
            cnpj="99000000000101",
            legal_name="EMPRESA TESTE A S.A.",
            trade_name="EMPRESA TESTE A",
        )
    )

    assert company.id is not None

    transport = create_b3_transport("TEST9512")

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        b3_client = B3Client(http_client)

        service = SecuritySyncService(
            db_session,
            b3_client,
        )

        securities = await service.sync_by_cvm_code("TEST9512")

    assert len(securities) == 2

    security_repository = SecurityRepository(db_session)

    common_share = await security_repository.get_by_ticker("TSTA3")
    preferred_share = await security_repository.get_by_ticker("TSTA4")

    assert common_share is not None
    assert preferred_share is not None

    assert common_share.isin == "BRTSTAACNOR1"
    assert common_share.security_type == "ON"
    assert common_share.company_id == company.id

    assert preferred_share.isin == "BRTSTAACNPR2"
    assert preferred_share.security_type == "PN"
    assert preferred_share.company_id == company.id


@pytest.mark.asyncio
async def test_sync_company_securities_is_idempotent(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="TEST9513",
            cnpj="99000000000102",
            legal_name="EMPRESA TESTE B S.A.",
            trade_name="EMPRESA TESTE B",
        )
    )

    assert company.id is not None

    transport = create_b3_transport("TEST9513")

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        service = SecuritySyncService(
            db_session,
            B3Client(http_client),
        )

        first = await service.sync_by_cvm_code("TEST9513")
        second = await service.sync_by_cvm_code("TEST9513")

    assert len(first) == 2
    assert len(second) == 2

    assert [security.id for security in first] == [security.id for security in second]


@pytest.mark.asyncio
async def test_sync_securities_requires_existing_company(
    db_session: AsyncSession,
) -> None:
    transport = create_b3_transport("UNKNOWN")

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        service = SecuritySyncService(
            db_session,
            B3Client(http_client),
        )

        with pytest.raises(CompanyNotFoundError):
            await service.sync_by_cvm_code("UNKNOWN")
