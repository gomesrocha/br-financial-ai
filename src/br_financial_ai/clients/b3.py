import base64
import json
import re
from dataclasses import dataclass

import httpx

B3_COMPANY_DETAIL_URL = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesProxy/CompanyCall/GetDetail"
)

EQUITY_TICKER_PATTERN = re.compile(r"^[A-Z]{4}[3-8]$")


@dataclass(frozen=True, slots=True)
class B3SecurityRecord:
    ticker: str
    isin: str
    security_type: str


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

        response = await self.http_client.get(
            f"{B3_COMPANY_DETAIL_URL}/{encoded_payload}",
        )

        response.raise_for_status()

        return parse_company_securities(response.json())

    @staticmethod
    def _encode_payload(payload: dict) -> str:
        raw = json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()

        return base64.b64encode(raw).decode()
