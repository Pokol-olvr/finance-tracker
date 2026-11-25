"""A dokumentum fajtája a szövegből."""



def test_deposit_voucher_slip_is_not_an_expense():
    from pathlib import Path

    from app.document_parser import document_type

    receipts = Path(__file__).parent / "receipts"
    slip = Path(__file__).parent / "non_expense" / "deposit_voucher_slip.txt"
    assert document_type(slip.read_text(encoding="utf-8")) == "non_expense"
    # A REpont fizetési sorként a nyugtán nem teszi a nyugtát utalvánnyá.
    assert document_type((receipts / "card_brand_and_repont.txt").read_text(encoding="utf-8")) == "receipt"



def test_currency_comes_from_the_text_when_the_parser_has_none():
    from app.document_parser import currency_in_text, parse_document

    stripe = "Invoice\nClaude Pro 1 €18.00 27% €18.00\nTotal €22.86\nAmount due €22.86"
    assert currency_in_text(stripe) == "EUR"
    assert parse_document([stripe])["currency"] == "EUR"


def test_forint_wins_over_an_occasional_foreign_mark():
    from app.document_parser import currency_in_text

    receipt = "KENYÉR 599 Ft\nTEJ 449 Ft\nÖSSZESEN 1 048 Ft\nÁrfolyam: 1 EUR = 400 Ft"
    assert currency_in_text(receipt) is None
    assert currency_in_text("Total 12.00 USD") == "USD"
    assert currency_in_text("nincs pénznem") is None
