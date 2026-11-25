"""A worker ciklusa: a postaládából a Garage-ba és a bronzba, majd a modellen át a lezárásig."""

import hashlib
import logging
import signal
import sys
import time
from collections.abc import Callable
from uuid import UUID

import psycopg

from app import bronze, pdf, reviews, text
from app.config import Settings, get_settings
from app.extract import PROMPT_VERSION, TRUNCATED, ModelMissing, ReceiptReader
from app.inbox import Inbox
from app.mail import MailIntake
from app.parsing import parse_pending
from app.receipt_parser import PARSER_VERSION
from app.status import StatusReporter
from app.storage import EXTENSIONS, Storage

log = logging.getLogger("worker")


class HashMismatch(Exception):
    pass


class IncompleteGroup(Exception):
    pass


# Ezeknél a tétel nyitva marad, és a következő körben újra próbálkozunk.
RETRYABLE = (*reviews.TRANSIENT, HashMismatch, IncompleteGroup, ModelMissing)


def source_type(item: dict) -> str:
    """A levélből jött dokumentum `email`, a feltöltött a fájltípusa szerint (FIN-307)."""
    if item.get("source_type"):
        return item["source_type"]
    return "pdf" if item["content_type"] == pdf.CONTENT_TYPE else "photo"


def reader_for(content_type: str, content: bytes, reader: ReceiptReader):
    """A PDF szövegrétege és a szöveges dokumentum modell nélkül olvasható."""
    if content_type == pdf.CONTENT_TYPE:
        return pdf.reader_for(content, reader)
    if content_type == text.CONTENT_TYPE:
        return text.TextReader()
    return reader


def object_key(item: dict) -> str:
    """Dátum nélküli feltöltésnél a feltöltés hónapja adja a mappát."""
    year, month = (item["purchase_date"] or item["uploaded_at"]).split("-")[:2]
    extension = EXTENSIONS[item["content_type"]]
    return f"{source_type(item)}/{year}/{month}/{item['sha256']}.{extension}"


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
    return store_content(item, content, conn, storage, reader, report)


def store_content(
    item: dict,
    content: bytes,
    conn: psycopg.Connection,
    storage: Storage,
    reader: ReceiptReader,
    report: Callable[[str], None],
) -> tuple[UUID, dict | None]:
    """A fájl a Garage-ba és a bronzba, majd a kiolvasása; a postaláda és a levél is ezt hívja."""
    document_id = bronze.find_document(conn, item["sha256"])
    if document_id is None:
        report("storage")
        key = object_key(item)
        storage.put(key, content, item["content_type"])
        document_id = bronze.insert_document(conn, item, key, source_type(item))

    payload = None
    active = reader_for(item["content_type"], content, reader)
    version = active.version()
    if not bronze.has_extraction(conn, document_id, active.name, version, PROMPT_VERSION):
        payload = active.read(content, report)
        bronze.insert_extraction(conn, document_id, active.name, version, PROMPT_VERSION, payload)
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
        reopened = reviews.reopen_rejected(conn, inbox, group_id, items[0]["uploaded_by"])
        outcome = {"result": "reopened" if reopened else "duplicate"}
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
    mail: MailIntake | None = None,
) -> None:
    groups = group_items(inbox.list_new())
    # Autocommit: a modell percekig is futhat, közben nem maradhat nyitva tranzakció.
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        reviews.sync(conn, inbox, storage)
        for items in groups:
            label = items[0]["group_id"] or items[0]["id"]
            try:
                process(items, conn, inbox, storage, reader, reporter.step)
            except RETRYABLE as error:
                log.error("A(z) %s blokk nyitva marad: %s", label, error)
            else:
                log.info("A(z) %s blokk kész.", label)
            reporter.step("idle")
            reviews.sync(conn, inbox, storage)
        if mail is not None and mail.due():

            def store(item: dict, content: bytes) -> UUID:
                return store_content(item, content, conn, storage, reader, reporter.step)[0]

            if done := mail.run(conn, storage, store, reporter.step):
                log.info("%s levél feldolgozva.", done)
                reviews.sync(conn, inbox, storage)


def reread_truncated(
    conn: psycopg.Connection, storage: Storage, reader: ReceiptReader
) -> list[UUID]:
    """A csonka olvasás újra a modellhez megy, ha azóta változott a beállítás (ADR 0012 kivétele).

    Ugyanarra a fájlra ugyanaz a beállítás ugyanazt adja, ezért csak régebbi `PROMPT_VERSION`
    csonka olvasása fut újra; a régi sor a bronzban marad, a feldolgozás a legutóbbit veszi.
    """
    done = []
    for document in bronze.truncated_documents(conn, TRUNCATED, PROMPT_VERSION):
        content = storage.get(document["object_key"])
        active = reader_for(reviews.stored_type(document["object_key"]), content, reader)
        payload = active.read(content, lambda _step: None)
        bronze.insert_extraction(
            conn, document["id"], active.name, active.version(), PROMPT_VERSION, payload
        )
        done.append(document["id"])
    return done


def reread_text_layers(conn: psycopg.Connection, storage: Storage) -> list[UUID]:
    """A szöveges PDF új sorképzése (`pdf.LAYOUT_VERSION`) a még el nem döntött dokumentumokon is.

    Modell nem kell hozzá, ezért olcsó; a döntött dokumentum olvasata nem változik. A régi sor a
    bronzban marad, a feldolgozás a `PARSER_VERSION` emelésével a legutóbbit veszi.
    """
    current = pdf.TextLayerReading({}).version()
    done = []
    for document in bronze.outdated_text_layers(conn, pdf.READER_NAME, current):
        try:
            text = pdf.text_layer(storage.get(document["object_key"]))
        except pdf.pdfium.PdfiumError:
            continue
        if not pdf.is_readable(text):
            continue
        payload = {"ocr_text": text, "done_reason": "stop", "seconds": 0}
        bronze.insert_extraction(
            conn, document["id"], pdf.READER_NAME, current, PROMPT_VERSION, payload
        )
        done.append(document["id"])
    return done


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
    reader = ReceiptReader(
        settings.ollama_url,
        settings.ollama_model,
        settings.ollama_num_thread,
        settings.ollama_keep_alive,
        settings.ollama_max_side,
    )
    try:
        with psycopg.connect(settings.database_url, autocommit=True) as conn:
            reader.history.extend(
                bronze.recent_read_stats(conn, settings.ollama_model, reader.history.maxlen)
            )
    except psycopg.Error as error:
        log.warning("A korábbi olvasások ideje nem tölthető be: %s", error)
    reporter = StatusReporter(
        settings.inbox_url,
        settings.worker_token,
        settings.ollama_url,
        settings.ollama_model,
        reader=reader,
    )
    reporter.start()
    mail = MailIntake(settings.mail) if settings.mail else None

    parsers_ready = False
    while True:
        try:
            if not parsers_ready:
                with psycopg.connect(settings.database_url, autocommit=True) as conn:
                    if reread := reread_truncated(conn, storage, reader):
                        log.info("%s csonka olvasás újraolvasva.", len(reread))
                    if reread := reread_text_layers(conn, storage):
                        log.info("%s szöveges PDF újraolvasva.", len(reread))
                reparse_stored(settings)
                parsers_ready = True
            run_once(settings, inbox, storage, reader, reporter, mail)
        except RETRYABLE as error:
            log.error("A kör megszakadt: %s", error)
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    main()
