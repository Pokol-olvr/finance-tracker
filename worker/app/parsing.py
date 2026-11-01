"""A tárolt szövegek feldolgozása. Modell nélkül fut, ezért új szabályokkal bármikor megismételhető."""

import logging
from itertools import groupby
from uuid import UUID

import psycopg

from app import bronze
from app.document_parser import parse_document
from app.receipt_checks import run_checks, status_of
from app.receipt_parser import PARSER_VERSION

log = logging.getLogger("worker")

UPLOAD_DAY_LIMIT = 1


def entered_date(page: dict) -> str | None:
    """Az űrlap a mai napot kínálja fel, ezért a feltöltés napja nem számít beírt dátumnak.

    Egy nap tűrés kell, mert a feltöltés ideje UTC, a felkínált dátum pedig helyi idő.
    """
    entered = page["purchase_date"]
    if entered is None or abs((entered - page["uploaded_at"].date()).days) <= UPLOAD_DAY_LIMIT:
        return None
    return entered.isoformat()


def parse_group(conn: psycopg.Connection, group_id: UUID, pages: list[dict]) -> str:
    """Egy blokk feldolgozása; a saját hibája sem állíthatja meg a workert."""
    extraction_ids = [page["extraction_id"] for page in pages]
    texts = [page["payload"].get("ocr_text") for page in pages]
    if not all(texts):
        return store(conn, group_id, extraction_ids, "unparsed", {"error": "A kép nem olvasható"}, {})
    try:
        parsed = parse_document(texts)
    except (ValueError, IndexError, KeyError, TypeError) as error:
        log.error("A(z) %s blokk feldolgozása nem sikerült: %s", group_id, type(error).__name__)
        return store(conn, group_id, extraction_ids, "unparsed", {"error": "A feldolgozó hibázott"}, {})

    seen_elsewhere = bronze.seen_elsewhere(
        conn, group_id, parsed["tax_number"], parsed["receipt_number"]
    )
    checks = run_checks(parsed, entered_date(pages[0]), seen_elsewhere)
    return store(conn, group_id, extraction_ids, status_of(parsed, checks), parsed, checks)


def store(
    conn: psycopg.Connection,
    group_id: UUID,
    extraction_ids: list[UUID],
    status: str,
    payload: dict,
    checks: dict,
) -> str:
    bronze.insert_parse(conn, group_id, extraction_ids, PARSER_VERSION, status, payload, checks)
    return status


def parse_pending(conn: psycopg.Connection, group_id: UUID | None = None) -> int:
    """Feldolgozza, amihez ezzel a verzióval még nincs eredmény; a hiányos csoport vár."""
    rows = bronze.pending_pages(conn, PARSER_VERSION, group_id)
    done = 0
    for key, group in groupby(rows, key=lambda row: row["group_id"]):
        pages = list(group)
        if len(pages) >= pages[0]["page_count"]:
            parse_group(conn, key, pages)
            done += 1
    return done
