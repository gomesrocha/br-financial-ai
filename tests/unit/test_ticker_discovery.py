from datetime import date
from pathlib import Path

import httpx
import pytest

from br_financial_ai.clients.b3 import B3SecurityRecord, B3TickerIssuer
from br_financial_ai.clients.b3_instruments import (
    B3InstrumentsClient,
    parse_instruments_consolidated,
)
from br_financial_ai.clients.cvm import CvmCompanyRecord, parse_companies_csv
from br_financial_ai.domain.ticker_discovery import (
    TickerDiscoveryAmbiguousError,
    TickerDiscoveryNotFoundError,
    TickerDiscoverySource,
    TickerDiscoveryUnavailableError,
    match_cvm_company,
    normalize_company_name,
    result_from_instrument_match,
)
from br_financial_ai.services.ticker_discovery import (
    B3InstrumentsCvmDiscovery,
    B3ListedCompaniesDiscovery,
    CompositeTickerDiscovery,
)

ITUB_INSTRUMENTS_CSV = "\n".join(
    [
        "Status do Arquivo: Parcial",
        "RptDt;TckrSymb;Asst;AsstDesc;SgmtNm;MktNm;SctyCtgyNm;ISIN;CFICd;CrpnNm",
        "2026-09-02;ITUB3;ITUB;ITUB;CASH;EQUITY-CASH;SHARES;"
        "BRITUBACNOR4;ESVUFR;ITAU UNIBANCO HOLDING S.A.",
        "2026-09-02;ITUB3F;ITUB;ITUB;ODD LOT;EQUITY-CASH;SHARES;"
        "BRITUBACNOR4;ESVUFR;ITAU UNIBANCO HOLDING S.A.",
        "2026-09-02;ITUB4;ITUB;ITUB;CASH;EQUITY-CASH;SHARES;"
        "BRITUBACNPR1;EPNNPR;ITAU UNIBANCO HOLDING S.A.",
        "2026-09-02;PETR4;PETR;PETR;CASH;EQUITY-CASH;SHARES;"
        "BRPETRACNPR6;EPNNPR;PETROLEO BRASILEIRO S.A. PETROBRAS",
        "",
    ]
)

CVM_CSV = (
    "CNPJ_CIA;DENOM_SOCIAL;DENOM_COMERC;SIT;CD_CVM\n"
    "60.872.504/0001-23;ITAÚ UNIBANCO HOLDING S.A.;ITAÚ UNIBANCO;ATIVO;19348\n"
    "33.000.167/0001-01;PETRÓLEO BRASILEIRO S.A. - PETROBRAS;PETROBRAS;ATIVO;9512\n"
)


def _cvm_companies() -> list[CvmCompanyRecord]:
    return parse_companies_csv(CVM_CSV.encode("utf-8"))


def test_normalize_company_name_strips_accents_and_punctuation() -> None:
    assert normalize_company_name("ITAÚ UNIBANCO HOLDING S.A.") == (
        "ITAU UNIBANCO HOLDING SA"
    )
    assert normalize_company_name("PETRÓLEO BRASILEIRO S.A. - PETROBRAS") == (
        "PETROLEO BRASILEIRO SA PETROBRAS"
    )


def test_match_prefers_active_cvm_registration() -> None:
    companies = [
        CvmCompanyRecord(
            cvm_code="1",
            cnpj="1",
            legal_name="ACME HOLDING S.A.",
            trade_name="ACME",
            status="CANCELADO",
        ),
        CvmCompanyRecord(
            cvm_code="19348",
            cnpj="60872504000123",
            legal_name="ITAÚ UNIBANCO HOLDING S.A.",
            trade_name="ITAÚ UNIBANCO",
            status="ATIVO",
        ),
        CvmCompanyRecord(
            cvm_code="9",
            cnpj="9",
            legal_name="ITAÚ UNIBANCO HOLDING S.A.",
            trade_name="OLD ITAU",
            status="CANCELADO",
        ),
    ]
    matched = match_cvm_company("ITAU UNIBANCO HOLDING S.A.", companies)
    assert matched.cvm_code == "19348"


def test_inactive_only_match_is_not_used() -> None:
    companies = [
        CvmCompanyRecord(
            cvm_code="19348",
            cnpj="60872504000123",
            legal_name="ITAÚ UNIBANCO HOLDING S.A.",
            trade_name="ITAÚ UNIBANCO",
            status="CANCELADO",
        )
    ]
    with pytest.raises(TickerDiscoveryNotFoundError):
        match_cvm_company("ITAU UNIBANCO HOLDING S.A.", companies)


