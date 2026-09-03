from datetime import UTC, datetime
from decimal import Decimal

import pytest

from br_financial_ai.clients.yahoo import to_yahoo_symbol
from br_financial_ai.clients.yahoo_market import (
    MarketDataNotFoundError,
    YahooMarketClient,
    YahooMarketProviderError,
    parse_market_quote,
    parse_price_bar,
)
from br_financial_ai.domain.market import MarketQuote, PriceBar

QUOTE_TIMESTAMP = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_market_client_reuses_yahoo_b3_symbol() -> None:
    captured: dict[str, object] = {}

    def fetch_quote(symbol: str) -> dict[str, object]:
        captured["symbol"] = symbol
        return {
            "price": "46.87",
            "previous_close": "45.02",
            "currency": "BRL",
            "timestamp": QUOTE_TIMESTAMP,
        }

    client = YahooMarketClient(fetch_quote=fetch_quote)
    quote = await client.get_quote("  petr4  ")

    assert captured["symbol"] == "PETR4.SA"
    assert captured["symbol"] == to_yahoo_symbol("PETR4")
    assert quote.ticker == "PETR4"
    assert quote.symbol == "PETR4.SA"


def test_parse_quote_uses_decimal_and_timezone() -> None:
    quote = parse_market_quote(
        "PETR4",
        "PETR4.SA",
        {
            "price": 46.87,
            "previous_close": 45.02,
            "currency": "BRL",
            "timestamp": QUOTE_TIMESTAMP,
        },
    )

    assert quote == MarketQuote(
        ticker="PETR4",
        symbol="PETR4.SA",
        price=Decimal("46.87"),
        previous_close=Decimal("45.02"),
        currency="BRL",
        timestamp=QUOTE_TIMESTAMP,
    )
    assert quote.timestamp.tzinfo is not None


def test_parse_quote_includes_market_cap() -> None:
    quote = parse_market_quote(
        "PETR4",
        "PETR4.SA",
        {
            "price": 46.87,
            "previous_close": 45.02,
            "currency": "BRL",
            "timestamp": QUOTE_TIMESTAMP,
            "market_cap": 400000000000,
        },
    )

    assert quote is not None
    assert quote.market_cap == Decimal("400000000000")


def test_parse_quote_market_cap_optional() -> None:
    quote = parse_market_quote(
        "PETR4",
        "PETR4.SA",
        {
            "price": 46.87,
            "previous_close": 45.02,
            "currency": "BRL",
            "timestamp": QUOTE_TIMESTAMP,
        },
    )

    assert quote is not None
    assert quote.market_cap is None


def test_parse_price_bar_converts_decimal() -> None:
    bar = parse_price_bar(
        "PETR4",
        {
            "timestamp": datetime(2026, 8, 3, tzinfo=UTC),
            "open": 41.11,
            "high": 41.78,
            "low": 41.06,
            "close": 41.74,
            "volume": 24400900,
        },
    )

    assert bar is not None
    assert bar.open == Decimal("41.11")
    assert bar.close == Decimal("41.74")
    assert bar.volume == 24400900
    assert bar.timestamp.tzinfo is not None


@pytest.mark.asyncio
async def test_price_history_is_ordered() -> None:
    later = datetime(2026, 8, 10, tzinfo=UTC)
    earlier = datetime(2026, 8, 3, tzinfo=UTC)

    def fetch_history(symbol: str, period: str) -> list[dict[str, object]]:
        assert symbol == "PETR4.SA"
        assert period == "1mo"
        return [
            {
                "timestamp": later,
                "open": "12",
                "high": "12",
                "low": "12",
                "close": "12",
                "volume": 1,
            },
            {
                "timestamp": earlier,
                "open": "10",
                "high": "10",
                "low": "10",
                "close": "10",
                "volume": 1,
            },
        ]

    client = YahooMarketClient(fetch_history=fetch_history)
    bars = await client.get_price_history("PETR4", period="1mo")

    assert [bar.timestamp for bar in bars] == [earlier, later]
    assert [bar.close for bar in bars] == [Decimal("10"), Decimal("12")]


@pytest.mark.asyncio
async def test_price_history_skips_malformed_bars() -> None:
    def fetch_history(symbol: str, period: str) -> list[object]:
        return [
            {
                "timestamp": datetime(2026, 8, 3, tzinfo=UTC),
                "open": "10",
                "high": "11",
                "low": "9",
                "close": "10.5",
                "volume": 100,
            },
            {"timestamp": datetime(2026, 8, 4, tzinfo=UTC), "close": "11"},
            "not-a-bar",
        ]

    client = YahooMarketClient(fetch_history=fetch_history)
    bars = await client.get_price_history("PETR4", period="1mo")

    assert len(bars) == 1
    assert isinstance(bars[0], PriceBar)
    assert bars[0].close == Decimal("10.5")


@pytest.mark.asyncio
async def test_price_history_empty_result() -> None:
    client = YahooMarketClient(fetch_history=lambda symbol, period: [])

    bars = await client.get_price_history("PETR4", period="3mo")

    assert bars == []


@pytest.mark.asyncio
async def test_quote_provider_failure() -> None:
    def fetch_quote(symbol: str) -> dict[str, object]:
        raise RuntimeError("yahoo down")

    client = YahooMarketClient(fetch_quote=fetch_quote)

    with pytest.raises(
        YahooMarketProviderError,
        match="Failed to fetch Yahoo quote for PETR4.SA",
    ):
        await client.get_quote("PETR4")


@pytest.mark.asyncio
async def test_quote_not_found() -> None:
    client = YahooMarketClient(
        fetch_quote=lambda symbol: {"currency": "BRL"},
    )

    with pytest.raises(MarketDataNotFoundError, match="PETR4"):
        await client.get_quote("PETR4")


@pytest.mark.asyncio
async def test_invalid_ticker_is_rejected() -> None:
    client = YahooMarketClient(fetch_quote=lambda symbol: {})

    with pytest.raises(ValueError, match="Unsupported ticker"):
        await client.get_quote("AAPL")
