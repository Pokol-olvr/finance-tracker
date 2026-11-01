"""Az A4-es számla szerkezete a szöveges olvasatból. Tiszta függvény, mint a blokk feldolgozója.

A vevő neve és címe nem kerülhet az eredménybe, ezért a szállító adatai csak a saját részéből jönnek.
"""

import re
from collections.abc import Iterator
from datetime import date

from app.receipt_parser import DATE_TEXT, TAX_NUMBER, classify, match_key

MONEY = r"-?\d{1,3}(?:[ .]\d{3})+(?:,\d{1,2})?|-?\d+(?:[,.]\d{1,2})?"
CURRENCY = r"Ft\.?|HUF|EUR|€|USD|\$|GBP|£"
CELL = rf"(?P<prefix>€|\$|£)?\s*(?P<amount>{MONEY})\s*(?P<currency>{CURRENCY})?"
AMOUNT_CELL = re.compile(CELL, re.IGNORECASE)
TRAILING_CELL = re.compile(rf"(?:^|\s){CELL}$", re.IGNORECASE)
CURRENCY_MARK = re.compile(rf"(?:(?<=\d)|\s)(?:{CURRENCY})(?=\s|$)", re.IGNORECASE)
RATE_CELL = re.compile(r"(?P<rate>\d{1,2})\s*%", re.IGNORECASE)
CODE_CELL = re.compile(r"[^\W\d_]{2,5}")
NUMBER_CELL = re.compile(r"-?\d[\d.,]*")
QUANTITY_CELL = re.compile(r"(?P<quantity>\d+(?:[,.]\d+)?)\s*(?P<unit>[^\W\d_]{1,7})\.?")
# Mennyiség, egységár és érték, de áfa nélkül: ez csak javaslat lehet, mert nem ellenőrzi magát.
DRAFT_ROW = re.compile(
    rf"^(?P<name>.+?)\s+(?P<quantity>\d+(?:[,.]\d+)?)\s*(?P<unit>[^\W\d_]{{1,7}})\.?\s+"
    rf"(?P<unit_price>{MONEY})\s*(?:Ft\.?|HUF)?\s+(?P<value>{MONEY})\s*(?:Ft\.?|HUF)?$",
    re.IGNORECASE,
)
# A sor elején a név áll, ezért a mennyiséget csak akkor fogadjuk el, ha utána szám jön.
QUANTITY_IN_ROW = re.compile(rf"(?:^|\s){QUANTITY_CELL.pattern}(?=\s+-?\d)")

BUYER_WORDS = {"VEVO", "VASARLO", "MEGRENDELO"}
SELLER_WORDS = {"SZALLITO", "ELADO", "KIBOCSATO", "KIALLITO", "SZOLGALTATO"}
HEADER_START = {"MEGNEVEZES", "TERMEK", "EGYSEGAR"}
HEADER_WORDS = {*HEADER_START, "NETTO", "BRUTTO", "AFA"}
TABLE_END_WORDS = {"OSSZESEN", "AFA", "FIZETENDO", "VEGOSSZEG", "NETTO", "BRUTTO", "MINDOSSZESEN"}
TOTAL_LABELS = (
    "BRUTTO VEGOSSZEG",
    "OSSZESEN BRUTTO",
    "BRUTTO OSSZESEN",
    "VEGOSSZEG",
    "FIZETENDO",
)
DATE_LABELS = re.compile(
    r"(?P<fulfilled>TELJESITES(?: (?:KELTE|DATUMA|IDEJE|IDOPONTJA|NAPJA))?)"
    r"|(?P<due>HATARIDO|ESEDEKESSEG)"
    r"|(?P<issued>KIALLITAS(?: (?:KELTE|DATUMA|IDEJE))?|KIBOCSATAS|\bKELTE?\b)"
)
NUMBER_LABEL = re.compile(r"\b(?:SORSZAMA?|SZAMLASZAM|SZAMLA SZAMA|BIZONYLATSZAM)\b")
OTHER_NUMBERS = ("RENDELES", "SZALLITOLEVEL")
PAYMENT_METHODS = (
    ("ATUTALAS", "transfer"),
    ("BANKKARTYA", "card"),
    ("KARTYA", "card"),
    ("KESZPENZ", "cash"),
    ("UTANVET", "cash_on_delivery"),
)
NOT_A_NAME = {
    "SZAMLA", "SORSZAM", "ADOSZAM", "EREDETI", "SZALLITOLEVEL", "DIJBEKERO", "PROFORMA",
}
HEADER_LOOKBACK = 8
LABEL_WORDS = 8
LABEL_POSITION = 3
AMOUNT_LIMIT = 1


