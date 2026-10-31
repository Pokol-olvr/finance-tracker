"""A worker ciklusa: a postaládából a Garage-ba és a bronzba, majd a modellen át a lezárásig."""

import hashlib
import logging
import signal
import sys
import time

import httpx
import psycopg
from botocore.exceptions import BotoCoreError, ClientError

from app import bronze
from app.config import Settings, get_settings
from app.extract import PROMPT_VERSION, ModelMissing, ReceiptReader
from app.inbox import Inbox
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


# Ezeknél a tétel nyitva marad, és a következő körben újra próbálkozunk.
RETRYABLE = (httpx.HTTPError, BotoCoreError, ClientError, psycopg.Error, HashMismatch, ModelMissing)


def object_key(item: dict) -> str:
    year, month, _ = item["purchase_date"].split("-")
    return f"photo/{year}/{month}/{item['sha256']}.{EXTENSIONS[item['content_type']]}"


def process(
    item: dict, conn: psycopg.Connection, inbox: Inbox, storage: Storage, reader: ReceiptReader
) -> None:
    """Bármelyik lépés után újraindítható: ami már megvan, az nem íródik újra."""
    content = inbox.download(item["id"])
    if hashlib.sha256(content).hexdigest() != item["sha256"]:
        raise HashMismatch("A letöltött fájl hash-e eltér.")

    document_id = bronze.find_document(conn, item["sha256"])
    if document_id is None:
        key = object_key(item)
        storage.put(key, content, item["content_type"])
        document_id = bronze.insert_document(conn, item, key)

    version = reader.version()
    if not bronze.has_extraction(conn, document_id, reader.name, version, PROMPT_VERSION):
        payload = reader.read(content)
        bronze.insert_extraction(conn, document_id, reader.name, version, PROMPT_VERSION, payload)

    inbox.close(item["id"])


def run_once(settings: Settings, inbox: Inbox, storage: Storage, reader: ReceiptReader) -> None:
    items = inbox.list_new()
    if not items:
        return
    # Autocommit: a modell percekig is futhat, közben nem maradhat nyitva tranzakció.
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        for item in items:
            try:
                process(item, conn, inbox, storage, reader)
            except RETRYABLE as error:
                log.error("A(z) %s tétel nyitva marad: %s", item["id"], error)
            else:
                log.info("A(z) %s tétel kész.", item["id"])


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

    while True:
        try:
            run_once(settings, inbox, storage, reader)
        except RETRYABLE as error:
            log.error("A kör megszakadt: %s", error)
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    main()
