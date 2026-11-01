"""Kitalált blokkok: a saját blokkok szövege nem kerülhet a repóba."""

from pathlib import Path

import pytest
from app.receipt_checks import run_checks, status_of
from app.receipt_parser import match_key, parse

RECEIPTS = Path(__file__).parent / "receipts"


def parsed(name: str) -> dict:
    return parse((RECEIPTS / f"{name}.txt").read_text(encoding="utf-8"))


def values(result: dict) -> list[int]:
    return [item["value"] for item in result["items"]]


def test_two_line_items_get_their_value_from_the_second_line():
    result = parsed("two_line_cash")

    assert values(result) == [597, 150, 599]
    water = result["items"][0]
    assert (water["name"], water["vat_code"]) == ("ÁSVÁNYVÍZ 1,5L", "C00")
    assert (water["quantity"], water["unit"], water["unit_price"]) == (3, "DB", 199)


def test_thousands_keep_their_first_digits():
    assert parsed("two_line_cash")["total"] == 1346


def test_quantity_at_end_of_name_is_not_a_price():
    assert parsed("two_line_cash")["items"][2]["name"] == "KENYÉR 500G"


def test_deposit_is_marked_even_with_broken_accents():
    item = parsed("two_line_cash")["items"][1]

    assert item["kind"] == "deposit"
    assert item["match_name"] == "DRS GONGYOLEG"


def test_header_and_footer_fields():
    result = parsed("two_line_cash")

    assert result["store_name"] == "TESZT ÉLELMISZER KFT"
    assert result["tax_number"] == "12345678-2-41"
    assert result["receipt_number"] == "0042/00017"
    assert result["purchased_on"] == "2026-12-14"
    assert result["purchased_at"] == "17:42"
    assert result["payments"] == [{"method": "cash", "amount": 2000}]
    assert result["change"] == 655


def test_quantity_above_name_with_vat_code_at_line_end():
    result = parsed("quantity_first")

    assert values(result) == [299, 399, 1290, 350, -88]
    assert result["total"] == 2250
    apple = result["items"][0]
    assert (apple["name"], apple["vat_code"]) == ("ALMALÉ 1L", "C27")
    assert (apple["quantity"], apple["unit"], apple["unit_price"]) == (2, "DB", 149.5)
    assert result["items"][2]["name"] == "FŰMAG 1,5 KG"
    assert result["payments"] == [{"method": "card", "amount": 2250}]
    assert result["receipt_number"] == "0042/00017"


def test_discount_line_with_a_prefixed_vat_code_is_counted():
    item = parsed("quantity_first")["items"][4]

    assert (item["vat_code"], item["kind"], item["value"]) == ("eC27", "discount", -88)


def test_quantity_decides_when_a_name_ends_in_a_number():
    item = parsed("quantity_first")["items"][3]

    assert (item["name"], item["value"]) == ("TÁPOLDAT 5", 350)


def test_deposit_vouchers_below_the_total_count_as_payment():
    result = parsed("deposit_voucher")

    assert result["total"] == 2347
    assert values(result) == [599, 449, 1299]
    assert result["payments"] == [
        {"method": "card", "amount": 547},
        {"method": "deposit_voucher", "amount": 300},
        {"method": "deposit_voucher", "amount": 1500},
    ]


def test_deposit_vouchers_settle_the_payment_check():
    result = parsed("deposit_voucher")

    checks = run_checks(result, None, False)

    assert checks["payment"] == {"ok": True, "paid": 2347}
    assert status_of(result, checks) == "ok"


def test_value_can_stand_on_its_own_line():
    result = parsed("price_below")

    assert values(result) == [399, 1500, 289, 470, -49]
    assert result["total"] == 2609
    assert result["payments"] == [{"method": "card", "amount": 2609}]
    assert result["receipt_number"] == "000123456/0007"


def test_weighed_item_value_is_not_the_weight_or_unit_price():
    result = parsed("price_below")

    tomato = result["items"][1]
    assert (tomato["quantity"], tomato["unit"], tomato["unit_price"]) == (1.25, "KG", 1200)
    assert tomato["value"] == 1500


def test_tare_line_is_skipped():
    result = parsed("price_below")

    apple = result["items"][3]
    assert (apple["quantity"], apple["value"]) == (0.94, 470)
    assert result["unmatched_lines"] == 0


def test_stray_number_before_quantity_line_does_not_win():
    assert parsed("price_below")["items"][1]["value"] == 1500


def test_adjustment_line_is_a_negative_discount():
    item = parsed("price_below")["items"][4]

    assert (item["kind"], item["value"]) == ("discount", -49)


def test_same_line_values_discount_and_rounding():
    result = parsed("same_line_weighed")

    assert values(result) == [1899, 599, -300, 379, 9, -9]
    assert result["items"][1]["unit_price"] == 499
    assert result["rounding"] == -2
    assert result["change"] == 425
    assert result["purchased_on"] == "2026-12-16"
    assert result["purchased_at"] == "18:05"


def test_misread_codes_and_labels_are_understood():
    result = parsed("noisy_reading")

    assert values(result) == [1490, 899, 690]
    assert [item["vat_code"] for item in result["items"]] == ["COD", "BOD", "COD"]
    assert result["payments"] == [{"method": "card", "amount": 3079}]


def test_total_decides_when_name_ends_in_a_number():
    result = parsed("name_ends_in_number")

    assert values(result) == [449, 599]
    assert result["items"][0]["name"] == "TOJÁS L 10"


def test_grouped_value_stays_when_it_matches_the_total():
    text = "NYUGTA\nC00 KÁVÉ 1 899\nÖSSZESEN: 1 899 FT\n"

    assert values(parse(text)) == [1899]


def test_value_before_its_line_is_paired_when_the_total_confirms_it():
    result = parsed("value_first")

    assert values(result) == [399, 289, 1500, -49]
    assert result["items"][2]["unit_price"] == 1200
    assert result["items"][3]["kind"] == "discount"


def test_shifted_order_is_rejected_when_the_total_does_not_confirm_it():
    text = "NYUGTA\n399\nC00 TÉSZTA\n289\nB00 LISZT\n999\nÖSSZESEN: 5 000 FT\n"

    assert values(parse(text)) == [289, 999]


def test_voucher_line_is_not_a_discount():
    text = "NYUGTA\nC00 KENYÉR 599\nE00 DRS UTALVÁNY -300\nÖSSZESEN: 299 FT\n"

    assert parse(text)["items"][1]["kind"] == "voucher"


def test_code_fence_is_ignored():
    text = "```markdown\nNYUGTA\nC00 KENYÉR 599\nÖSSZESEN: 599 FT\n```"

    assert parse(text)["total"] == 599


@pytest.mark.parametrize("text", ["", "semmi hasznos", "NYUGTA\n", "ÖSSZESEN:"])
def test_unusable_text_gives_empty_result(text):
    result = parse(text)

    assert result["items"] == []
    assert result["total"] is None


def test_invalid_date_is_dropped():
    assert parse("ÖSSZESEN: 1 FT\n2026.13.45\n")["purchased_on"] is None


def test_match_key_ignores_accents_and_punctuation():
    assert match_key("Gòngyóleg!  drs") == "GONGYOLEG DRS"
