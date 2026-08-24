import httpx
import pytest

from br_financial_ai.clients.b3 import (
    B3Client,
    classify_equity_ticker,
    parse_company_securities,
)


def test_classify_common_share() -> None:
    assert classify_equity_ticker("PETR3") == "ON"


def test_classify_preferred_share() -> None:
    assert classify_equity_ticker("PETR4") == "PN"


def test_reject_debenture() -> None:
    assert classify_equity_ticker("PETR-DEB62") is None


def test_parse_petrobras_securities() -> None:
    data = {
        "issuingCompany": "PETR",
        "companyName": "PETROLEO BRASILEIRO S.A. PETROBRAS",
        "tradingName": "PETROBRAS",
        "codeCVM": "9512",
        "otherCodes": [
            {
                "code": "PETR3",
                "isin": "BRPETRACNOR9",
            },
            {
                "code": "PETR4",
                "isin": "BRPETRACNPR6",
            },
            {
                "code": "PETR-DEB62",
                "isin": "BRPETRDBS092",
            },
        ],
    }

    securities = parse_company_securities(data)

    assert len(securities) == 2

    assert securities[0].ticker == "PETR3"
    assert securities[0].isin == "BRPETRACNOR9"
    assert securities[0].security_type == "ON"

    assert securities[1].ticker == "PETR4"
    assert securities[1].isin == "BRPETRACNPR6"
    assert securities[1].security_type == "PN"


@pytest.mark.asyncio
async def test_get_company_securities() -> None:
    response_data = {
        "codeCVM": "9512",
        "otherCodes": [
            {
                "code": "PETR3",
                "isin": "BRPETRACNOR9",
            },
            {
                "code": "PETR4",
                "isin": "BRPETRACNPR6",
            },
            {
                "code": "PETR-DEB62",
                "isin": "BRPETRDBS092",
            },
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=response_data,
            request=request,
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        client = B3Client(http_client)

        securities = await client.get_company_securities("9512")

    assert [security.ticker for security in securities] == [
        "PETR3",
        "PETR4",
    ]