def to_amount(text: str) -> int | float:
    cleaned = text.replace(" ", "")
    if re.search(r"\.\d{3}", cleaned):
        cleaned = cleaned.replace(".", "")
    number = float(cleaned.replace(",", "."))
    return int(number) if number.is_integer() else number


def close(first: float, second: float) -> bool:
    return abs(first - second) <= AMOUNT_LIMIT


def currency_of(match: re.Match) -> str | None:
    mark = (match["prefix"] or match["currency"] or "").rstrip(".").upper()
    if not mark:
        return None
    return {"FT": "HUF", "€": "EUR", "$": "USD", "£": "GBP"}.get(mark, mark)


def read_cell(text: str) -> tuple[int | float, str | None] | None:
    match = AMOUNT_CELL.fullmatch(text.strip())
    return (to_amount(match["amount"]), currency_of(match)) if match else None


def groupings(tokens: list[str]) -> Iterator[list[int | float]]:
    """A szóköz ezres tagolás és cellahatár is lehet, ezért minden felosztást végignéz."""
    if not tokens:
        yield []
        return
    for size in range(1, len(tokens) + 1):
        head = tokens[:size]
        if size > 1 and not is_grouped(head):
            break
        if NUMBER_CELL.fullmatch(head[0]):
            for rest in groupings(tokens[size:]):
                yield [to_amount(" ".join(head)), *rest]


def is_grouped(tokens: list[str]) -> bool:
    return (
        re.fullmatch(r"-?\d{1,3}", tokens[0]) is not None
        and all(re.fullmatch(r"\d{3}", token) for token in tokens[1:-1])
        and re.fullmatch(r"\d{3}(?:,\d{1,2})?", tokens[-1]) is not None
    )


def fit_amounts(quantity: float | None, amounts: list[int | float]) -> dict | None:
    """Egységár, nettó, áfa, bruttó: az értelmezés csak akkor jó, ha a számok kiadják egymást."""
    if len(amounts) not in (3, 4):
        return None
    unit_price = amounts[0] if len(amounts) == 4 else None
    net, vat, gross = amounts[-3:]
    if not close(net + vat, gross):
        return None
    if unit_price is not None and quantity is not None:
        expected = quantity * unit_price
        if not (close(expected, net) or close(expected, gross)):
            return None
    return {"unit_price": unit_price, "net": net, "vat": vat, "value": gross}


def to_quantity(text: str) -> int | float:
    number = float(text.replace(",", "."))
    return int(number) if number.is_integer() else number


def rate_of(token: str) -> int | str | None:
    match = RATE_CELL.fullmatch(token)
    if match:
        return int(match["rate"])
    return token.upper() if CODE_CELL.fullmatch(token) else None


def parse_row(line: str) -> dict | None:
    """Tétel egy sorban: név, mennyiség, egység, majd a számok; az áfakulcs bárhol állhat köztük."""
    for spot in QUANTITY_IN_ROW.finditer(line):
        quantity = to_quantity(spot["quantity"])
        tail = CURRENCY_MARK.sub(" ", f" {line[spot.end() :]} ")
        tail = re.sub(r"(\d)\s+%", r"\1%", tail)
        tokens = tail.split()
        rates = [token for token in tokens if not NUMBER_CELL.fullmatch(token)]
        if len(rates) > 1 or (rates and rate_of(rates[0]) is None):
            continue
        for grouping in groupings_around(tokens, rates):
            fitted = fit_amounts(quantity, grouping)
            if fitted:
                return {
                    "name": line[: spot.start()].strip(),
                    "quantity": quantity,
                    "unit": spot["unit"],
                    "vat_rate": rate_of(rates[0]) if rates else None,
                    **fitted,
                }
    return None


