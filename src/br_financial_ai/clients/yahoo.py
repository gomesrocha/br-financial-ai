from br_financial_ai.clients.b3 import EQUITY_TICKER_PATTERN

YAHOO_B3_SUFFIX = ".SA"


def to_yahoo_symbol(ticker: str) -> str:
    normalized = ticker.strip().upper()

    if normalized.endswith(YAHOO_B3_SUFFIX):
        normalized = normalized[: -len(YAHOO_B3_SUFFIX)]

    if not EQUITY_TICKER_PATTERN.fullmatch(normalized):
        raise ValueError(f"Unsupported ticker: {ticker}")

    return f"{normalized}{YAHOO_B3_SUFFIX}"


def to_b3_ticker(ticker: str) -> str:
    return to_yahoo_symbol(ticker).removesuffix(YAHOO_B3_SUFFIX)
