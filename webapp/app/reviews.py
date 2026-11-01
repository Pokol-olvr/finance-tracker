"""Az Ellenőrzés képernyő adatai. Csak a visszatöltött csomagokból dolgozik, a bronzot nem éri el."""

from app import status

RESULT_LABELS = status.RESULT_LABELS | {"non_expense": "nem kiadás"}
DECISION_LABELS = {"approved": "jóváhagyva", "corrected": "javítva", "rejected": "elvetve"}
TYPE_LABELS = {"receipt": "blokk", "invoice": "számla", "non_expense": "nem kiadás"}
NON_EXPENSE_NOTE = (
    "A modell elolvasta a dokumentumot, de ez nem kiadás, például szállítólevél, ezért nincs "
    "tétele. Ha mégis kiadásként rögzítenéd, a Javítom gomb a szövegből kinyert sorokkal indul."
)
DRAFT_NOTE = (
    "A táblázatot nem sikerült biztosan felismerni. "
    "A Javítom gomb a szövegből kinyert sorokkal indul, ezeket nézd át."
)


def money(value: float | None) -> str:
    if value is None:
        return "nincs adat"
    whole = int(value) if float(value).is_integer() else value
    return f"{status.format_number(whole)} Ft"


def check_text(key: str, check: dict) -> str:
    """Az elbukott ellenőrzés emberi nyelven, a döntéshez szükséges számokkal."""
    if key == "sum":
        return (
            f"A tételek összege {money(check.get('actual'))}, "
            f"a végösszeg {money(check.get('expected'))}."
        )
    if key == "line_total":
        return f"{check.get('wrong_lines')} sorban nem jön ki az érték a mennyiségből és az árból."
    if key == "payment":
        return f"A fizetett összeg {money(check.get('paid'))}, ez eltér a végösszegtől."
    if key == "date":
        return f"Beírt dátum: {check.get('entered')}, a dokumentumon: {check.get('read')}."
    if key == "duplicate":
        return "Ez az adószám és sorszám már szerepel egy másik dokumentumon."
    if key == "vat_summary":
        return f"Az áfaösszesítő bruttója {money(check.get('gross'))}, ez eltér a végösszegtől."
    if key == "currency":
        return f"A végösszeg nem forintban van: {check.get('currency')}."
    return key


def failed_checks(review: dict) -> list[str]:
    if "error" in review["parsed"]:
        return [review["parsed"]["error"]]
    if review["document_type"] == "non_expense":
        return []
    return [check_text(key, check) for key, check in review["checks"].items() if check.get("ok") is False]


def note_of(review: dict) -> str | None:
    if review["decision"]:
        return None
    if review["document_type"] == "non_expense":
        return NON_EXPENSE_NOTE
    return DRAFT_NOTE if review["parsed"].get("draft") else None


def state_label(review: dict) -> str:
    if review["decision"]:
        return DECISION_LABELS[review["decision"]["action"]]
    if review["document_type"] == "non_expense":
        return RESULT_LABELS["non_expense"]
    return RESULT_LABELS[review["result"]]


def shown_data(review: dict) -> dict:
    """Javítás után a javított adat látszik, a modell eredeti olvasata a csomagban marad."""
    decision = review["decision"]
    return decision["corrected"] if decision and decision["corrected"] else review["parsed"]


def summary(review: dict) -> dict:
    data = shown_data(review)
    draft = review["parsed"].get("draft") or {}
    return {
        "group_id": review["group_id"],
        "state": review["state"],
        "label": state_label(review),
        "document_type": TYPE_LABELS.get(review["document_type"], "ismeretlen"),
        "store_name": data.get("store_name") or draft.get("store_name"),
        "purchased_on": data.get("purchased_on") or draft.get("purchased_on"),
        "total": money(data.get("total")) if data.get("total") is not None else None,
        "items": len(data.get("items", [])),
        "uploaded_at": review["uploaded_at"],
        "failed": failed_checks(review) if not review["decision"] else [],
    }


def build_list(reviews: list[dict]) -> dict:
    rows = [summary(review) for review in reviews]
    return {
        "open": [row for row in rows if row["state"] == "open"],
        "closed": [row for row in rows if row["state"] == "closed"],
    }


def build_detail(review: dict) -> dict:
    parsed = shown_data(review)
    return {
        **summary(review),
        "parse_id": review["parse_id"],
        "parsed": parsed,
        "ocr_text": review["ocr_text"],
        "note": note_of(review),
        "show_text": review["document_type"] == "non_expense",
        "decision": review["decision"]
        and {
            **review["decision"],
            "label": DECISION_LABELS[review["decision"]["action"]],
        },
        "pages": [
            {
                "url": f"/reviews/{review['group_id']}/pages/{page_no}",
                "is_pdf": content_type == "application/pdf",
            }
            for page_no, content_type in enumerate(review["content_types"], 1)
        ],
    }