def groupings_around(tokens: list[str], rates: list[str]) -> Iterator[list[int | float]]:
    """Az áfakulcs két oldala külön cella, ezért az ezres csoport nem léphet át rajta."""
    if not rates:
        yield from groupings(tokens)
        return
    split = tokens.index(rates[0])
    for left in groupings(tokens[:split]):
        for right in groupings(tokens[split + 1 :]):
            yield [*left, *right]


def line_cells(line: str) -> list[int | float] | None:
    """Forintos cellák egy sorban; a külföldi pénznem csak tájékoztató, ezért nem számít."""
    parts = re.findall(rf"(?:{MONEY})\s*(?:Ft\.?|HUF)", line, re.IGNORECASE)
    if parts and re.sub(rf"(?:{MONEY})\s*(?:Ft\.?|HUF)", "", line, flags=re.IGNORECASE).strip() == "":
        return [read_cell(part)[0] for part in parts]
    cell = read_cell(line)
    return [cell[0]] if cell and cell[1] in (None, "HUF") else None


def read_cells(lines: list[str], index: int) -> tuple[dict | None, int]:
    """Cellánként külön sorok: a számok és az áfakulcs összefüggő szakasza egy tétel vége."""
    amounts: list[int | float] = []
    rate = None
    position = index
    while position < len(lines):
        line = lines[position]
        match = RATE_CELL.fullmatch(line)
        cells = line_cells(line)
        if match and rate is None:
            rate = int(match["rate"])
        elif cells:
            amounts.extend(cells)
        else:
            break
        position += 1
    fitted = fit_amounts(None, amounts[-4:]) if len(amounts) >= 3 else None
    return ({"vat_rate": rate, **fitted}, position) if fitted else (None, index)


def split_quantity(pending: list[str]) -> tuple[list[str], int | float | None, str | None]:
    """A mennyiség a számok felett áll, köztük legfeljebb egy üres jelentésű cellával."""
    for offset in (1, 2):
        if len(pending) >= offset:
            match = QUANTITY_CELL.fullmatch(pending[-offset])
            if match:
                return pending[:-offset], to_quantity(match["quantity"]), match["unit"]
    return pending, None, None


def name_of(pending: list[str], own_name: str = "") -> str:
    parts = [
        line for line in pending if not (line.isdigit() or QUANTITY_CELL.fullmatch(line))
    ]
    return " ".join([*parts, own_name]).strip()


def finish_item(row: dict) -> dict:
    return {
        "name": row["name"],
        "match_name": match_key(row["name"]),
        "kind": classify(row["name"], row["value"]),
        "quantity": row.get("quantity"),
        "unit": row.get("unit"),
        "unit_price": row["unit_price"],
        "net": row["net"],
        "vat_rate": row["vat_rate"],
        "vat": row["vat"],
        "value": row["value"],
    }


def read_items(lines: list[str]) -> tuple[list[dict], int]:
    items = []
    pending: list[str] = []
    index = 0
    while index < len(lines):
        row = parse_row(lines[index])
        if row:
            row["name"] = name_of(pending, row["name"])
            items.append(finish_item(row))
            pending = []
            index += 1
            continue
        cells, after = read_cells(lines, index)
        if cells:
            before, quantity, unit = split_quantity(pending)
            items.append(
                finish_item(cells | {"name": name_of(before), "quantity": quantity, "unit": unit})
            )
            pending = []
            index = after
            continue
        pending.append(lines[index])
        index += 1
    return items, len(pending)


def words_of(line: str) -> list[str]:
    return re.findall(r"[A-Z]+", match_key(line))


def table_bounds(lines: list[str]) -> tuple[int, int]:
    start = next((i for i, line in enumerate(lines) if HEADER_START & set(words_of(line))), None)
    if start is None:
        return len(lines), len(lines)
    last_header = start
    for position in range(start + 1, min(start + 10, len(lines))):
        if any(char.isdigit() for char in lines[position]):
            break
        if HEADER_WORDS & set(words_of(lines[position])):
            last_header = position
    body = last_header + 1
    end = next(
        (
            position
            for position in range(body, len(lines))
            if (words := words_of(lines[position])) and words[0] in TABLE_END_WORDS
        ),
        len(lines),
    )
    return body, end


