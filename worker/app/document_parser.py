"""A szöveg dönti el a dokumentum típusát, így a fotó, a PDF és az e-mail ugyanoda jut."""

import re

from app.invoice_parser import clean_lines, draft_of, parse_invoice
from app.receipt_parser import match_key, parse_pages

BUYER_WORDS = {"VEVO", "VASARLO", "MEGRENDELO"}
# Ezek nem kiadások: a hozzájuk tartozó számla számít, különben kétszer számolódna.
NON_EXPENSE_TITLES = {"SZALLITOLEVEL", "DIJBEKERO", "PROFORMA"}
# A visszaváltó automata utalványa nem vásárlás; a párosítása a vásárlással a FIN-411 feladata.
# A REpont a nyugtán fizetési sorként is szerepel, ezért nyugtánál nem elég önmagában.
VOUCHER_WORDS = {"UTALVANY", "VISSZAVALTOD"}


# A szövegben talált pénznemjelek; a forintjel elsőbbséget kap, mert a magyar blokkon is
# előfordulhat euró (pl. az árfolyam sora).
FOREIGN_CURRENCIES = {
    "EUR": re.compile(r"€|\bEUR\b", re.IGNORECASE),
    "USD": re.compile(r"(?<![A-Z])\$|\bUSD\b", re.IGNORECASE),
    "GBP": re.compile(r"£|\bGBP\b", re.IGNORECASE),
    "CHF": re.compile(r"\bCHF\b", re.IGNORECASE),
    "CZK": re.compile(r"\bCZK\b|\bKč", re.IGNORECASE),
    "PLN": re.compile(r"\bPLN\b|\bzł", re.IGNORECASE),
    "RON": re.compile(r"\bRON\b|\blei\b", re.IGNORECASE),
}
HUF_MARK = re.compile(r"\bFt\b|\bHUF\b|\bforint", re.IGNORECASE)


def currency_in_text(text: str) -> str | None:
    """A leggyakoribb külföldi pénznem, ha a szövegben nincs több forintjel; különben None (HUF)."""
    counts = {code: len(pattern.findall(text)) for code, pattern in FOREIGN_CURRENCIES.items()}
    code, count = max(counts.items(), key=lambda pair: pair[1])
    return code if count and count > len(HUF_MARK.findall(text)) else None


def is_deposit_voucher(words: set[str]) -> bool:
    return VOUCHER_WORDS <= words or ("REPONT" in words and "NYUGTA" not in words)


def document_type(text: str) -> str:
    keys = [match_key(line) for line in text.splitlines()]
    words = set(re.findall(r"[A-Z]+", " ".join(keys)))
    if NON_EXPENSE_TITLES & set(keys) or is_deposit_voucher(words):
        return "non_expense"
    if "SZAMLA" in words and "NETTO" in words and BUYER_WORDS & words:
        return "invoice"
    return "non_expense" if NON_EXPENSE_TITLES & words else "receipt"


def parse_document(texts: list[str]) -> dict:
    """A feldolgozó eredménye; ha a pénznemet nem olvasta ki, a szöveg jelei döntenek."""
    joined = "\n".join(texts)
    result = parse_by_type(joined, texts)
    if result.get("currency") is None and (currency := currency_in_text(joined)):
        result["currency"] = currency
    return result


def parse_by_type(joined: str, texts: list[str]) -> dict:
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
            "draft": draft_of(clean_lines(joined)),
        }
    return {"document_type": kind, **parse_pages(texts)}
