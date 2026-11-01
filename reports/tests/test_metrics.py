from datetime import date

import pandas as pd
import pytest
from app import metrics


def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "month": [date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)],
            "income": [300.0, 600.0, 900.0, 1000.0],
            "expense": [100.0, 200.0, 300.0, 400.0],
        }
    )


@pytest.mark.parametrize(
    ("income", "expense", "expected"),
    [(1000, 400, 60.0), (0, 400, None), (None, None, None), (300, 400, -33.3)],
)
def test_savings_rate(income, expense, expected):
    assert metrics.savings_rate(income, expense) == expected


def test_months_shift_across_years():
    assert metrics.shift_month(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert metrics.shift_month(date(2026, 11, 1), 3) == date(2027, 2, 1)


def test_comparison_has_three_periods():
    this_month, last_month, average = metrics.comparison(frame(), date(2026, 10, 1))

    assert (this_month["income"], this_month["expense"]) == (1000.0, 400.0)
    assert (last_month["income"], last_month["expense"]) == (900.0, 300.0)
    assert (average["income"], average["expense"]) == (600.0, 200.0)


def test_average_leaves_out_the_current_month():
    assert metrics.closed_average(frame(), date(2026, 9, 1))["income"] == 450.0


def test_missing_month_stays_empty():
    assert metrics.comparison(frame(), date(2027, 3, 1))[0] == {
        "period": "Ez a hónap", "income": None, "expense": None,
    }