def seller_part(lines: list[str]) -> list[str]:
    """A szállító része: a saját címkéjétől a vevőig, címke nélkül a vevő előtti rész."""
    starts = [set(words_of(line)[:LABEL_POSITION]) for line in lines]
    seller = next((i for i, words in enumerate(starts) if SELLER_WORDS & words), None)
    buyer = next((i for i, words in enumerate(starts) if BUYER_WORDS & words), None)
    if seller is None:
        return lines if buyer is None else lines[:buyer]
    # Ha egy sorban áll a két címke, a neveik nem választhatók szét biztosan.
    if BUYER_WORDS & set(words_of(lines[seller])):
        return []
    end = buyer if buyer is not None and buyer > seller else len(lines)
    rest = lines[seller].split(":", 1)
    return ([rest[1].strip()] if len(rest) == 2 and rest[1].strip() else []) + lines[seller + 1 : end]


def store_name_of(part: list[str]) -> str | None:
    for line in part:
        words = words_of(line)
        letters = sum(len(word) for word in words)
        if letters >= 3 and words[0] not in NOT_A_NAME:
            return line
    return None


def dates_in(line: str) -> list[str]:
    found = []
    for match in DATE_TEXT.finditer(line):
        try:
            found.append(date(*map(int, match.groups())).isoformat())
        except ValueError:
            continue
    return found


def read_dates(lines: list[str]) -> dict[str, str]:
    """A címke a dátummal egy sorban vagy oszlopos elrendezésben a dátumok fölött áll."""
    found: dict[str, str] = {}
    waiting: list[str] = []
    for line in lines:
        key = match_key(line)
        if len(key.split()) <= LABEL_WORDS or dates_in(line):
            waiting.extend(match.lastgroup for match in DATE_LABELS.finditer(key))
        for value in dates_in(line):
            if waiting:
                found.setdefault(waiting.pop(0), value)
    return found


def read_number(lines: list[str]) -> str | None:
    for index, line in enumerate(lines):
        label = match_key(line.split(":")[0])
        if NUMBER_LABEL.search(label) is None or any(word in label for word in OTHER_NUMBERS):
            continue
        rest = line.split(":", 1)[1] if ":" in line else line
        if not rest.strip() and index + 1 < len(lines):
            rest = lines[index + 1]
        number = next((word for word in rest.split() if any(c.isdigit() for c in word)), None)
        if number:
            return number
    return None


def read_method(lines: list[str]) -> str | None:
    for line in lines:
        key = match_key(line)
        for word, method in PAYMENT_METHODS:
            if re.search(rf"\b{word}\b", key):
                return method
    return None


def amount_near(lines: list[str], index: int) -> tuple[int | float, str | None] | None:
    """A címke összege ugyanabban vagy a következő sorban áll."""
    match = TRAILING_CELL.search(lines[index])
    if match:
        return to_amount(match["amount"]), currency_of(match)
    return read_cell(lines[index + 1]) if index + 1 < len(lines) else None


def read_total(lines: list[str]) -> tuple[int | float | None, str | None]:
    for label in TOTAL_LABELS:
        for index, line in enumerate(lines):
            key = match_key(line)
            if label in key and "AFA" not in key.split()[:2]:
                found = amount_near(lines, index)
                if found and found[0] > 0:
                    return found
    for index in range(len(lines) - 1, -1, -1):
        if match_key(lines[index]).startswith("OSSZESEN"):
            found = amount_near(lines, index)
            if found and found[0] > 0:
                return found
    return None, None


