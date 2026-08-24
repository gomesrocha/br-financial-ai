from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MonitoredCompany:
    name: str
    legal_name: str
    tickers: tuple[str, ...]


MONITORED_COMPANIES = (
    MonitoredCompany(
        name="Petrobras",
        legal_name="Petróleo Brasileiro S.A. - Petrobras",
        tickers=("PETR3", "PETR4"),
    ),
    MonitoredCompany(
        name="Bradesco",
        legal_name="Banco Bradesco S.A.",
        tickers=("BBDC3", "BBDC4"),
    ),
    MonitoredCompany(
        name="Vale",
        legal_name="Vale S.A.",
        tickers=("VALE3",),
    ),
)


def find_company_by_ticker(ticker: str) -> MonitoredCompany | None:
    normalized_ticker = ticker.strip().upper()

    return next(
        (
            company
            for company in MONITORED_COMPANIES
            if normalized_ticker in company.tickers
        ),
        None,
    )
