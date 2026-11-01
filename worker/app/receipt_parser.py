"""A szöveges olvasatból blokkszerkezet. Tiszta függvény: se hálózat, se adatbázis nem kell hozzá."""

import re
import unicodedata
from datetime import date
from difflib import get_close_matches
from itertools import product

# Ha a szabály változik, a worker a meglévő szövegeket is újra feldolgozza, modellfutás nélkül.
PARSER_VERSION = "1"

MAX_AMBIGUOUS_LINES = 12
MAX_OVERLAP_LINES = 15

GROUPED = r"\d{1,3}(?: \d{3})+"
AMOUNT = rf"-?(?:{GROUPED}|\d+)"
# Az olvasat a 00-t néha OD-nek vagy OO-nak adja; a kisbetűs előtag az akciós sorokat jelöli.
ITEM_LINE = re.compile(r"^(?P<code>[a-z]?[A-E][0O][0OD])\s+(?P<rest>.+)$")
QUANTITY_LINE = re.compile(
    r"^(?P<quantity>\d+(?:[,.]\d+)?)\s*(?P<unit>[^\W\d_]+)\s*[*xX]\s*"
    rf"(?P<unit_price>{GROUPED}|\d+)\s*(?:ft)?\s*/\s*[^\W\d_]+(?:\s+(?P<value>{GROUPED}|\d+))?$",
    re.IGNORECASE,
)
TARE_LINE = re.compile(r"^\d+[,.]\d+\s*KG\s*-\s*\d+[,.]\d+\s*KG\b", re.IGNORECASE)
BARE_AMOUNT = re.compile(rf"^(?P<value>{AMOUNT})(?:\s*FT)?$", re.IGNORECASE)
TRAILING_AMOUNT = re.compile(rf"^(?P<name>.*?\S)\s+(?P<value>{AMOUNT})$")
LABELLED_LINE = re.compile(r"^(?P<label>[^:]+):\s*(?P<rest>.*)$")
LABEL_AMOUNT = re.compile(rf"^(?P<value>{AMOUNT})(?:\s*(?:FT|HUF))?\b", re.IGNORECASE)
DATE_TEXT = re.compile(r"\b(20\d{2})[.\-/ ]\s?(\d{2})[.\-/ ]\s?(\d{2})\b")
TIME_TEXT = re.compile(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b")
TAX_NUMBER = re.compile(r"\b\d{8}-\d-\d{2}\b")
RECEIPT_NUMBER = re.compile(r"\b\d{3,}/\d{3,}\b")

PAYMENT_LABELS = {
    "KESZPENZ": "cash",
    "BANKKARTYA": "card",
    "KARTYA": "card",
    "SZEP KARTYA": "szep",
    "UTALVANY": "voucher",
}
CHANGE_LABEL = "VISSZAJARO"
ROUNDING_LABEL = "KEREKITES"
DEPOSIT_WORDS = ("DRS", "GONGYOLEG", "BETETDIJ")
VOUCHER_WORDS = (*DEPOSIT_WORDS, "UTALVANY", "VISSZAVALT")


def match_key(text: str) -> str:
    """Ékezet nélküli, nagybetűs egyeztető kulcs: a kiolvasás ékezethibái így nem számítanak."""
    decomposed = unicodedata.normalize("NFKD", text.upper())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^A-Z0-9%,.]+", " ", plain).split())


def to_int(text: str) -> int:
    return int(text.replace(" ", ""))


def to_number(text: str) -> float:
    return float(text.replace(",", "."))


def is_item_start(line: str) -> bool:
    return ITEM_LINE.match(line) is not None


def is_total_line(line: str) -> bool:
    words = match_key(line).replace("0", "O").split()
    return bool(words) and bool(get_close_matches(words[0].rstrip(":"), ["OSSZESEN"], cutoff=0.8))


def split_trailing_amount(rest: str) -> tuple[str, int | None, int | None]:
    """Név, érték és a másik értelmezés: a `10 449` lehet 10 449 Ft, vagy egy 10-re végződő név."""
    match = TRAILING_AMOUNT.match(rest)
    if match is None:
        return rest, None, None
    value = match["value"]
    if re.fullmatch(r"-?\d{1,3} \d{3}", value):
        return match["name"], to_int(value), int(value.split()[1])
    return match["name"], to_int(value), None


