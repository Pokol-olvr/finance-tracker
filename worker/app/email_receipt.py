"""A levél törzséből jött e-nyugta (pl. Apple-előfizetés, webshop-visszaigazolás).

Ezekben a címke és az érték, a tétel neve és az ára gyakran külön sorban áll, ezért a
blokkfeldolgozó nem ismeri fel őket. Ha a levél szövege a `Kibocsátó:` sorral kezdődik (ezt a
worker írja a levél elé, FIN-307), és a blokkfeldolgozó nem talált végösszeget vagy tételt, ez a
feldolgozó próbálkozik: a végösszeg a címkéből vagy a kártyás fizetés sorából, a tétel a
végösszeg előtti névsor. Az eredmény kikövetkeztetett, ezért mindig ellenőrzésre megy.
"""

import re
from datetime import date

from app.receipt_parser import TAX_NUMBER, match_key

ISSUER = re.compile(r"^Kibocsátó:\s*(?P<name>.+)$")
# A worker ezt írja, ha a feladóból nem derül ki a kibocsátó.
UNKNOWN_ISSUER = "ismeretlen"
MONEY = r"(?P<amount>-?\d{1,3}(?:[  .]\d{3})*(?:,\d{1,2})?|-?\d+(?:,\d{1,2})?)"
AMOUNT_ONLY = re.compile(rf"^{MONEY}\s*(?:Ft|HUF|forint)\.?$", re.IGNORECASE)
AMOUNT_IN = re.compile(rf"{MONEY}\s*(?:Ft|HUF|forint)\b", re.IGNORECASE)
TOTAL_LABEL = re.compile(
    r"^(?:fizetendő(?: összeg| végösszeg)?|végösszeg|összesen|teljes összeg|fizetett összeg|"
    r"total|amount due|amount paid)\b",
    re.IGNORECASE,
)
PAYMENT = re.compile(
    r"mastercard|visa|maestro|american express|amex|apple pay|google pay|paypal|bankkártya|"
    r"simplepay|barion",
    re.IGNORECASE,
)
# A név keresésekor átugrott sorok: címkék, mennyiség, áfa, megújulás.
NOT_A_NAME = re.compile(
    r"^(?:megújul|lejár|termék|cikkszám|mennyiség|egységár|ár\b|áfa|áfával|részösszeg|sorszám|"
    r"dátum|kedvezmény|\d+\s*(?:db|x)$)",
    re.IGNORECASE,
)
MONTHS = (
    "január", "február", "március", "április", "május", "június",
    "július", "augusztus", "szeptember", "október", "november", "december",
)  # fmt: skip
LONG_DATE = re.compile(rf"\b(20\d\d)\.\s*({'|'.join(MONTHS)})\s*(\d{{1,2}})\.?", re.IGNORECASE)
SHORT_DATE = re.compile(r"\b(20\d\d)[.-]\s?(\d{1,2})[.-]\s?(\d{1,2})\.?")
# Ezekben a sorokban a dátum nem a vásárlásé.
FUTURE_DATE = re.compile(r"^(?:megújul|lejár|fizetési határidő|érvényes)", re.IGNORECASE)
NUMBER_LABEL = re.compile(
    r"^(?:sorszám|számlaszám|számla sorszáma|nyugtaszám|rendelésszám|invoice number)\s*:?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
MAX_NAME_LENGTH = 120


def to_amount(text: str) -> int | float:
    number = float(re.sub(r"[  .]", "", text).replace(",", "."))
    return int(number) if number.is_integer() else number


def amount_of(line: str) -> int | float | None:
    found = AMOUNT_IN.search(line)
    return to_amount(found["amount"]) if found else None


def labelled_total(lines: list[str]) -> int | float | None:
    """Az utolsó címkézett végösszeg; az érték a címke sorában vagy alatta áll."""
    found = None
    for index, line in enumerate(lines):
        if not TOTAL_LABEL.match(line):
            continue
        value = amount_of(line)
        if value is None and index + 1 < len(lines) and AMOUNT_ONLY.match(lines[index + 1]):
            value = amount_of(lines[index + 1])
        if value is not None and value > 0:
            found = value
    return found


def paid_total(lines: list[str]) -> int | float | None:
    """A kártyás fizetés sora (pl. „Mastercard •••• 1234 (Apple Pay)”), az összeg mellette vagy alatta."""
    for index, line in enumerate(lines):
        if not PAYMENT.search(line):
            continue
        value = amount_of(line)
        if value is None and index + 1 < len(lines) and AMOUNT_ONLY.match(lines[index + 1]):
            value = amount_of(lines[index + 1])
        if value is not None and value > 0:
            return value
    return None


def is_name(line: str) -> bool:
    return (
        not AMOUNT_ONLY.match(line)
        and not NOT_A_NAME.match(line)
        and not line.endswith(":")
        and ":" not in line[:20]
        and len(line) <= MAX_NAME_LENGTH
        and any(char.isalpha() for char in line)
        and not LONG_DATE.search(line)
        and not SHORT_DATE.search(line)
    )


def item_name(lines: list[str], total: float) -> str | None:
    """A végösszeg első előfordulása előtti első névsor."""
    first = next(
        (index for index, line in enumerate(lines) if AMOUNT_ONLY.match(line) and amount_of(line) == total),
        None,
    )
    if first is None:
        return None
    return next((line for line in reversed(lines[:first]) if is_name(line)), None)


def purchase_date(lines: list[str]) -> str | None:
    for line in lines:
        if FUTURE_DATE.match(line):
            continue
        try:
            if found := LONG_DATE.search(line):
                month = MONTHS.index(found[2].lower()) + 1
                return date(int(found[1]), month, int(found[3])).isoformat()
            if found := SHORT_DATE.search(line):
                return date(*map(int, found.groups())).isoformat()
        except ValueError:
            continue
    return None


def document_number(lines: list[str]) -> str | None:
    for index, line in enumerate(lines):
        if found := NUMBER_LABEL.match(line):
            rest = found["rest"].strip() or (lines[index + 1] if index + 1 < len(lines) else "")
            if rest and not rest.endswith(":"):
                return rest.split()[0]
    return None


def issuer_name(text: str) -> str | None:
    """A levél kibocsátója az első sorból; None, ha nem levélből jött, vagy ismeretlen."""
    first = text.lstrip().split("\n", 1)[0].strip()
    found = ISSUER.match(first)
    if found is None:
        return None
    name = found["name"].strip()
    return None if name == UNKNOWN_ISSUER else name


def parse_email_receipt(text: str) -> dict | None:
    """None, ha a szöveg nem levélből jött, vagy nincs benne végösszeg."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not (issuer := ISSUER.match(lines[0])):
        return None
    body = lines[1:]
    total = labelled_total(body) or paid_total(body)
    if total is None:
        return None
    name = item_name(body, total) or "Levélben kapott számla"
    tax_number = TAX_NUMBER.search(text)
    store_name = issuer["name"].strip()
    return {
        "store_name": None if store_name == UNKNOWN_ISSUER else store_name,
        "tax_number": tax_number.group(0) if tax_number else None,
        "total": total,
        "items": [
            {
                "name": name,
                "match_name": match_key(name),
                "vat_code": None,
                "kind": "item",
                "quantity": None,
                "unit": None,
                "unit_price": None,
                "value": total,
                "ean": None,
                "alternative": None,
            }
        ],
        "unmatched_lines": [],
        "payments": [],
        "change": None,
        "rounding": None,
        "purchased_on": purchase_date(body),
        "purchased_at": None,
        "receipt_number": document_number(body),
        # A végösszeg és a tétel kikövetkeztetett: az ellenőrzésen dől el, jó-e.
        "inferred": True,
    }