def test_ambiguous_active_companies_fail() -> None:
    companies = [
        CvmCompanyRecord(
            cvm_code="1",
            cnpj="1",
            legal_name="ITAÚ UNIBANCO HOLDING S.A.",
            trade_name="A",
            status="ATIVO",
        ),
        CvmCompanyRecord(
            cvm_code="2",
            cnpj="2",
            legal_name="ITAU UNIBANCO HOLDING SA",
            trade_name="B",
            status="ATIVO",
        ),
    ]
    with pytest.raises(TickerDiscoveryAmbiguousError):
        match_cvm_company("ITAU UNIBANCO HOLDING S.A.", companies)


def test_itub4_fixture_resolves_cvm_19348_without_ticker_branch() -> None:
    records = parse_instruments_consolidated(ITUB_INSTRUMENTS_CSV.encode("latin-1"))
    result = result_from_instrument_match("ITUB4", records, _cvm_companies())

    assert result.cvm_code == "19348"
    assert result.requested_ticker == "ITUB4"
    assert result.source == TickerDiscoverySource.B3_INSTRUMENTS_CONSOLIDATED.value
    assert [item.ticker for item in result.securities] == ["ITUB3", "ITUB4"]
    assert result.securities[0].isin == "BRITUBACNOR4"
    assert result.securities[1].isin == "BRITUBACNPR1"
    assert result.securities[1].security_type == "PN"


def test_instrument_ticker_without_isin_is_ignored() -> None:
    csv = "\n".join(
        [
            "RptDt;TckrSymb;Asst;AsstDesc;SgmtNm;MktNm;SctyCtgyNm;ISIN;CFICd;CrpnNm",
            "2026-09-02;ITUB4;ITUB;ITUB;CASH;EQUITY-CASH;SHARES;;EPNNPR;"
            "ITAU UNIBANCO HOLDING S.A.",
            "",
        ]
    )
    records = parse_instruments_consolidated(csv.encode())
    with pytest.raises(TickerDiscoveryNotFoundError):
        result_from_instrument_match("ITUB4", records, _cvm_companies())


@pytest.mark.asyncio
async def test_local_security_wins_without_external_calls() -> None:
    listed = _Provider(TickerDiscoveryUnavailableError("listed"))
    fallback = _Provider(TickerDiscoveryUnavailableError("fallback"))
    local = _ResultProvider(
        requested_ticker="ITUB4",
        cvm_code="19348",
        company_name="ITAÚ UNIBANCO HOLDING S.A.",
        source=TickerDiscoverySource.LOCAL.value,
    )
    discovery = CompositeTickerDiscovery((local, listed, fallback))

    result = await discovery.discover("ITUB4")

    assert result.source == TickerDiscoverySource.LOCAL.value
    assert listed.calls == 0
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_primary_b3_listed_success_skips_fallback() -> None:
    local = _Provider(TickerDiscoveryNotFoundError("local"))
    listed = _ResultProvider(
        requested_ticker="ITUB4",
        cvm_code="19348",
        company_name="ITAU UNIBANCO HOLDING S.A.",
        source=TickerDiscoverySource.B3_LISTED_COMPANIES.value,
    )
    fallback = _Provider(TickerDiscoveryUnavailableError("fallback"))
    discovery = CompositeTickerDiscovery((local, listed, fallback))

    result = await discovery.discover("ITUB4")

    assert result.source == TickerDiscoverySource.B3_LISTED_COMPANIES.value
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_listed_unavailable_uses_official_fallback() -> None:
    local = _Provider(TickerDiscoveryNotFoundError("local"))
    listed = _Provider(TickerDiscoveryUnavailableError("listed"))
    records = parse_instruments_consolidated(ITUB_INSTRUMENTS_CSV.encode("latin-1"))
    fallback = B3InstrumentsCvmDiscovery(
        _StaticInstrumentsClient(records),
        _StaticCvmClient(_cvm_companies()),
    )
    discovery = CompositeTickerDiscovery((local, listed, fallback))

    result = await discovery.discover("itub4")

    assert result.cvm_code == "19348"
    assert result.source == TickerDiscoverySource.B3_INSTRUMENTS_CONSOLIDATED.value
    assert [item.ticker for item in result.securities] == ["ITUB3", "ITUB4"]


