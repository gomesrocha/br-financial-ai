from datetime import UTC, datetime
from decimal import Decimal

import pytest

from br_financial_ai.domain.market import (
    TRADING_DAYS_PER_YEAR,
    MarketQuote,
    PriceBar,
    historical_volatility,
    max_drawdown,
    period_return,
    quote_price_change,
)


def _bar(
    close: str,
    *,
    day: int,
    ticker: str = "PETR4",
) -> PriceBar:
    price = Decimal(close)

    return PriceBar(
        ticker=ticker,
        timestamp=datetime(2026, 8, day, tzinfo=UTC),
        open=price,
        high=price,
        low=price,
        close=price,
        volume=1000,
    )


def test_period_return() -> None:
    bars = [_bar("10", day=1), _bar("12", day=2)]

    assert period_return(bars) == Decimal("0.2")


def test_zero_return() -> None:
    bars = [_bar("10", day=1), _bar("10", day=3)]

    assert period_return(bars) == Decimal("0")


def test_negative_return() -> None:
    bars = [_bar("10", day=1), _bar("8", day=2)]

    assert period_return(bars) == Decimal("-0.2")


def test_period_return_uses_ordered_timestamps() -> None:
    later = _bar("12", day=10)
    earlier = _bar("10", day=1)

    assert period_return([later, earlier]) == Decimal("0.2")


def test_empty_series_return_raises() -> None:
    with pytest.raises(ValueError, match="at least two bars"):
        period_return([])

    with pytest.raises(ValueError, match="at least two bars"):
        period_return([_bar("10", day=1)])


def test_historical_volatility() -> None:
    bars = [_bar("10", day=1), _bar("12", day=2), _bar("9", day=3)]
    returns = [Decimal("0.2"), Decimal("-0.25")]
    mean = sum(returns, start=Decimal("0")) / Decimal("2")
    variance = sum((item - mean) ** 2 for item in returns) / Decimal("1")
    expected = variance.sqrt() * TRADING_DAYS_PER_YEAR.sqrt()

    assert historical_volatility(bars) == expected


def test_volatility_rejects_short_series() -> None:
    with pytest.raises(ValueError, match="at least three bars"):
        historical_volatility([_bar("10", day=1), _bar("12", day=2)])


def test_max_drawdown() -> None:
    bars = [
        _bar("10", day=1),
        _bar("12", day=2),
        _bar("9", day=3),
        _bar("11", day=4),
    ]

    assert max_drawdown(bars) == Decimal("9") / Decimal("12") - Decimal("1")


def test_max_drawdown_empty_series_raises() -> None:
    with pytest.raises(ValueError, match="Price series is empty"):
        max_drawdown([])


def test_quote_price_change() -> None:
    quote = MarketQuote(
        ticker="PETR4",
        symbol="PETR4.SA",
        price=Decimal("46.87"),
        previous_close=Decimal("45.02"),
        currency="BRL",
        timestamp=datetime(2026, 9, 1, tzinfo=UTC),
    )
    change = quote_price_change(quote)

    assert change.absolute == Decimal("1.85")
    assert change.percentage == (Decimal("46.87") / Decimal("45.02")) - Decimal("1")
