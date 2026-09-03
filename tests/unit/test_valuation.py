from decimal import Decimal

import pytest

from br_financial_ai.domain.valuation import (
    AnnualAmounts,
    compute_valuation_metrics,
    cvm_amount_to_brl,
    margin,
    price_to_earnings,
    price_to_sales,
)

AMOUNTS = AnnualAmounts(
    revenue=Decimal("1000"),
    gross_profit=Decimal("400"),
    operating_result=Decimal("200"),
    net_income=Decimal("100"),
)


def test_cvm_mil_normalizes_to_brl() -> None:
    assert cvm_amount_to_brl(
        Decimal("169.0000000000"),
        "MIL",
    ) == Decimal("169000.0000000000")


def test_cvm_unidade_stays_in_brl() -> None:
    assert cvm_amount_to_brl(Decimal("100"), "UNIDADE") == Decimal("100")


def test_unsupported_currency_scale_raises() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported CVM currency scale",
    ):
        cvm_amount_to_brl(Decimal("1"), "BILHAO")


def test_margins() -> None:
    metrics = compute_valuation_metrics(
        ticker="petr4",
        reference_year=2025,
        amounts=AMOUNTS,
        market_cap=Decimal("2000"),
        quote_currency="BRL",
    )

    assert metrics.ticker == "PETR4"
    assert metrics.gross_margin == Decimal("0.4")
    assert metrics.operating_margin == Decimal("0.2")
    assert metrics.net_margin == Decimal("0.1")
    assert metrics.price_to_sales == Decimal("2")
    assert metrics.price_to_earnings == Decimal("20")


def test_zero_revenue_skips_margins_and_price_to_sales() -> None:
    metrics = compute_valuation_metrics(
        ticker="PETR4",
        reference_year=2025,
        amounts=AnnualAmounts(
            revenue=Decimal("0"),
            gross_profit=Decimal("10"),
            operating_result=Decimal("5"),
            net_income=Decimal("2"),
        ),
        market_cap=Decimal("1000"),
        quote_currency="BRL",
    )

    assert metrics.gross_margin is None
    assert metrics.operating_margin is None
    assert metrics.net_margin is None
    assert metrics.price_to_sales is None
    assert metrics.price_to_earnings == Decimal("500")


def test_negative_income_keeps_net_margin_and_skips_pe() -> None:
    metrics = compute_valuation_metrics(
        ticker="PETR4",
        reference_year=2025,
        amounts=AnnualAmounts(
            revenue=Decimal("100"),
            gross_profit=Decimal("20"),
            operating_result=Decimal("-5"),
            net_income=Decimal("-10"),
        ),
        market_cap=Decimal("1000"),
        quote_currency="BRL",
    )

    assert metrics.net_margin == Decimal("-0.1")
    assert metrics.operating_margin == Decimal("-0.05")
    assert metrics.price_to_earnings is None


def test_zero_income_skips_pe() -> None:
    assert (
        price_to_earnings(
            Decimal("1000"),
            Decimal("0"),
        )
        is None
    )


def test_missing_optional_values() -> None:
    metrics = compute_valuation_metrics(
        ticker="PETR4",
        reference_year=2025,
        amounts=AnnualAmounts(
            revenue=None,
            gross_profit=None,
            operating_result=None,
            net_income=None,
        ),
        market_cap=None,
        quote_currency="BRL",
    )

    assert metrics.gross_margin is None
    assert metrics.price_to_sales is None
    assert metrics.price_to_earnings is None
    assert metrics.market_cap is None


def test_price_to_sales_formula() -> None:
    assert price_to_sales(Decimal("2000"), Decimal("1000")) == Decimal("2")


def test_margin_formula() -> None:
    assert margin(Decimal("40"), Decimal("100")) == Decimal("0.4")
    assert margin(Decimal("40"), Decimal("0")) is None
    assert margin(None, Decimal("100")) is None


def test_non_brl_quote_skips_market_multiples() -> None:
    metrics = compute_valuation_metrics(
        ticker="PETR4",
        reference_year=2025,
        amounts=AMOUNTS,
        market_cap=Decimal("2000"),
        quote_currency="USD",
    )

    assert metrics.market_cap is None
    assert metrics.price_to_sales is None
    assert metrics.price_to_earnings is None
    assert metrics.gross_margin == Decimal("0.4")


def test_mil_to_brl_price_to_sales() -> None:
    revenue_brl = cvm_amount_to_brl(Decimal("100"), "MIL")
    market_cap = Decimal("200000")

    assert revenue_brl == Decimal("100000")
    assert price_to_sales(market_cap, revenue_brl) == Decimal("2")


def test_bank_amounts_do_not_turn_unsupported_margins_into_zero() -> None:
    metrics = compute_valuation_metrics(
        ticker="ITUB4",
        reference_year=2025,
        amounts=AnnualAmounts(
            revenue=None,
            gross_profit=None,
            operating_result=None,
            net_income=Decimal("45849000000"),
        ),
        market_cap=Decimal("300000000000"),
        quote_currency="BRL",
    )

    assert metrics.net_income == Decimal("45849000000")
    assert metrics.gross_margin is None
    assert metrics.operating_margin is None
    assert metrics.net_margin is None
    assert metrics.price_to_sales is None
    assert metrics.price_to_earnings is not None
    assert metrics.gross_margin != 0
    assert metrics.price_to_sales != 0