def summary_row(lines: list[str], index: int) -> dict | None:
    """Nettó, áfa, bruttó ugyanabban a sorban vagy a címke alatt, cellánként."""
    tail = CURRENCY_MARK.sub(" ", f" {lines[index]} ").split()
    tokens = [token for token in tail if NUMBER_CELL.fullmatch(token)]
    cells: list[int | float] = []
    for line in lines[index + 1 : index + 6]:
        found = line_cells(line)
        if found:
            cells.extend(found)
        elif read_cell(line) is None:
            break
    candidates = [*groupings(tokens), cells[:3]]
    for amounts in candidates:
        if len(amounts) == 3 and close(amounts[0] + amounts[1], amounts[2]):
            return {"net": amounts[0], "vat": amounts[1], "gross": amounts[2]}
    return None


def read_summary(lines: list[str]) -> list[dict]:
    rows = []
    for index, line in enumerate(lines):
        rate = re.match(r"(\d{1,2})\s*%", line)
        if rate or match_key(line).startswith("OSSZESEN"):
            row = summary_row(lines, index)
            if row:
                rows.append({"rate": int(rate[1]) if rate else None, **row})
    return rows


def clean_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return [line for line in lines if not line.startswith("```")]


def gross_factor(lines: list[str], body: int) -> float:
    """Ha a táblázat csak nettót ad, és egy áfakulcs van, a javaslat bruttóra vált."""
    header = {word for line in lines[max(0, body - HEADER_LOOKBACK) : body] for word in words_of(line)}
    rates = {
        int(match[1])
        for line in lines
        if words_of(line)[:1] == ["AFA"]
        for match in re.finditer(r"(\d{1,2})\s*%", line)
    }
    if "NETTO" in header and "BRUTTO" not in header and len(rates) == 1:
        return 1 + rates.pop() / 100
    return 1


def draft_row(line: str, factor: float) -> dict | None:
    """A sor legjobb értelmezése; lehet hibás, ezért csak a javítás űrlapját tölti ki."""
    full = parse_row(line)
    if full:
        return {key: full[key] for key in ("name", "quantity", "unit", "unit_price", "value")}
    match = DRAFT_ROW.match(line)
    if match:
        return {
            "name": match["name"],
            "quantity": to_quantity(match["quantity"]),
            "unit": match["unit"],
            "unit_price": to_amount(match["unit_price"]) if factor == 1 else None,
            "value": round(to_amount(match["value"]) * factor),
        }
    trailing = TRAILING_CELL.search(line)
    if trailing is None or len(words_of(line[: trailing.start()])) == 0:
        return None
    return {
        "name": line[: trailing.start()].strip(),
        "quantity": None,
        "unit": None,
        "unit_price": None,
        "value": round(to_amount(trailing["amount"]) * factor),
    }


def draft_of(lines: list[str]) -> dict:
    """Javaslat a javítás űrlapjához: mentés nélkül nem számít adatnak."""
    body, end = table_bounds(lines)
    factor = gross_factor(lines, body)
    rows = [row for line in lines[body:end] if (row := draft_row(line, factor))]
    dates = read_dates(lines)
    any_date = next((value for line in lines for value in dates_in(line)), None)
    return {
        "store_name": store_name_of(seller_part(lines)),
        "purchased_on": dates.get("fulfilled") or dates.get("issued") or any_date,
        "total": read_total(lines)[0],
        "items": [row | {"kind": "item"} for row in rows],
    }


def parse_invoice(text: str) -> dict:
    lines = clean_lines(text)

    body, end = table_bounds(lines)
    items, unmatched = read_items(lines[body:end])
    total, currency = read_total(lines)
    dates = read_dates(lines)
    method = read_method(lines)
    seller = seller_part(lines)
    tax_number = next(filter(None, (TAX_NUMBER.search(line) for line in seller)), None)

    return {
        "document_type": "invoice",
        "store_name": store_name_of(seller),
        "tax_number": tax_number.group(0) if tax_number else None,
        "total": total,
        "currency": currency,
        "items": items,
        "unmatched_lines": unmatched,
        "vat_summary": read_summary(lines[end:]),
        "payments": [{"method": method, "amount": total}] if method and total else [],
        "change": None,
        "rounding": None,
        "purchased_on": dates.get("fulfilled") or dates.get("issued"),
        "purchased_at": None,
        "issued_on": dates.get("issued"),
        "due_on": dates.get("due"),
        "receipt_number": read_number(lines),
        **({"draft": draft_of(lines)} if not items else {}),
    }
