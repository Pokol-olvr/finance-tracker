"""Kitalált számlák: a saját számlák szövege nem kerülhet a repóba."""

import json
from pathlib import Path

import pytest
from app.document_parser import document_type, parse_document
from app.invoice_parser import parse_invoice
from app.receipt_checks import run_checks, status_of

INVOICES = Path(__file__).parent / "invoices"
RECEIPTS = Path(__file__).parent / "receipts"


def text_of(name: str) -> str:
    return (INVOICES / f"{name}.txt").read_text(encoding="utf-8")


def parsed(name: str) -> dict:
    return parse_invoice(text_of(name))


def status(result: dict, entered_date: str | None = None, seen: bool = False) -> str:
    return status_of(result, run_checks(result, entered_date, seen))


def test_row_layout_keeps_every_column():
    first, second = parsed("one_line_row")["items"]

    assert (first["name"], first["quantity"], first["unit"]) == ("Tervezési díj", 2, "db")
    assert (first["unit_price"], first["net"], first["vat_rate"]) == (5000, 10000, 27)
    assert (first["vat"], first["value"]) == (2700, 12700)
    assert (second["vat_rate"], second["vat"], second["value"]) == ("AAM", 0, 1000)


def test_cell_layout_builds_items_from_separate_lines():
    first, second = parsed("one_cell_per_line")["items"]

    assert first["name"].startswith("Példa laptop 15 col")
    assert first["name"].endswith("gyári csomagolás")
    assert (first["quantity"], first["unit"], first["unit_price"]) == (1, "db", 236220)
    assert (first["net"], first["vat_rate"], first["vat"], first["value"]) == (236220, 27, 63780, 300000)
    assert second["unit_price"] == 1574.8
    assert (second["net"], second["vat"], second["value"]) == (1575, 425, 2000)
    assert "szolgáltatás kiszállítási díja" in second["name"]


@pytest.mark.parametrize(
    ("name", "total"),
    [("one_line_row", 13700), ("one_cell_per_line", 302000), ("buyer_first", 23775)],
)
def test_items_add_up_to_the_total(name, total):
    result = parsed(name)

    assert result["total"] == total
    assert sum(item["value"] for item in result["items"]) == total
    assert status(result) == "ok"


def test_labelled_header_fields():
    result = parsed("one_line_row")

    assert result["store_name"] == "Példa Stúdió Bt. 1011 Budapest"
    assert result["tax_number"] == "12345678-2-41"
    assert result["receipt_number"] == "PS-2026-17"
    assert result["purchased_on"] == "2026-10-20"
    assert result["issued_on"] == "2026-10-21"
    assert result["due_on"] == "2026-10-28"
    assert result["payments"] == [{"method": "transfer", "amount": 13700}]


def test_header_fields_in_columns_pair_labels_with_values():
    result = parsed("one_cell_per_line")

    assert result["store_name"] == "Minta Webshop Kft."
    assert result["receipt_number"] == "MWS12345/2026"
    assert result["purchased_on"] == "2026-10-20"
    assert result["issued_on"] == "2026-10-21"
    assert result["due_on"] == "2026-10-22"
    assert result["payments"] == [{"method": "card", "amount": 302000}]


def test_labels_above_dates_in_one_row():
    result = parsed("buyer_first")

    assert result["purchased_on"] == "2026-09-30"
    assert result["issued_on"] == "2026-10-01"
    assert result["due_on"] == "2026-10-09"
    assert result["payments"] == [{"method": "cash", "amount": 23775}]


def test_seller_comes_from_its_own_part_when_the_buyer_is_first():
    result = parsed("buyer_first")

    assert result["store_name"] == "Példa Szerviz Zrt."
    assert result["tax_number"] == "44332211-2-06"


@pytest.mark.parametrize(
    ("name", "words"),
    [
        ("one_line_row", ["Teszt Elek", "Nemlétező", "3/B"]),
        ("one_cell_per_line", ["Teszt Elek", "Szentendre", "Kitalált köz", "123 4567"]),
        ("buyer_first", ["Kitalált Vásárló", "Nincsilyen", "11223344"]),
    ],
)
def test_buyer_never_reaches_the_result(name, words):
    stored = json.dumps(parsed(name), ensure_ascii=False)

    assert not [word for word in words if word in stored]


def test_buyer_label_is_found_further_along_the_line():
    text = text_of("buyer_first").replace("Szállító: Példa Szerviz Zrt.", "A szállító: Példa Szerviz Zrt.")
    text = text.replace("Vevő neve:", "A vevő neve:").replace("Vevő címe:", "A vevő címe:")

    result = parse_invoice(text)

    assert result["store_name"] == "Példa Szerviz Zrt."
    assert "Kitalált Vásárló" not in json.dumps(result, ensure_ascii=False)


