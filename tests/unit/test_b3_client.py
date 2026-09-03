import httpx
import pytest

from br_financial_ai.clients.b3 import (
    B3Client,
    classify_equity_ticker,
    parse_company_securities,
    parse_listed_company_search,
    rank_ticker_discovery_candidates,
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


def test_parse_listed_company_search() -> None:
    companies = parse_listed_company_search(
        {
            "results": [
                {
                    "codeCVM": "19348",
                    "issuingCompany": "ITUB",
                    "companyName": "ITAU UNIBANCO HOLDING S.A.",
                    "tradingName": "ITAUUNIBANCO",
                }
            ]
        }
    )

    assert len(companies) == 1
    assert companies[0].cvm_code == "19348"
    assert companies[0].issuing_company == "ITUB"


def test_rank_ticker_discovery_candidates_prefers_issuing_prefix() -> None:
    ranked = rank_ticker_discovery_candidates(
        "ITUB4",
        parse_listed_company_search(
            {
                "results": [
                    {
                        "codeCVM": "917506",
                        "issuingCompany": "MRTR",
                        "companyName": "MARITUBA",
                        "tradingName": "MARITUBATRA",
                    },
                    {
                        "codeCVM": "19348",
                        "issuingCompany": "ITUB",
                        "companyName": "ITAU UNIBANCO HOLDING S.A.",
                        "tradingName": "ITAUUNIBANCO",
                    },
                ]
            }
        ),
    )

    assert [item.cvm_code for item in ranked] == ["19348", "917506"]


@pytest.mark.asyncio
async def test_discover_ticker_issuer_confirms_security() -> None:
    search_data = {
        "results": [
            {
                "codeCVM": "19348",
                "issuingCompany": "ITUB",
                "companyName": "ITAU UNIBANCO HOLDING S.A.",
                "tradingName": "ITAUUNIBANCO",
            }
        ]
    }
    detail_data = {
        "codeCVM": "19348",
        "otherCodes": [
            {"code": "ITUB3", "isin": "BRITUBACNOR4"},
            {"code": "ITUB4", "isin": "BRITUBACNPR1"},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "GetInitialCompanies" in str(request.url):
            return httpx.Response(200, json=search_data, request=request)
        return httpx.Response(200, json=detail_data, request=request)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = B3Client(http_client)
        issuer = await client.discover_ticker_issuer("itub4")

    assert issuer is not None
    assert issuer.ticker == "ITUB4"
    assert issuer.cvm_code == "19348"


@pytest.mark.asyncio
async def test_discover_ticker_issuer_rejects_unrelated_search_hit() -> None:
    search_data = {
        "results": [
            {
                "codeCVM": "917506",
                "issuingCompany": "MRTR",
                "companyName": "MARITUBA",
                "tradingName": "MARITUBATRA",
            }
        ]
    }
    detail_data = {
        "codeCVM": "917506",
        "otherCodes": [{"code": "MRTR3", "isin": "BRMRTRACNOR1"}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "GetInitialCompanies" in str(request.url):
            return httpx.Response(200, json=search_data, request=request)
        return httpx.Response(200, json=detail_data, request=request)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = B3Client(http_client)
        issuer = await client.discover_ticker_issuer("ITUB4")

    assert issuer is None