def classify(name: str, value: int | None) -> str:
    key = match_key(name)
    if value is not None and value < 0:
        return "voucher" if any(word in key for word in VOUCHER_WORDS) else "discount"
    return "deposit" if any(word in key for word in DEPOSIT_WORDS) else "item"


def parse_item(lines: list[str], index: int, end: int) -> tuple[dict, int, int]:
    """Egy tétel az indextől a következő tétel elejéig; visszaadja az el nem fogadott sorok számát."""
    match = ITEM_LINE.match(lines[index])
    rest = match["rest"]
    quantity = unit = unit_price = None
    value = None
    unmatched = 0

    position = index + 1
    while position < end and not is_item_start(lines[position]):
        line = lines[position]
        quantity_match = QUANTITY_LINE.match(line)
        bare = BARE_AMOUNT.match(line)
        if quantity_match:
            quantity = to_number(quantity_match["quantity"])
            unit = quantity_match["unit"].upper()
            unit_price = to_int(quantity_match["unit_price"])
            if quantity_match["value"]:
                value = to_int(quantity_match["value"])
        elif bare:
            # Egy elcsúszott szám után a mennyiségsor alatti érték az érvényes.
            value = to_int(bare["value"])
        elif not TARE_LINE.match(line):
            unmatched += 1
        position += 1

    alternative = None
    name = rest
    if value is None:
        name, value, alternative = split_trailing_amount(rest)

    item = {
        "name": name,
        "match_name": match_key(name),
        "vat_code": match["code"],
        "kind": classify(name, value),
        "quantity": quantity,
        "unit": unit,
        "unit_price": unit_price,
        "value": value,
        "alternative": alternative,
    }
    return item, position, unmatched


def resolve_amounts(items: list[dict], total: int | None) -> None:
    """A kétféleképp olvasható sorok közül azt választja, amelyikkel kijön a végösszeg."""
    ambiguous = [item for item in items if item["alternative"] is not None]
    if total is not None and 0 < len(ambiguous) <= MAX_AMBIGUOUS_LINES:
        fixed = sum(item["value"] or 0 for item in items if item["alternative"] is None)
        for choice in product(*[(item["value"], item["alternative"]) for item in ambiguous]):
            if fixed + sum(choice) == total:
                for item, value in zip(ambiguous, choice, strict=True):
                    if value != item["value"]:
                        item["name"] = f"{item['name']} {str(item['value'])[:-3]}"
                        item["match_name"] = match_key(item["name"])
                        item["value"] = value
                break
    for item in items:
        del item["alternative"]


def read_items(lines: list[str], total: int | None) -> tuple[list[dict], int]:
    items = []
    unmatched = 0
    index = 0
    while index < len(lines):
        if not is_item_start(lines[index]):
            index += 1
            continue
        item, index, skipped = parse_item(lines, index, len(lines))
        items.append(item)
        unmatched += skipped
    resolve_amounts(items, total)
    for item in items:
        item["kind"] = classify(item["name"], item["value"])
    return items, unmatched


def values_first(lines: list[str]) -> list[str]:
    """Az olvasat néha előbb adja a sor jobb szélét: ilyenkor az érték a saját sora elé kerül."""
    swapped = list(lines)
    index = 0
    while index < len(swapped) - 1:
        if BARE_AMOUNT.match(swapped[index]) and not BARE_AMOUNT.match(swapped[index + 1]):
            swapped[index], swapped[index + 1] = swapped[index + 1], swapped[index]
            index += 2
        else:
            index += 1
    return swapped


def items_add_up(items: list[dict], total: int | None) -> bool:
    return sum(item["value"] or 0 for item in items) == total


def labelled_amount(lines: list[str], index: int, rest: str) -> int | None:
    """A címke értéke ugyanabban vagy a következő sorban áll."""
    match = LABEL_AMOUNT.match(rest.strip())
    if match:
        return to_int(match["value"])
    if not rest.strip() and index + 1 < len(lines):
        bare = BARE_AMOUNT.match(lines[index + 1])
        if bare:
            return to_int(bare["value"])
    return None


def known_label(label: str, known: list[str]) -> str | None:
    found = get_close_matches(match_key(label), known, n=1, cutoff=0.7)
    return found[0] if found else None


