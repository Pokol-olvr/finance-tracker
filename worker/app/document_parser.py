"""A szöveg dönti el a dokumentum típusát, így a fotó, a PDF és az e-mail ugyanoda jut."""

import re

from app.invoice_parser import parse_invoice
from app.receipt_parser import match_key, parse_pages

BUYER_WORDS = {"VEVO", "VASARLO", "MEGRENDELO"}
# Ezek nem kiadások: a hozzájuk tartozó számla számít, különben kétszer számolódna.
NON_EXPENSE_TITLES = {"SZALLITOLEVEL", "DIJBEKERO", "PROFORMA"}


def document_type(text: str) -> str:
    keys = [match_key(line) for line in text.splitlines()]
    words = set(re.findall(r"[A-Z]+", " ".join(keys)))
    if NON_EXPENSE_TITLES & set(keys):
        return "non_expense"
    if "SZAMLA" in words and "NETTO" in words and BUYER_WORDS & words:
        return "invoice"
    return "non_expense" if NON_EXPENSE_TITLES & words else "receipt"


def parse_document(texts: list[str]) -> dict:
    joined = "\n".join(texts)
    kind = document_type(joined)
    if kind == "invoice":
        return parse_invoice(joined)
    if kind == "non_expense":
        return {
            "document_type": kind,
            "store_name": None,
            "tax_number": None,
            "total": None,
            "items": [],
            "payments": [],
            "purchased_on": None,
            "receipt_number": None,
        }
    return {"document_type": kind, **parse_pages(texts)}
