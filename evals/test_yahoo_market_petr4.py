from decimal import Decimal

import pytest

from br_financial_ai.clients.yahoo_market import YahooMarketClient
from br_financial_ai.domain.market import (
    compute_period_metrics,
    quote_price_change,
)

pytestmark = [pytest.mark.eval, pytest.mark.external, pytest.mark.yahoo]


@pytest.mark.asyncio
async def test_yahoo_market_returns_petr4_quote_and_history() -> None:
    client = YahooMarketClient()

    quote = await client.get_quote("PETR4")
    bars = await client.get_price_history("PETR4", period="1mo")

    assert quote.ticker == "PETR4"
    assert quote.symbol == "PETR4.SA"
    assert quote.currency == "BRL"
    assert quote.price > Decimal("0")
    assert quote.timestamp.tzinfo is not None

    assert bars
    assert bars == sorted(bars, key=lambda bar: bar.timestamp)
    assert bars[0].timestamp.tzinfo is not None
    assert isinstance(bars[0].close, Decimal)

    change = quote_price_change(quote)
    metrics = compute_period_metrics(bars, period="1mo")

    print(quote)
    print(change)
    print(f"bars={len(bars)} first={bars[0]} last={bars[-1]}")
    print(metrics)
