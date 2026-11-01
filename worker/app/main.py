"""A worker ciklusa: a postaládából a Garage-ba és a bronzba, majd a modellen át a lezárásig."""

import hashlib
import logging
import signal
import sys
import time
from collections.abc import Callable
from uuid import UUID

import httpx
import psycopg
from botocore.exceptions import BotoCoreError, ClientError

from app import bronze
from app.config import Settings, get_settings
from app.extract import PROMPT_VERSION, ModelMissing, ReceiptReader
from app.inbox import Inbox
from app.parsing import parse_pending
from app.receipt_parser import PARSER_VERSION
from app.status import StatusReporter
from app.storage import Storage

log = logging.getLogger("worker")

EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/heic": "heic",
    "image/webp": "webp",
}


class HashMismatch(Exception):
    pass


class IncompleteGroup(Exception):
    pass


# Ezeknél a tétel nyitva marad, és a következő körben újra próbálkozunk.
RETRYABLE = (
    httpx.HTTPError,
    BotoCoreError,
    ClientError,
    psycopg.Error,
    HashMismatch,
    IncompleteGroup,
    ModelMissing,
)


def object_key(item: dict) -> str:
    """Dátum nélküli feltöltésnél a feltöltés hónapja adja a mappát."""
    year, month = (item["purchase_date"] or item["uploaded_at"]).split("-")[:2]
    return f"photo/{year}/{month}/{item['sha256']}.{EXTENSIONS[item['content_type']]}"


def outcome_of(status: str, items: int, seconds: float | None, readable: bool) -> dict:
    """Az állapotoldal sora: nincs benne blokktartalom, csak az eredmény, az idő és a tételszám."""
    if not readable:
        return {"result": "unreadable"}
    return {"result": status, "seconds": seconds, "items": items}


def store_page(
    item: dict,
    conn: psycopg.Connection,
    inbox: Inbox,
    storage: Storage,
    reader: ReceiptReader,
    report: Callable[[str], None],
) -> tuple[UUID, dict | None]:
    report("download")
    content = inbox.download(item["id"])
    if hashlib.sha256(content).hexdigest() != item["sha256"]:
        raise HashMismatch("A letöltött fájl hash-e eltér.")

    document_id = bronze.find_document(conn, item["sha256"])
    if document_id is None:
        report("storage")
        key = object_key(item)
        storage.put(key, content, item["content_type"])
        document_id = bronze.insert_document(conn, item, key)

    payload = None
    version = reader.version()
    if not bronze.has_extraction(conn, document_id, reader.name, version, PROMPT_VERSION):
        payload = reader.read(content, report)
        bronze.insert_extraction(conn, document_id, reader.name, version, PROMPT_VERSION, payload)
    return document_id, payload


def process(
    items: list[dict],
    conn: psycopg.Connection,
    inbox: Inbox,
    storage: Storage,
    reader: ReceiptReader,
    report: Callable[[str], None],
) -> None:
    """Egy blokk minden képe. Bármelyik lépés után újraindítható, ami megvan, nem íródik újra."""
    stored = [store_page(item, conn, inbox, storage, reader, report) for item in items]
    payloads = [payload for _, payload in stored if payload is not None]
    group_id = bronze.group_of(conn, stored[0][0])

    report("parse")
    previous = bronze.parse_result(conn, group_id, PARSER_VERSION)
    parse_pending(conn, group_id)
    result = bronze.parse_result(conn, group_id, PARSER_VERSION)

    if not payloads and previous is not None:
        outcome = {"result": "duplicate"}
    elif result is None:
        raise IncompleteGroup("A csoport nem minden képe van meg.")
    else:
        seconds = round(sum(payload.get("seconds", 0) for payload in payloads), 1) or None
        readable = not any("error" in payload for payload in payloads)
        outcome = outcome_of(result[0], result[1], seconds, readable)

    report("close")
    # A blokk eredménye az első képhez tartozik, így az állapotoldal blokkot számol.
    for position, item in enumerate(items):
        inbox.close(item["id"], outcome if position == 0 else None)


def group_items(items: list[dict]) -> list[list[dict]]:
    """Blokkonként csoportosít, oldalsorrendben; a hiányos csoport a következő körre vár."""
    groups: dict[str, list[dict]] = {}
    for item in items:
        groups.setdefault(item["group_id"] or item["id"], []).append(item)
    complete = [pages for pages in groups.values() if len(pages) == pages[0]["page_count"]]
    return [sorted(pages, key=lambda page: page["page_no"]) for pages in complete]


def run_once(
    settings: Settings,
    inbox: Inbox,
    storage: Storage,
    reader: ReceiptReader,
    reporter: StatusReporter,
) -> None:
    groups = group_items(inbox.list_new())
    if not groups:
        return
    # Autocommit: a modell percekig is futhat, közben nem maradhat nyitva tranzakció.
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        for items in groups:
            label = items[0]["group_id"] or items[0]["id"]
            try:
                process(items, conn, inbox, storage, reader, reporter.step)
            except RETRYABLE as error:
                log.error("A(z) %s blokk nyitva marad: %s", label, error)
            else:
                log.info("A(z) %s blokk kész.", label)
            reporter.step("idle")


def reparse_stored(settings: Settings) -> None:
    """Új `PARSER_VERSION` után a meglévő szövegek is feldolgozódnak, modellfutás nélkül."""
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        done = parse_pending(conn)
    if done:
        log.info("%s tárolt blokk feldolgozva.", done)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # A httpx minden kérést naplóz, ami a percenkénti lekérdezéssel csak zaj.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # Konténerben 1-es folyamatként fut, itt a SIGTERM kezelő nélkül hatástalan.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    settings = get_settings()
    inbox = Inbox(settings.inbox_url, settings.worker_token)
    storage = Storage(
        settings.garage_endpoint, settings.garage_access_key, settings.garage_secret_key
    )
    reader = ReceiptReader(settings.ollama_url, settings.ollama_model, settings.ollama_num_thread)
    reporter = StatusReporter(
        settings.inbox_url, settings.worker_token, settings.ollama_url, settings.ollama_model
    )
    reporter.start()

    parsers_ready = False
    while True:
        try:
            if not parsers_ready:
                reparse_stored(settings)
                parsers_ready = True
            run_once(settings, inbox, storage, reader, reporter)
        except RETRYABLE as error:
            log.error("A kör megszakadt: %s", error)
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    main()
