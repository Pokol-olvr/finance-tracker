import pytest
from app import format as fmt


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1148, "1 148 Ft"), (0, "0 Ft"), (-364991, "-364 991 Ft"), (None, "–"), (float("nan"), "–")],
)
def test_money_uses_spaces(value, expected):
    assert fmt.money(value) == expected


def test_percent_uses_a_decimal_comma():
    assert fmt.percent(12.5) == "12,5%"


@pytest.mark.parametrize(
    ("amount", "unit", "expected"),
    [(2.0, "DB", "2 DB"), (0.82, "KG", "0,82 KG"), (None, None, "–"), (1.0, None, "1")],
)
def test_quantity(amount, unit, expected):
    assert fmt.quantity(amount, unit) == expected


def test_shared_payer_has_a_name():
    assert fmt.payer_label("shared") == "Közös kártya"
    assert fmt.payer_label("person_a") == "person_a"
