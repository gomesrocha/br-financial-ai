from br_financial_ai.domain.financial_metrics import (
    get_financial_metric,
    is_context_metric_supported,
    list_supported_metrics,
    list_unsupported_context_metrics,
    supports_metric,
)
from br_financial_ai.domain.financial_profile import FinancialProfile


def test_get_revenue_metric() -> None:
    metric = get_financial_metric("revenue")

    assert metric is not None
    assert metric.statement_type == "DRE"
    assert metric.account_code == "3.01"
    assert metric.scope == "CONSOLIDATED"


def test_metric_lookup_normalizes_key() -> None:
    metric = get_financial_metric("  NET_INCOME  ")

    assert metric is not None
    assert metric.account_code == "3.11"


def test_unknown_metric_returns_none() -> None:
    assert get_financial_metric("unknown_metric") is None


def test_metric_aliases_map_to_canonical_keys() -> None:
    gross = get_financial_metric("gross_income")
    operating = get_financial_metric("operational_result")

    assert gross is not None
    assert gross.key == "gross_profit"
    assert operating is not None
    assert operating.key == "operating_result"


def test_non_financial_mappings_unchanged() -> None:
    expected = {
        "revenue": "3.01",
        "gross_profit": "3.03",
        "operating_result": "3.05",
        "profit_before_tax": "3.07",
        "net_income": "3.11",
    }

    for key, code in expected.items():
        metric = get_financial_metric(key, FinancialProfile.NON_FINANCIAL)
        assert metric is not None
        assert metric.account_code == code
        assert supports_metric(FinancialProfile.NON_FINANCIAL, key)


def test_financial_institution_supported_mappings() -> None:
    net_income = get_financial_metric(
        "net_income",
        FinancialProfile.FINANCIAL_INSTITUTION,
    )
    intermediation = get_financial_metric(
        "financial_intermediation_revenue",
        FinancialProfile.FINANCIAL_INSTITUTION,
    )

    assert net_income is not None
    assert [item.account_code for item in net_income.selectors] == [
        "3.11",
        "3.09",
    ]
    assert intermediation is not None
    assert intermediation.account_code == "3.01"
    assert "net_income" in list_supported_metrics(
        FinancialProfile.FINANCIAL_INSTITUTION,
    )


def test_unsupported_industrial_metrics_are_explicit_for_banks() -> None:
    profile = FinancialProfile.FINANCIAL_INSTITUTION

    assert supports_metric(profile, "revenue") is False
    assert supports_metric(profile, "gross_profit") is False
    assert supports_metric(profile, "operating_result") is False
    assert get_financial_metric("revenue", profile) is None
    assert is_context_metric_supported(profile, "gross_margin") is False
    assert "gross_profit" in list_unsupported_context_metrics(profile)
    assert "price_to_sales" in list_unsupported_context_metrics(profile)
    assert "net_income" not in list_unsupported_context_metrics(profile)
    assert "price_to_earnings" not in list_unsupported_context_metrics(
        profile,
    )


def test_catalogue_selection_depends_on_profile() -> None:
    industrial = get_financial_metric("net_income")
    bank = get_financial_metric(
        "net_income",
        FinancialProfile.FINANCIAL_INSTITUTION,
    )

    assert industrial is not None
    assert bank is not None
    assert industrial.selectors != bank.selectors
    assert (
        get_financial_metric(
            "financial_intermediation_revenue",
            FinancialProfile.NON_FINANCIAL,
        )
        is None
    )
