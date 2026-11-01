from pathlib import Path

import pytest
from app.receipt_checks import run_checks, status_of
from app.receipt_parser import parse

RECEIPTS = Path(__file__).parent / "receipts"


def parsed(name: str) -> dict:
    return parse((RECEIPTS / f"{name}.txt").read_text(encoding="utf-8"))


def check(name: str, entered_date: str | None = None, seen: bool = False) -> tuple[dict, str]:
    result = parsed(name)
    checks = run_checks(result, entered_date, seen)
    return checks, status_of(result, checks)


@pytest.mark.parametrize(
    "name",
    [
        "two_line_cash",
        "price_below",
        "same_line_weighed",
        "noisy_reading",
        "name_ends_in_number",
        "value_first",
    ],
)
def test_all_sample_receipts_pass(name):
    checks, status = check(name)

    assert status == "ok", checks


def test_cash_rounding_is_tolerated():
    checks, _ = check("two_line_cash")

    assert checks["payment"] == {"ok": True, "paid": 1345}


def test_changed_price_needs_review():
    result = parsed("two_line_cash")
    result["items"][2]["value"] = 699

    checks = run_checks(result, None, False)

    assert checks["sum"] == {"ok": False, "expected": 1346, "actual": 1446}
    assert status_of(result, checks) == "review"


def test_wrong_line_total_needs_review():
    result = parsed("two_line_cash")
    result["items"][0]["unit_price"] = 299
    result["items"][0]["value"] = 597

    checks = run_checks(result, None, False)

    assert checks["line_total"]["wrong_lines"] == 1
    assert status_of(result, checks) == "review"


def test_line_total_allows_rounding_of_weighed_items():
    assert check("same_line_weighed")[0]["line_total"]["ok"] is True


def test_different_entered_date_needs_review():
    checks, status = check("two_line_cash", entered_date="2026-12-13")

    assert checks["date"]["ok"] is False
    assert status == "review"


def test_same_entered_date_passes():
    assert check("two_line_cash", entered_date="2026-12-14")[0]["date"]["ok"] is True


def test_missing_date_is_skipped():
    assert check("two_line_cash")[0]["date"] == {"ok": None}


def test_rephotographed_receipt_needs_review():
    checks, status = check("two_line_cash", seen=True)

    assert checks["duplicate"]["ok"] is False
    assert status == "review"


def test_duplicate_check_needs_tax_and_receipt_number():
    assert check("noisy_reading", seen=True)[0]["duplicate"] == {"ok": None}


def test_card_payment_has_no_rounding_tolerance():
    result = parsed("name_ends_in_number")
    result["payments"][0]["amount"] = 1046

    assert run_checks(result, None, False)["payment"]["ok"] is False


def test_payment_is_skipped_without_payment_lines():
    result = parsed("name_ends_in_number")
    result["payments"] = []

    assert run_checks(result, None, False)["payment"] == {"ok": None}


def test_receipt_without_items_or_total_is_unparsed():
    result = parse("semmi hasznos")

    assert status_of(result, run_checks({**result, "total": None}, None, False)) == "unparsed"