def parse_footer(lines: list[str]) -> dict:
    """A végösszeg utáni rész: fizetés, visszajáró, kerekítés, dátum és nyugtaszám."""
    payments: dict[str, int] = {}
    change = rounding = None
    for index, line in enumerate(lines):
        match = LABELLED_LINE.match(line)
        if match is None:
            continue
        label = known_label(match["label"], [*PAYMENT_LABELS, CHANGE_LABEL, ROUNDING_LABEL])
        amount = labelled_amount(lines, index, match["rest"]) if label else None
        if amount is None:
            continue
        if label == CHANGE_LABEL:
            change = change if change is not None else amount
        elif label == ROUNDING_LABEL:
            rounding = rounding if rounding is not None else amount
        else:
            payments.setdefault(PAYMENT_LABELS[label], amount)

    purchased_on = purchased_at = receipt_number = None
    for line in lines:
        without_times = line
        if purchased_on is None and (found := DATE_TEXT.search(line)):
            try:
                purchased_on = date(*map(int, found.groups())).isoformat()
            except ValueError:
                purchased_on = None
            without_times = line.replace(found.group(0), " ")
        if purchased_on and purchased_at is None and (found := TIME_TEXT.search(line)):
            purchased_at = found.group(0)
        if receipt_number is None and (found := RECEIPT_NUMBER.search(without_times)):
            receipt_number = found.group(0)
    return {
        "payments": [{"method": key, "amount": value} for key, value in payments.items()],
        "change": change,
        "rounding": rounding,
        "purchased_on": purchased_on,
        "purchased_at": purchased_at,
        "receipt_number": receipt_number,
    }


def merge_pages(texts: list[str]) -> str:
    """Összefűzi a képek szövegét; a két képen is látszó sorok egyszer számítanak."""
    merged = [line.strip() for line in texts[0].splitlines() if line.strip()]
    for text in texts[1:]:
        page = [line.strip() for line in text.splitlines() if line.strip()]
        keys = [match_key(line) for line in merged]
        page_keys = [match_key(line) for line in page]
        overlap = next(
            (
                size
                for size in range(min(MAX_OVERLAP_LINES, len(keys), len(page_keys)), 0, -1)
                if keys[-size:] == page_keys[:size]
            ),
            0,
        )
        merged.extend(page[overlap:])
    return "\n".join(merged)


def parse_pages(texts: list[str]) -> dict:
    """Több képnél két azonos szomszédos tétel is lehet, ezért a végösszeg dönt az átfedésről."""
    result = parse(merge_pages(texts))
    if len(texts) == 1 or items_add_up(result["items"], result["total"]):
        return result
    plain = parse("\n".join(texts))
    return plain if items_add_up(plain["items"], plain["total"]) else result


def parse(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = [line for line in lines if not line.startswith("```")]

    total_index = next((i for i, line in enumerate(lines) if is_total_line(line)), None)
    end = total_index if total_index is not None else len(lines)
    first_item = next((i for i, line in enumerate(lines[:end]) if is_item_start(line)), end)

    total = None
    footer_lines: list[str] = []
    if total_index is not None:
        match = LABELLED_LINE.match(lines[total_index])
        rest = match["rest"] if match else lines[total_index].split(maxsplit=1)[-1]
        total = labelled_amount(lines, total_index, rest)
        footer_lines = lines[total_index + 1 :]

    items, unmatched = read_items(lines[first_item:end], total)
    # Az elcsúszott sorrendet csak akkor fogadjuk el, ha azzal kijön a végösszeg.
    if not items_add_up(items, total) and first_item > 0 and BARE_AMOUNT.match(lines[first_item - 1]):
        shifted, shifted_unmatched = read_items(values_first(lines[first_item - 1 : end]), total)
        if items_add_up(shifted, total):
            items, unmatched = shifted, shifted_unmatched

    tax_number = TAX_NUMBER.search(text)
    return {
        "store_name": lines[0] if first_item > 0 and match_key(lines[0]) != "NYUGTA" else None,
        "tax_number": tax_number.group(0) if tax_number else None,
        "total": total,
        "items": items,
        "unmatched_lines": unmatched,
        **parse_footer(footer_lines),
    }
