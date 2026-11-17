"""A dokumentum fajtája a szövegből."""



def test_deposit_voucher_slip_is_not_an_expense():
    from pathlib import Path

    from app.document_parser import document_type

    receipts = Path(__file__).parent / "receipts"
    slip = Path(__file__).parent / "non_expense" / "deposit_voucher_slip.txt"
    assert document_type(slip.read_text(encoding="utf-8")) == "non_expense"
    # A REpont fizetési sorként a nyugtán nem teszi a nyugtát utalvánnyá.
    assert document_type((receipts / "card_brand_and_repont.txt").read_text(encoding="utf-8")) == "receipt"

