import asyncio
import base64
import json
import re
from dataclasses import dataclass

import httpx

from br_financial_ai.utils.identifiers import normalize_cvm_code

B3_COMPANY_DETAIL_URL = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesProxy/CompanyCall/GetDetail"
)

B3_INITIAL_COMPANIES_URL = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesProxy/CompanyCall/GetInitialCompanies"
)

B3_REQUEST_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://sistemaswebb3-listados.b3.com.br/",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

EQUITY_TICKER_PATTERN = re.compile(r"^[A-Z]{4}[3-8]$")
B3_TRANSPORT_RETRIES = 2
B3_LISTED_TIMEOUT = httpx.Timeout(
    connect=3.0,
    read=8.0,
    write=8.0,
    pool=3.0,
)


@dataclass(frozen=True, slots=True)
class B3SecurityRecord:
    ticker: str
    isin: str
    security_type: str


@dataclass(frozen=True, slots=True)
class B3ListedCompanySummary:
    cvm_code: str
    issuing_company: str
    company_name: str
    trading_name: str


@dataclass(frozen=True, slots=True)
class B3TickerIssuer:
    ticker: str
    cvm_code: str
    issuing_company: str
    company_name: str
    trading_name: str


def classify_equity_ticker(ticker: str) -> str | None:
    normalized_ticker = ticker.strip().upper()

    if not EQUITY_TICKER_PATTERN.fullmatch(normalized_ticker):
        return None

    suffix = normalized_ticker[-1]

    if suffix == "3":
        return "ON"

    if suffix in {"4", "5", "6", "7", "8"}:
        return "PN"

    return None


def parse_company_securities(
    data: dict,
) -> list[B3SecurityRecord]:
    securities: list[B3SecurityRecord] = []

    for item in data.get("otherCodes", []):
        ticker = item.get("code", "").strip().upper()
        isin = item.get("isin", "").strip().upper()

        security_type = classify_equity_ticker(ticker)

        if security_type is None or not isin:
            continue

        securities.append(
            B3SecurityRecord(
                ticker=ticker,
                isin=isin,
                security_type=security_type,
            )
        )

    return securities


def parse_listed_company_search(
    data: dict,
) -> list[B3ListedCompanySummary]:
    results = data.get("results") or []
    companies: list[B3ListedCompanySummary] = []

    for item in results:
        if not isinstance(item, dict):
            continue

        cvm_code = str(item.get("codeCVM") or "").strip()
        issuing_company = str(item.get("issuingCompany") or "").strip().upper()
        company_name = str(item.get("companyName") or "").strip()
        trading_name = str(item.get("tradingName") or "").strip()

        if not cvm_code:
            continue

        companies.append(
            B3ListedCompanySummary(
                cvm_code=cvm_code,
                issuing_company=issuing_company,
                company_name=company_name,
                trading_name=trading_name,
            )
        )

    return companies


def rank_ticker_discovery_candidates(
    ticker: str,
    candidates: list[B3ListedCompanySummary],
) -> list[B3ListedCompanySummary]:
    prefix = ticker.strip().upper()[:4]

    def sort_key(item: B3ListedCompanySummary) -> tuple[int, str]:
        issuing = item.issuing_company.strip().upper()
        if issuing == prefix:
            rank = 0
        elif issuing.startswith(prefix) or prefix.startswith(issuing):
            rank = 1
        else:
            rank = 2
        return (rank, item.company_name)

    return sorted(candidates, key=sort_key)


class B3Client:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.http_client = http_client

    async def get_company_securities(
        self,
        cvm_code: str,
    ) -> list[B3SecurityRecord]:
        payload = {
            "codeCVM": cvm_code.strip(),
            "language": "pt-br",
        }

        encoded_payload = self._encode_payload(payload)
        response = await self._get(f"{B3_COMPANY_DETAIL_URL}/{encoded_payload}")
        return parse_company_securities(response.json())

    async def search_listed_companies(
        self,
        query: str,
    ) -> list[B3ListedCompanySummary]:
        payload = {
            "language": "pt-br",
            "pageNumber": 1,
            "pageSize": 20,
            "company": query.strip().upper(),
        }
        encoded_payload = self._encode_payload(payload)
        response = await self._get(
            f"{B3_INITIAL_COMPANIES_URL}/{encoded_payload}",
        )
        if not response.content:
            return []

        return parse_listed_company_search(response.json())

    async def discover_ticker_issuer(
        self,
        ticker: str,
    ) -> B3TickerIssuer | None:
        normalized = ticker.strip().upper()
        candidates = rank_ticker_discovery_candidates(
            normalized,
            await self.search_listed_companies(normalized),
        )

        for candidate in candidates:
            securities = await self.get_company_securities(candidate.cvm_code)
            if any(item.ticker == normalized for item in securities):
                return B3TickerIssuer(
                    ticker=normalized,
                    cvm_code=normalize_cvm_code(candidate.cvm_code),
                    issuing_company=candidate.issuing_company,
                    company_name=candidate.company_name,
                    trading_name=candidate.trading_name,
                )

        return None

    async def _get(self, url: str) -> httpx.Response:
        last_error: httpx.TransportError | None = None
        for attempt in range(B3_TRANSPORT_RETRIES):
            try:
                response = await self.http_client.get(
                    url,
                    timeout=B3_LISTED_TIMEOUT,
                )
                response.raise_for_status()
                return response
            except httpx.TransportError as exc:
                last_error = exc
                if attempt == B3_TRANSPORT_RETRIES - 1:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
        assert last_error is not None
        raise last_error

    @staticmethod
    def _encode_payload(payload: dict) -> str:
        raw = json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()

        return base64.b64encode(raw).decode()
