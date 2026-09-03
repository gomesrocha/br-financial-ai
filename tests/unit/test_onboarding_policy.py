from datetime import date

import pytest

from br_financial_ai.domain.onboarding import (
    financial_periods_for_onboarding,
    normalize_requested_ticker,
)


def test_normalize_requested_ticker_trims_and_uppercases() -> None:
    assert normalize_requested_ticker(" itub4 ") == "ITUB4"


def test_normalize_requested_ticker_strips_yahoo_suffix() -> None:
    assert normalize_requested_ticker("ITUB4.SA") == "ITUB4"


def test_normalize_requested_ticker_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_requested_ticker("ITAU")


def test_financial_periods_use_previous_dfp_and_current_itr() -> None:
    periods = financial_periods_for_onboarding(date(2026, 9, 2))

    assert [(item.document_type, item.year) for item in periods] == [
        ("DFP", 2025),
        ("ITR", 2026),
    ]
