from dataclasses import dataclass
from decimal import Decimal

CVM_CURRENCY_SCALE_TO_BRL = {
    "MIL": Decimal("1000"),
    "UNIDADE": Decimal("1"),
}

BRL_CURRENCIES = frozenset({"BRL", "REAL", "R$"})

VALUATION_METRIC_KEYS = (
    "revenue",
    "gross_profit",
    "operating_result",
    "net_income",
)


@dataclass(frozen=True, slots=True)
class AnnualAmounts:
    """Annual DRE amounts expressed in BRL units, not CVM thousands."""

    revenue: Decimal | None
    gross_profit: Decimal | None
    operating_result: Decimal | None
    net_income: Decimal | None


@dataclass(frozen=True, slots=True)
class ValuationMetrics:
    """Deterministic valuation snapshot.

    Monetary fields are BRL units. CVM ``MIL`` values are multiplied by
    1,000 before ratios are calculated so they are comparable to Yahoo
    Finance market capitalization, which is also in BRL units.
    """

    ticker: str
    reference_year: int

    revenue: Decimal | None
    gross_profit: Decimal | None
    operating_result: Decimal | None
    net_income: Decimal | None

    gross_margin: Decimal | None
    operating_margin: Decimal | None
    net_margin: Decimal | None

    market_cap: Decimal | None
    price_to_sales: Decimal | None
    price_to_earnings: Decimal | None


def cvm_amount_to_brl(
    value: Decimal,
    currency_scale: str,
) -> Decimal:
    multiplier = CVM_CURRENCY_SCALE_TO_BRL.get(
        currency_scale.strip().upper(),
    )

    if multiplier is None:
        raise ValueError(
            f"Unsupported CVM currency scale: {currency_scale}",
        )

    return value * multiplier


def is_brl_currency(currency: str | None) -> bool:
    if currency is None:
        return False

    return currency.strip().upper() in BRL_CURRENCIES


def margin(
    numerator: Decimal | None,
    revenue: Decimal | None,
) -> Decimal | None:
    if numerator is None or revenue is None or revenue == 0:
        return None

    return numerator / revenue


def price_to_sales(
    market_cap: Decimal | None,
    revenue: Decimal | None,
) -> Decimal | None:
    if market_cap is None or market_cap <= 0 or revenue is None or revenue <= 0:
        return None

    return market_cap / revenue


def price_to_earnings(
    market_cap: Decimal | None,
    net_income: Decimal | None,
) -> Decimal | None:
    if market_cap is None or market_cap <= 0 or net_income is None or net_income <= 0:
        return None

    return market_cap / net_income


def compute_valuation_metrics(
    *,
    ticker: str,
    reference_year: int,
    amounts: AnnualAmounts,
    market_cap: Decimal | None,
    quote_currency: str | None,
) -> ValuationMetrics:
    usable_market_cap = market_cap if is_brl_currency(quote_currency) else None

    return ValuationMetrics(
        ticker=ticker.strip().upper(),
        reference_year=reference_year,
        revenue=amounts.revenue,
        gross_profit=amounts.gross_profit,
        operating_result=amounts.operating_result,
        net_income=amounts.net_income,
        gross_margin=margin(amounts.gross_profit, amounts.revenue),
        operating_margin=margin(
            amounts.operating_result,
            amounts.revenue,
        ),
        net_margin=margin(amounts.net_income, amounts.revenue),
        market_cap=usable_market_cap,
        price_to_sales=price_to_sales(
            usable_market_cap,
            amounts.revenue,
        ),
        price_to_earnings=price_to_earnings(
            usable_market_cap,
            amounts.net_income,
        ),
    )
