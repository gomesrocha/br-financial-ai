import csv
from datetime import date, timedelta
from io import StringIO

import httpx

from br_financial_ai.domain.ticker_discovery import InstrumentEquityRecord

B3_INSTRUMENTS_REQUEST_URL = "https://arquivos.b3.com.br/api/download/requestname"
B3_INSTRUMENTS_DOWNLOAD_URL = "https://arquivos.b3.com.br/api/download/"
B3_INSTRUMENTS_FILE_NAME = "InstrumentsConsolidated"
B3_INSTRUMENTS_LOOKBACK_DAYS = 5
B3_INSTRUMENTS_TIMEOUT = httpx.Timeout(
    connect=5.0,
    read=60.0,
    write=15.0,
    pool=5.0,
)


class B3InstrumentsClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        as_of: date | None = None,
    ) -> None:
        self.http_client = http_client
        self._as_of = as_of

    async def get_equity_records(self) -> list[InstrumentEquityRecord]:
        content, _used_date = await self.download_latest()
        return parse_instruments_consolidated(content)

    async def download_latest(self) -> tuple[bytes, date]:
        last_error: Exception | None = None
        as_of = self._as_of or datetime_today()
        for offset in range(B3_INSTRUMENTS_LOOKBACK_DAYS):
            day = as_of - timedelta(days=offset)
            try:
                return await self._download_for_date(day), day
            except httpx.HTTPError as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        raise httpx.HTTPError("InstrumentsConsolidated file is unavailable.")

    async def _download_for_date(self, day: date) -> bytes:
        response = await self.http_client.get(
            B3_INSTRUMENTS_REQUEST_URL,
            params={
                "fileName": B3_INSTRUMENTS_FILE_NAME,
                "date": day.isoformat(),
            },
            timeout=B3_INSTRUMENTS_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        token = str(payload.get("token") or "").strip()
        if not token:
            raise httpx.HTTPError(
                f"InstrumentsConsolidated token missing for {day.isoformat()}."
            )

        download = await self.http_client.get(
            B3_INSTRUMENTS_DOWNLOAD_URL,
            params={"token": token},
            timeout=B3_INSTRUMENTS_TIMEOUT,
        )
        download.raise_for_status()
        if not download.content:
            raise httpx.HTTPError(
                f"InstrumentsConsolidated file empty for {day.isoformat()}."
            )
        return download.content


def parse_instruments_consolidated(content: bytes) -> list[InstrumentEquityRecord]:
    text = _decode(content)
    reader = csv.DictReader(
        StringIO(_csv_body(text)),
        delimiter=";",
    )
    records: list[InstrumentEquityRecord] = []
    if reader.fieldnames is None:
        return records

    for row in reader:
        ticker = (row.get("TckrSymb") or "").strip().upper()
        isin = (row.get("ISIN") or "").strip().upper()
        if not ticker:
            continue
        records.append(
            InstrumentEquityRecord(
                ticker=ticker,
                asset=(row.get("Asst") or "").strip().upper(),
                isin=isin,
                security_type=(row.get("CFICd") or "").strip().upper(),
                corporation_name=(row.get("CrpnNm") or "").strip(),
                segment=(row.get("SgmtNm") or "").strip().upper(),
                category=(row.get("SctyCtgyNm") or "").strip().upper(),
            )
        )
    return records


def _csv_body(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if "TckrSymb" in line:
            return "\n".join(lines[index:])
    return text


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("latin-1")


def datetime_today() -> date:
    return date.today()
