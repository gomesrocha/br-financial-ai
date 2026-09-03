from datetime import date

import pytest

from br_financial_ai.services.financial_query import (
    annual_period,
    quarter_period,
)


@pytest.mark.parametrize(
    ("quarter", "expected_start", "expected_end"),
    [
        (
            1,
            date(2026, 1, 1),
            date(2026, 3, 31),
        ),
        (
            2,
            date(2026, 4, 1),
            date(2026, 6, 30),
        ),
        (
            3,
            date(2026, 7, 1),
            date(2026, 9, 30),
        ),
        (
            4,
            date(2026, 10, 1),
            date(2026, 12, 31),
        ),
    ],
)
def test_quarter_period(
    quarter: int,
    expected_start: date,
    expected_end: date,
) -> None:
    assert quarter_period(
        2026,
        quarter,
    ) == (
        expected_start,
        expected_end,
    )


def test_reject_invalid_quarter() -> None:
    with pytest.raises(
        ValueError,
        match="Quarter must be between 1 and 4",
    ):
        quarter_period(
            2026,
            5,
        )


def test_annual_period() -> None:
    assert annual_period(2025) == (
        date(2025, 1, 1),
        date(2025, 12, 31),
    )
