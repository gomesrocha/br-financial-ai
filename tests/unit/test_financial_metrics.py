from br_financial_ai.domain.financial_metrics import (
    get_financial_metric,
)


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
