import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from br_financial_ai.clients.yahoo import (
    to_b3_ticker,
    to_yahoo_symbol,
)
from br_financial_ai.domain.market import MarketQuote, PriceBar

SUPPORTED_HISTORY_PERIODS = frozenset({"1mo", "3mo", "6mo", "1y"})

QuoteFetcher = Callable[[str], Mapping[str, object]]
HistoryFetcher = Callable[[str, str], Sequence[object]]


class YahooMarketProviderError(Exception):
    pass


class MarketDataNotFoundError(Exception):
    pass


def fetch_yahoo_quote(symbol: str) -> dict[str, object]:
    from yfinance import Ticker

    info = Ticker(symbol).fast_info

    return {
        "price": info.last_price,
        "previous_close": info.previous_close,
        "currency": info.currency,
        "timestamp": datetime.now(UTC),
        "market_cap": _fast_info_value(info, "market_cap", "marketCap"),
    }


def fetch_yahoo_history(symbol: str, period: str) -> list[dict[str, object]]:
    from yfinance import Ticker

    frame = Ticker(symbol).history(
        period=period,
        interval="1d",
        auto_adjust=True,
    )

    rows: list[dict[str, object]] = []

    for index, row in frame.iterrows():
        timestamp = index.to_pydatetime() if hasattr(index, "to_pydatetime") else index
        volume = row.get("Volume")

        rows.append(
            {
                "timestamp": timestamp,
                "open": row.get("Open"),
                "high": row.get("High"),
                "low": row.get("Low"),
                "close": row.get("Close"),
                "volume": None if _is_missing_number(volume) else volume,
            }
        )

    return rows


def parse_market_quote(
    ticker: str,
    symbol: str,
    payload: object,
) -> MarketQuote | None:
    if not isinstance(payload, Mapping):
        return None

    price = _to_decimal(payload.get("price"))

    if price is None:
        return None

    currency = _optional_text(payload.get("currency")) or "BRL"
    timestamp = _to_aware_datetime(payload.get("timestamp"))

    if timestamp is None:
        return None

    return MarketQuote(
        ticker=ticker,
        symbol=symbol,
        price=price,
        previous_close=_to_decimal(payload.get("previous_close")),
        currency=currency,
        timestamp=timestamp,
        market_cap=_to_decimal(payload.get("market_cap")),
    )


def parse_price_bar(
    ticker: str,
    payload: object,
) -> PriceBar | None:
    if not isinstance(payload, Mapping):
        return None

    timestamp = _to_aware_datetime(payload.get("timestamp"))
    open_price = _to_decimal(payload.get("open"))
    high = _to_decimal(payload.get("high"))
    low = _to_decimal(payload.get("low"))
    close = _to_decimal(payload.get("close"))

    if (
        timestamp is None
        or open_price is None
        or high is None
        or low is None
        or close is None
    ):
        return None

    return PriceBar(
        ticker=ticker,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=_to_int(payload.get("volume")),
    )


class YahooMarketClient:
    def __init__(
        self,
        fetch_quote: QuoteFetcher | None = None,
        fetch_history: HistoryFetcher | None = None,
    ) -> None:
        self._fetch_quote = fetch_quote or fetch_yahoo_quote
        self._fetch_history = fetch_history or fetch_yahoo_history

    async def get_quote(self, ticker: str) -> MarketQuote:
        symbol = to_yahoo_symbol(ticker)
        b3_ticker = to_b3_ticker(ticker)

        try:
            payload = await asyncio.to_thread(self._fetch_quote, symbol)
        except YahooMarketProviderError:
            raise
        except Exception as exc:
            raise YahooMarketProviderError(
                f"Failed to fetch Yahoo quote for {symbol}."
            ) from exc

        quote = parse_market_quote(b3_ticker, symbol, payload)

        if quote is None:
            raise MarketDataNotFoundError(b3_ticker)

        return quote

    async def get_price_history(
        self,
        ticker: str,
        *,
        period: str,
    ) -> list[PriceBar]:
        if period not in SUPPORTED_HISTORY_PERIODS:
            raise ValueError(f"Unsupported period: {period}")

        symbol = to_yahoo_symbol(ticker)
        b3_ticker = to_b3_ticker(ticker)

        try:
            payload = await asyncio.to_thread(
                self._fetch_history,
                symbol,
                period,
            )
        except YahooMarketProviderError:
            raise
        except Exception as exc:
            raise YahooMarketProviderError(
                f"Failed to fetch Yahoo history for {symbol}."
            ) from exc

        if payload is None:
            return []

        if not isinstance(payload, list | tuple):
            raise YahooMarketProviderError(
                f"Unexpected Yahoo history payload for {symbol}."
            )

        bars: list[PriceBar] = []

        for item in payload:
            bar = parse_price_bar(b3_ticker, item)

            if bar is not None:
                bars.append(bar)

        return sorted(bars, key=lambda item: item.timestamp)


def _fast_info_value(info: object, *names: str) -> object:
    for name in names:
        value = getattr(info, name, None)

        if value is not None:
            return value

        getter = getattr(info, "get", None)

        if callable(getter):
            value = getter(name)

            if value is not None:
                return value

    return None


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    text = value.strip()

    return text or None


def _is_missing_number(value: object) -> bool:
    if value is None:
        return True

    if isinstance(value, float) and value != value:
        return True

    return False


def _to_decimal(value: object) -> Decimal | None:
    if _is_missing_number(value):
        return None

    raw = value.item() if hasattr(value, "item") else value

    if isinstance(raw, Decimal):
        return raw

    try:
        if isinstance(raw, float):
            return Decimal(str(raw))

        return Decimal(str(raw))
    except (InvalidOperation, ValueError, ArithmeticError):
        return None


def _to_int(value: object) -> int | None:
    if _is_missing_number(value):
        return None

    raw = value.item() if hasattr(value, "item") else value

    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _to_aware_datetime(value: object) -> datetime | None:
    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value
