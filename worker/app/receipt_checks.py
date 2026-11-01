"""A feldolgozott blokk ellenőrzései. Az `ok: None` azt jelenti, hogy az ellenőrzés nem futhatott."""

# Készpénznél a végösszeg 0-ra vagy 5-re kerekedik, ezért legfeljebb ennyi lehet az eltérés.
CASH_ROUNDING_LIMIT = 2
LINE_TOTAL_LIMIT = 1


def check_sum(parsed: dict) -> dict:
    actual = sum(item["value"] or 0 for item in parsed["items"])
    return {"ok": actual == parsed["total"], "expected": parsed["total"], "actual": actual}


def check_line_totals(parsed: dict) -> dict:
    with_quantity = [
        item
        for item in parsed["items"]
        if item["quantity"] is not None and item["unit_price"] is not None
    ]
    if not with_quantity:
        return {"ok": None}
    wrong = sum(
        1
        for item in with_quantity
        if item["value"] is None
        or abs(item["quantity"] * item["unit_price"] - item["value"]) > LINE_TOTAL_LIMIT
    )
    return {"ok": wrong == 0, "wrong_lines": wrong, "checked_lines": len(with_quantity)}


def check_payment(parsed: dict) -> dict:
    payments = parsed["payments"]
    if not payments or parsed["total"] is None:
        return {"ok": None}
    paid = sum(payment["amount"] for payment in payments) - (parsed["change"] or 0)
    limit = CASH_ROUNDING_LIMIT if any(p["method"] == "cash" for p in payments) else 0
    return {"ok": abs(paid - parsed["total"]) <= limit, "paid": paid}


def check_invoice_sum(parsed: dict) -> dict:
    """A számla végösszegét kulcsonként kerekítik, ezért a tételek bruttója kicsit eltérhet."""
    if parsed["total"] is None:
        return {"ok": None}
    actual = sum(item["value"] or 0 for item in parsed["items"])
    ok = abs(actual - parsed["total"]) <= CASH_ROUNDING_LIMIT
    return {"ok": ok, "expected": parsed["total"], "actual": actual}


def is_wrong_invoice_line(item: dict) -> bool:
    expected = None
    if item["quantity"] is not None and item["unit_price"] is not None:
        expected = item["quantity"] * item["unit_price"]
    return abs(item["net"] + item["vat"] - item["value"]) > LINE_TOTAL_LIMIT or (
        expected is not None
        and abs(expected - item["net"]) > LINE_TOTAL_LIMIT
        and abs(expected - item["value"]) > LINE_TOTAL_LIMIT
    )


def check_invoice_lines(parsed: dict) -> dict:
    if not parsed["items"]:
        return {"ok": None}
    wrong = sum(1 for item in parsed["items"] if is_wrong_invoice_line(item))
    return {"ok": wrong == 0, "wrong_lines": wrong, "checked_lines": len(parsed["items"])}


def check_vat_summary(parsed: dict) -> dict:
    """Az Összesen sor a teljes számlát adja, enélkül a kulcsonkénti sorok összege számít."""
    rows = parsed["vat_summary"]
    if not rows or parsed["total"] is None:
        return {"ok": None}
    whole = [row["gross"] for row in rows if row["rate"] is None]
    gross = whole[0] if whole else sum(row["gross"] for row in rows)
    return {"ok": abs(gross - parsed["total"]) <= CASH_ROUNDING_LIMIT, "gross": gross}


def check_currency(parsed: dict) -> dict:
    if parsed["currency"] is None:
        return {"ok": None}
    return {"ok": parsed["currency"] == "HUF", "currency": parsed["currency"]}


def check_date(parsed: dict, entered_date: str | None) -> dict:
    if entered_date is None or parsed["purchased_on"] is None:
        return {"ok": None}
    return {
        "ok": entered_date == parsed["purchased_on"],
        "entered": entered_date,
        "read": parsed["purchased_on"],
    }


def check_duplicate(parsed: dict, seen_elsewhere: bool) -> dict:
    if parsed["tax_number"] is None or parsed["receipt_number"] is None:
        return {"ok": None}
    return {"ok": not seen_elsewhere}


def run_checks(parsed: dict, entered_date: str | None, seen_elsewhere: bool) -> dict:
    common = {
        "date": check_date(parsed, entered_date),
        "duplicate": check_duplicate(parsed, seen_elsewhere),
    }
    if parsed.get("document_type") == "invoice":
        return {
            "sum": check_invoice_sum(parsed),
            "line_total": check_invoice_lines(parsed),
            "vat_summary": check_vat_summary(parsed),
            "currency": check_currency(parsed),
            "payment": check_payment(parsed),
            **common,
        }
    return {
        "sum": check_sum(parsed),
        "line_total": check_line_totals(parsed),
        "payment": check_payment(parsed),
        **common,
    }


def status_of(parsed: dict, checks: dict) -> str:
    """A tétel nélküli számla ellenőrzésre megy: a végösszege így sem vész el."""
    is_invoice = parsed.get("document_type") == "invoice"
    if parsed["total"] is None or (not parsed["items"] and not is_invoice):
        return "unparsed"
    return "review" if any(check["ok"] is False for check in checks.values()) else "ok"
