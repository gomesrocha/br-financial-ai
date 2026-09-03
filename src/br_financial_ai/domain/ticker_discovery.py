import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from br_financial_ai.clients.b3 import classify_equity_ticker
from br_financial_ai.clients.cvm import CvmCompanyRecord
from br_financial_ai.utils.identifiers import normalize_cvm_code

CVM_ACTIVE_STATUS = "ATIVO"
PUNCTUATION_PATTERN = re.compile(r"[^\w\s]+", re.UNICODE)
WHITESPACE_PATTERN = re.compile(r"\s+")
CORPORATE_SA_PATTERN = re.compile(r"\bS\s+A\b")


class TickerDiscoverySource(StrEnum):
    LOCAL = "local"
    B3_LISTED_COMPANIES = "b3_listed_companies"
    B3_INSTRUMENTS_CONSOLIDATED = "b3_instruments_consolidated"


class TickerDiscoveryUnavailableError(Exception):
    pass


class TickerDiscoveryNotFoundError(Exception):
    pass


class TickerDiscoveryAmbiguousError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DiscoveredSecurity:
    ticker: str
    isin: str
    security_type: str


@dataclass(frozen=True, slots=True)
class TickerDiscoveryResult:
    requested_ticker: str
    cvm_code: str
    company_name: str
    securities: tuple[DiscoveredSecurity, ...]
    source: str


@dataclass(frozen=True, slots=True)
class InstrumentEquityRecord:
    ticker: str
    asset: str
    isin: str
    security_type: str
    corporation_name: str
    segment: str
    category: str


def normalize_company_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    alphanumeric = PUNCTUATION_PATTERN.sub(" ", without_marks.upper())
    collapsed = WHITESPACE_PATTERN.sub(" ", alphanumeric).strip()
    return CORPORATE_SA_PATTERN.sub("SA", collapsed)


def cash_share_security(
    ticker: str,
    isin: str,
) -> DiscoveredSecurity | None:
    security_type = classify_equity_ticker(ticker)
    normalized_isin = isin.strip().upper()
    if security_type is None or len(normalized_isin) != 12:
        return None
    return DiscoveredSecurity(
        ticker=ticker.strip().upper(),
        isin=normalized_isin,
        security_type=security_type,
    )


def is_cash_share_instrument(record: InstrumentEquityRecord) -> bool:
    return (
        record.segment.strip().upper() == "CASH"
        and record.category.strip().upper() == "SHARES"
        and cash_share_security(record.ticker, record.isin) is not None
    )


def match_cvm_company(
    corporation_name: str,
    companies: list[CvmCompanyRecord],
) -> CvmCompanyRecord:
    needle = normalize_company_name(corporation_name)
    if not needle:
        raise TickerDiscoveryNotFoundError(corporation_name)

    active_matches = [
        company
        for company in companies
        if company.status.strip().upper() == CVM_ACTIVE_STATUS
        and _names_equal(needle, company)
    ]
    if len(active_matches) == 1:
        return active_matches[0]
    if len(active_matches) > 1:
        raise TickerDiscoveryAmbiguousError(corporation_name)
    raise TickerDiscoveryNotFoundError(corporation_name)


def _names_equal(needle: str, company: CvmCompanyRecord) -> bool:
    return needle in {
        normalize_company_name(company.legal_name),
        normalize_company_name(company.trade_name),
    }


def securities_for_asset(
    requested_ticker: str,
    records: list[InstrumentEquityRecord],
) -> tuple[DiscoveredSecurity, ...]:
    requested = requested_ticker.strip().upper()
    matching = [
        record
        for record in records
        if is_cash_share_instrument(record) and record.ticker == requested
    ]
    if not matching:
        return ()

    asset = matching[0].asset.strip().upper()
    discovered: list[DiscoveredSecurity] = []
    seen: set[str] = set()
    for record in records:
        if record.asset.strip().upper() != asset:
            continue
        if not is_cash_share_instrument(record):
            continue
        security = cash_share_security(record.ticker, record.isin)
        if security is None or security.ticker in seen:
            continue
        seen.add(security.ticker)
        discovered.append(security)

    return tuple(sorted(discovered, key=lambda item: item.ticker))


def result_from_instrument_match(
    requested_ticker: str,
    records: list[InstrumentEquityRecord],
    companies: list[CvmCompanyRecord],
) -> TickerDiscoveryResult:
    securities = securities_for_asset(requested_ticker, records)
    if not securities:
        raise TickerDiscoveryNotFoundError(requested_ticker)

    requested = requested_ticker.strip().upper()
    instrument = next(
        (
            record
            for record in records
            if record.ticker.strip().upper() == requested
            and is_cash_share_instrument(record)
        ),
        None,
    )
    if instrument is None:
        raise TickerDiscoveryNotFoundError(requested_ticker)

    company = match_cvm_company(instrument.corporation_name, companies)
    return TickerDiscoveryResult(
        requested_ticker=requested,
        cvm_code=normalize_cvm_code(company.cvm_code),
        company_name=company.legal_name,
        securities=securities,
        source=TickerDiscoverySource.B3_INSTRUMENTS_CONSOLIDATED.value,
    )