@pytest.mark.asyncio
async def test_no_candidate_fails() -> None:
    local = _Provider(TickerDiscoveryNotFoundError("local"))
    listed = _Provider(TickerDiscoveryNotFoundError("listed"))
    records = parse_instruments_consolidated(ITUB_INSTRUMENTS_CSV.encode("latin-1"))
    fallback = B3InstrumentsCvmDiscovery(
        _StaticInstrumentsClient(records),
        _StaticCvmClient(_cvm_companies()),
    )
    discovery = CompositeTickerDiscovery((local, listed, fallback))

    with pytest.raises(TickerDiscoveryNotFoundError):
        await discovery.discover("XXXX4")


@pytest.mark.asyncio
async def test_all_providers_unavailable() -> None:
    discovery = CompositeTickerDiscovery(
        (
            _LocalMiss(),
            _Provider(TickerDiscoveryUnavailableError("listed")),
            _Provider(TickerDiscoveryUnavailableError("fallback")),
        )
    )
    with pytest.raises(TickerDiscoveryUnavailableError):
        await discovery.discover("ITUB4")


@pytest.mark.asyncio
async def test_listed_provider_maps_http_error_to_unavailable() -> None:
    class Client:
        async def discover_ticker_issuer(self, ticker: str):
            raise httpx.ConnectTimeout("blocked")

    provider = B3ListedCompaniesDiscovery(Client())  # type: ignore[arg-type]
    with pytest.raises(TickerDiscoveryUnavailableError):
        await provider.discover("ITUB4")


@pytest.mark.asyncio
async def test_listed_provider_returns_issuer_without_guessing_isin() -> None:
    class Client:
        async def discover_ticker_issuer(self, ticker: str):
            return B3TickerIssuer(
                ticker="ITUB4",
                cvm_code="19348",
                issuing_company="ITUB",
                company_name="ITAU UNIBANCO HOLDING S.A.",
                trading_name="ITAUUNIBANCO",
            )

        async def get_company_securities(self, cvm_code: str):
            return [
                B3SecurityRecord(
                    ticker="ITUB4",
                    isin="BRITUBACNPR1",
                    security_type="PN",
                )
            ]

    client = Client()
    result = await B3ListedCompaniesDiscovery(client).discover("ITUB4")  # type: ignore[arg-type]
    assert result.cvm_code == "19348"
    assert result.securities[0].isin == "BRITUBACNPR1"


@pytest.mark.asyncio
async def test_instruments_client_downloads_tokenized_file() -> None:
    csv = ITUB_INSTRUMENTS_CSV.encode("latin-1")

    def handler(request: httpx.Request) -> httpx.Response:
        if "requestname" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "token": "abc",
                    "file": {
                        "name": "InstrumentsConsolidatedFile_20260902_1",
                        "extension": ".csv",
                    },
                },
                request=request,
            )
        return httpx.Response(200, content=csv, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = B3InstrumentsClient(http_client, as_of=date(2026, 9, 2))
        records = await client.get_equity_records()

    assert any(item.ticker == "ITUB4" for item in records)


def test_discovery_modules_do_not_import_yahoo() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "br_financial_ai"
    for relative in (
        "domain/ticker_discovery.py",
        "services/ticker_discovery.py",
        "clients/b3_instruments.py",
    ):
        text = (root / relative).read_text()
        assert "yahoo" not in text.lower()


class _LocalMiss:
    cache_miss_only = True

    async def discover(self, ticker: str):
        raise TickerDiscoveryNotFoundError(ticker)


class _Provider:
    cache_miss_only = False

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    async def discover(self, ticker: str):
        self.calls += 1
        raise self.error


class _ResultProvider:
    def __init__(self, **kwargs: str) -> None:
        self.kwargs = kwargs
        self.calls = 0

    async def discover(self, ticker: str):
        from br_financial_ai.domain.ticker_discovery import TickerDiscoveryResult

        self.calls += 1
        return TickerDiscoveryResult(
            requested_ticker=self.kwargs["requested_ticker"],
            cvm_code=self.kwargs["cvm_code"],
            company_name=self.kwargs["company_name"],
            securities=(),
            source=self.kwargs["source"],
        )


class _StaticInstrumentsClient:
    def __init__(self, records: list) -> None:
        self.records = records

    async def get_equity_records(self):
        return self.records


class _StaticCvmClient:
    def __init__(self, companies: list[CvmCompanyRecord]) -> None:
        self.companies = companies

    async def get_companies(self):
        return self.companies
