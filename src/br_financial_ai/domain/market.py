from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

TRADING_DAYS_PER_YEAR = Decimal("252")


@dataclass(frozen=True, slots=True)
class MarketQuote:
    ticker: str
    symbol: str
    price: Decimal
    previous_close: Decimal | None
    currency: str
    timestamp: datetime
    market_cap: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PriceBar:
    ticker: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None


@dataclass(frozen=True, slots=True)
class PriceChange:
    absolute: Decimal | None
    percentage: Decimal | None


@dataclass(frozen=True, slots=True)
class MarketPeriodMetrics:
    period: str
    period_return: Decimal
    volatility: Decimal
    max_drawdown: Decimal


def quote_price_change(quote: MarketQuote) -> PriceChange:
    if quote.previous_close is None:
        return PriceChange(absolute=None, percentage=None)

    if quote.previous_close == 0:
        raise ValueError("Previous close must be non-zero.")

    return PriceChange(
        absolute=quote.price - quote.previous_close,
        percentage=(quote.price / quote.previous_close) - Decimal("1"),
    )


def period_return(bars: Sequence[PriceBar]) -> Decimal:
    ordered = _ordered_bars(bars)

    if len(ordered) < 2:
        raise ValueError("Price series must contain at least two bars.")

    initial = ordered[0].close
    current = ordered[-1].close

    if initial == 0:
        raise ValueError("Initial price must be non-zero.")

    return (current / initial) - Decimal("1")


def historical_volatility(bars: Sequence[PriceBar]) -> Decimal:
    """Annualized sample volatility of simple close-to-close returns.

    Daily simple return: ``(close_t / close_t-1) - 1``.
    Daily volatility is the sample standard deviation (n-1).
    Annualization uses ``sqrt(252)`` trading days.
    """
    ordered = _ordered_bars(bars)

    if len(ordered) < 3:
        raise ValueError("Price series must contain at least three bars.")

    returns = _simple_returns(ordered)
    mean = sum(returns, start=Decimal("0")) / Decimal(len(returns))
    variance = sum((item - mean) ** 2 for item in returns) / Decimal(len(returns) - 1)
    daily = variance.sqrt()

    return daily * TRADING_DAYS_PER_YEAR.sqrt()


def max_drawdown(bars: Sequence[PriceBar]) -> Decimal:
    ordered = _ordered_bars(bars)

    if not ordered:
        raise ValueError("Price series is empty.")

    peak = ordered[0].close
    worst = Decimal("0")

    for bar in ordered:
        if bar.close > peak:
            peak = bar.close

        if peak == 0:
            raise ValueError("Peak price must be non-zero.")

        drawdown = (bar.close / peak) - Decimal("1")

        if drawdown < worst:
            worst = drawdown

    return worst


def compute_period_metrics(
    bars: Sequence[PriceBar],
    *,
    period: str,
) -> MarketPeriodMetrics:
    return MarketPeriodMetrics(
        period=period,
        period_return=period_return(bars),
        volatility=historical_volatility(bars),
        max_drawdown=max_drawdown(bars),
    )


def _ordered_bars(bars: Sequence[PriceBar]) -> list[PriceBar]:
    return sorted(bars, key=lambda bar: bar.timestamp)


def _simple_returns(ordered: Sequence[PriceBar]) -> list[Decimal]:
    returns: list[Decimal] = []

    for previous, current in zip(ordered[:-1], ordered[1:], strict=True):
        if previous.close == 0:
            raise ValueError("Price must be non-zero to compute returns.")

        returns.append((current.close / previous.close) - Decimal("1"))

    return returns