def test_labels_of_both_parties_on_one_line_leave_the_seller_empty():
    text = "SZÁMLA\nSzállító: Vevő:\nTeszt Elek\nPélda Kft.\nAdószám: 12345678-2-41\nNettó\n"

    result = parse_invoice(text)

    assert (result["store_name"], result["tax_number"]) == (None, None)


def test_order_number_is_not_the_invoice_number():
    text = text_of("one_line_row").replace("Sorszám: PS-2026-17", "Rendelés sorszáma: 998\nSorszám: PS-2026-17")

    assert parse_invoice(text)["receipt_number"] == "PS-2026-17"


def test_currency_written_right_after_the_number():
    text = text_of("buyer_first").replace("1.500 Ft 4.500 Ft", "1.500Ft 4.500Ft")

    assert [item["value"] for item in parse_invoice(text)["items"]] == [19050, 4725]


def test_invoice_date_is_the_fulfilment_date():
    result = parsed("one_line_row")

    assert run_checks(result, "2026-10-20", False)["date"]["ok"] is True
    assert status(result, "2026-10-21") == "review"


def test_issue_date_stands_in_when_fulfilment_is_missing():
    text = text_of("one_line_row").replace("Teljesítés dátuma: 2026.10.20.\n", "")

    assert parse_invoice(text)["purchased_on"] == "2026-10-21"


def test_summary_rows_are_read_by_rate():
    result = parsed("one_cell_per_line")

    assert result["vat_summary"] == [
        {"rate": 27, "net": 237795, "vat": 64205, "gross": 302000},
        {"rate": None, "net": 237795, "vat": 64205, "gross": 302000},
    ]
    assert run_checks(result, None, False)["vat_summary"] == {"ok": True, "gross": 302000}


def test_summary_on_one_line_is_read_too():
    assert parsed("one_line_row")["vat_summary"] == [
        {"rate": None, "net": 11000, "vat": 2700, "gross": 13700}
    ]


def test_unknown_table_keeps_the_total_without_inventing_items():
    result = parsed("unknown_table")

    assert result["items"] == []
    assert result["total"] == 1270
    assert result["tax_number"] == "55667788-2-13"
    assert status(result) == "review"


def test_foreign_currency_needs_review():
    result = parsed("foreign_currency")

    assert (result["total"], result["currency"]) == (12.7, "EUR")
    assert run_checks(result, None, False)["currency"] == {"ok": False, "currency": "EUR"}
    assert status(result) == "review"


def test_forint_invoice_passes_the_currency_check():
    assert run_checks(parsed("one_cell_per_line"), None, False)["currency"]["ok"] is True


def test_wrong_line_needs_review():
    text = text_of("one_line_row").replace("10 000 27% 2 700 12 700", "10 000 27% 2 700 12 709")

    result = parse_invoice(text)

    assert status(result) == "review"


def test_same_invoice_again_needs_review():
    assert status(parsed("one_line_row"), seen=True) == "review"


def test_invoice_without_total_is_unparsed():
    text = "SZÁMLA\nVevő: Teszt Elek\nNettó\nSzállító: Példa Kft.\n"

    assert status(parse_invoice(text)) == "unparsed"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Szállítólevél", "non_expense"),
        ("Díjbekérő", "non_expense"),
        ("Proforma", "non_expense"),
    ],
)
def test_non_expense_titles_win_over_invoice_words(line, expected):
    assert document_type(f"{line}\nSzámla\nVevő\nNettó\n") == expected


def test_delivery_note_never_gets_items():
    result = parse_document([text_of("delivery_note")])

    assert result["document_type"] == "non_expense"
    assert result["items"] == []
    assert result["total"] is None
    assert status(result) == "unparsed"


def test_invoice_mentioning_a_delivery_note_stays_an_invoice():
    text = text_of("one_line_row").replace("Oldal 1/1", "Szállítólevél száma: 123")

    assert document_type(text) == "invoice"


def test_invoice_is_recognised_from_either_layout():
    assert document_type(text_of("one_line_row")) == "invoice"
    assert document_type(text_of("one_cell_per_line")) == "invoice"


@pytest.mark.parametrize("path", sorted(RECEIPTS.glob("*.txt")), ids=lambda path: path.stem)
def test_receipts_stay_receipts(path):
    assert document_type(path.read_text(encoding="utf-8")) == "receipt"


def test_receipt_footer_with_the_word_invoice_stays_a_receipt():
    assert document_type("NYUGTA\nVEVŐSZOLGÁLAT\nNYUGTA/SZAMLA\nÖSSZESEN: 1 000 Ft\n") == "receipt"


def test_pages_of_an_invoice_are_joined():
    text = text_of("one_line_row")
    middle = text.index("Összesen: 11 000")

    result = parse_document([text[:middle], text[middle:]])

    assert result["document_type"] == "invoice"
    assert result["total"] == 13700
    assert len(result["items"]) == 2
