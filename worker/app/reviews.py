"""Az ellenőrzési csomagok visszatöltése és a döntések lehúzása a bronzba.

A worker körönként összeveti a bronzot a csomagokkal, ezért az új, az újrafeldolgozott és a korábbi
dokumentum ugyanazon az úton jut a képernyőre.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import psycopg
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image

from app import bronze
from app.extract import prepare_image
from app.inbox import Inbox
from app.storage import EXTENSIONS, Storage

log = logging.getLogger("worker")

# Ezek elmúló hibák: ami most nem sikerül, a következő körben pótlódik.
TRANSIENT = (httpx.HTTPError, BotoCoreError, ClientError, psycopg.Error)

CONTENT_TYPES = {extension: content_type for content_type, extension in EXTENSIONS.items()}
HEIC_TYPE = "image/heic"
PREVIEW_TYPE = "image/jpeg"


def stored_type(object_key: str) -> str:
    return CONTENT_TYPES[object_key.rsplit(".", 1)[1]]


def shown_type(content_type: str) -> str:
    """A böngésző a HEIC-et nem tudja megjeleníteni, ezért abból JPEG-előnézet megy vissza."""
    return PREVIEW_TYPE if content_type == HEIC_TYPE else content_type


def shown_content(content: bytes, content_type: str) -> bytes:
    if content_type != HEIC_TYPE:
        return content
    try:
        return prepare_image(content)
    except (OSError, ValueError, Image.DecompressionBombError):
        # A sérült kép nem jeleníthető meg, de a csomag többi része így is hasznos.
        return content


def result_of(parse: dict) -> str:
    return "unreadable" if "error" in parse["payload"] else parse["status"]


def push(
    conn: psycopg.Connection, inbox: Inbox, storage: Storage, candidate: dict, has_files: bool
) -> None:
    """Előbb a fájlok, utána az adatok: a képernyőn csak teljes csomag jelenhet meg."""
    group_id: UUID = candidate["group_id"]
    parse = bronze.review_parse(conn, candidate["parse_id"])
    pages = bronze.review_pages(conn, group_id)
    content_types = []
    for page in pages:
        content_type = stored_type(page["object_key"])
        content_types.append(shown_type(content_type))
        if not has_files:
            content = shown_content(storage.get(page["object_key"]), content_type)
            inbox.put_review_page(group_id, page["page_no"], content)
    inbox.put_review(
        group_id,
        {
            "parse_id": str(parse["id"]),
            "parser_version": parse["parser_version"],
            "result": result_of(parse),
            "document_type": parse["payload"].get("document_type"),
            "parsed": parse["payload"],
            "checks": parse["checks"],
            "ocr_text": "\n\n".join(page["ocr_text"] or "" for page in pages),
            "uploaded_at": candidate["uploaded_at"].isoformat(),
            "content_types": content_types,
            "sha256s": [page["sha256"] for page in pages],
        },
    )


def pull_decisions(conn: psycopg.Connection, inbox: Inbox) -> None:
    """A bronzba írás után nyugtáz, ezért a megszakadt kör nem veszít döntést."""
    for decision in inbox.open_decisions():
        bronze.insert_decision(conn, decision)
        inbox.close_decision(decision["id"])


def pull_events(conn: psycopg.Connection, inbox: Inbox) -> None:
    """A szabályok és a kézi betétdíj-műveletek ugyanúgy jutnak a bronzba, mint a döntések."""
    writers = {
        "rule_event": bronze.insert_rule_event,
        "deposit_correction": bronze.insert_deposit_correction,
    }
    for event in inbox.open_events():
        writers[event["event_type"]](conn, event["data"])
        inbox.close_event(event["id"])


def reopen_rejected(conn: psycopg.Connection, inbox: Inbox, group_id: UUID, decided_by: str) -> bool:
    """Az elvetett dokumentum újrafeltöltése újranyit: a modellt nem érdemes újra futtatni.

    Előbb a bronz, utána a webapp, ezért megszakadás után a következő kör ugyanazzal az
    azonosítóval folytatja. A hiányzó csomagot a `sync` pótolja.
    """
    latest = bronze.latest_decision(conn, group_id)
    if latest is None or latest["decision"] not in ("rejected", "reopened"):
        return False
    decision_id = latest["id"]
    if latest["decision"] == "rejected":
        decision_id = uuid4()
        bronze.insert_decision(
            conn,
            {
                "id": decision_id,
                "group_id": group_id,
                "parse_id": bronze.latest_parse_id(conn, group_id),
                "action": "reopened",
                "corrected": None,
                "decided_by": decided_by,
                "decided_at": datetime.now(UTC),
            },
        )
    inbox.reopen_review(group_id, decision_id, decided_by)
    return True


def report_deposit(conn: psycopg.Connection, inbox: Inbox) -> None:
    """Az első dbt-futás előtt a gold még üres, ez a csomagokat nem akadályozhatja."""
    try:
        inbox.report_deposit(bronze.deposit_report(conn))
    except TRANSIENT as error:
        log.error("A várható betétdíj nem tölthető vissza: %s", error)


def sync(conn: psycopg.Connection, inbox: Inbox, storage: Storage) -> None:
    """Soha nem állítja meg a feldolgozást: a hiba a következő körben pótlódik."""
    report_deposit(conn, inbox)
    try:
        pull_decisions(conn, inbox)
        pull_events(conn, inbox)
        known = inbox.known_reviews()
        candidates = bronze.review_candidates(conn)
    except TRANSIENT as error:
        log.error("Az ellenőrzési csomagok összevetése nem sikerült: %s", error)
        return

    for candidate in candidates:
        have = known.get(str(candidate["group_id"]))
        if have and (have["decided"] or have["parse_id"] == str(candidate["parse_id"])):
            continue
        try:
            push(conn, inbox, storage, candidate, has_files=have is not None)
        except TRANSIENT as error:
            log.error("A(z) %s csomag nem tölthető vissza: %s", candidate["group_id"], error)
