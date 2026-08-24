import httpx
import pytest

from br_financial_ai.clients.cvm import CvmClient


@pytest.mark.asyncio
async def test_get_company_by_cvm_code() -> None:
    csv_content = (
        "CNPJ_CIA;DENOM_SOCIAL;DENOM_COMERC;SIT;CD_CVM\n"
        "33.000.167/0001-01;"
        "PETRÓLEO BRASILEIRO S.A. - PETROBRAS;"
        "PETROBRAS;"
        "ATIVO;"
        "9512\n"
        "33.592.510/0001-54;"
        "VALE S.A.;"
        "VALE;"
        "ATIVO;"
        "4170\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=csv_content.encode(),
            request=request,
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        client = CvmClient(http_client)

        company = await client.get_company_by_cvm_code("9512")

    assert company is not None
    assert company.trade_name == "PETROBRAS"
    assert company.cnpj == "33000167000101"


@pytest.mark.asyncio
async def test_get_company_by_unknown_cvm_code() -> None:
    csv_content = (
        "CNPJ_CIA;DENOM_SOCIAL;DENOM_COMERC;SIT;CD_CVM\n"
        "33.000.167/0001-01;"
        "PETRÓLEO BRASILEIRO S.A. - PETROBRAS;"
        "PETROBRAS;"
        "ATIVO;"
        "9512\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=csv_content.encode(),
            request=request,
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        client = CvmClient(http_client)

        company = await client.get_company_by_cvm_code("999999")

    assert company is None
