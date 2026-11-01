"""Valódi Garage és Postgres; a bronz írás visszagörget, a Garage-objektumok törlődnek."""

import hashlib

import httpx
import pytest
from app.main import HashMismatch, object_key, outcome_of, process, run_once
from app.storage import BUCKET
from botocore.exceptions import EndpointConnectionError
from conftest import FakeInbox, FakeReader, invented_receipt, make_item, no_report


def documents(conn, sha256):
    return conn.execute(
        "select id, object_key, source_type, uploaded_by, purchased_by, payer, "
        "purchase_date::text, tags from bronze.raw_document where sha256 = %s",
        (sha256,),
    ).fetchall()


def extractions(conn, document_id):
    return conn.execute(
        "select model_name, model_version, prompt_version, payload from bronze.extraction "
        "where document_id = %s",
        (document_id,),
    ).fetchall()


def stored_bytes(storage, key):
    return storage.client.get_object(Bucket=BUCKET, Key=key)["Body"].read()


def test_item_reaches_garage_and_bronze_then_closes(conn, storage):
    content = invented_receipt()
    item = make_item(content)
    inbox = FakeInbox({item["id"]: content})
    reader = FakeReader({"raw_text": "{}", "parsed": {"store": "TESZT"}})

    process(item, conn, inbox, storage, reader, no_report)

    rows = documents(conn, item["sha256"])
    assert len(rows) == 1
    document_id, key, source_type, *fields = rows[0]
    assert key == f"photo/2026/11/{item['sha256']}.png"
    assert source_type == "photo"
    assert fields == ["person_a", "person_b", "shared", "2026-11-30", ["élelmiszer", "háztartás"]]
    assert hashlib.sha256(stored_bytes(storage, key)).hexdigest() == item["sha256"]
    assert extractions(conn, document_id) == [
        ("teszt-modell", "teszt-valtozat", "1", {"raw_text": "{}", "parsed": {"store": "TESZT"}})
    ]
    assert inbox.closed == [item["id"]]


def test_same_image_twice_is_written_once_and_both_close(conn, storage):
    content = invented_receipt()
    first = make_item(content)
    second = make_item(content) | {"purchase_date": "2026-12-05"}
    inbox = FakeInbox({first["id"]: content, second["id"]: content})
    reader = FakeReader()

    process(first, conn, inbox, storage, reader, no_report)
    process(second, conn, inbox, storage, reader, no_report)

    rows = documents(conn, first["sha256"])
    assert len(rows) == 1
    assert len(storage.written) == 1
    assert len(extractions(conn, rows[0][0])) == 1
    assert reader.calls == 1
    assert inbox.closed == [first["id"], second["id"]]


def test_restart_before_close_finishes_without_duplicate(conn, storage):
    content = invented_receipt()
    item = make_item(content)
    inbox = FakeInbox({item["id"]: content})
    reader = FakeReader()

    def die(_item_id, _outcome):
        raise httpx.ConnectError("a worker itt leállt")

    inbox.close = die
    with pytest.raises(httpx.ConnectError):
        process(item, conn, inbox, storage, reader, no_report)

    restarted = FakeInbox({item["id"]: content})
    process(item, conn, restarted, storage, reader, no_report)

    rows = documents(conn, item["sha256"])
    assert len(rows) == 1
    assert len(extractions(conn, rows[0][0])) == 1
    assert reader.calls == 1
    assert restarted.closed == [item["id"]]


def test_unreachable_model_keeps_item_open_and_raw_file_safe(conn, storage):
    content = invented_receipt()
    item = make_item(content)
    inbox = FakeInbox({item["id"]: content})
    down = FakeReader(error=httpx.ConnectError("az Ollama nem érhető el"))

    with pytest.raises(httpx.ConnectError):
        process(item, conn, inbox, storage, down, no_report)

    assert inbox.closed == []
    rows = documents(conn, item["sha256"])
    assert extractions(conn, rows[0][0]) == []
    assert hashlib.sha256(stored_bytes(storage, rows[0][1])).hexdigest() == item["sha256"]

    process(item, conn, inbox, storage, FakeReader(), no_report)

    assert len(extractions(conn, rows[0][0])) == 1
    assert inbox.closed == [item["id"]]


def test_failed_read_is_kept_and_item_closes(conn, storage):
    content = invented_receipt()
    item = make_item(content)
    inbox = FakeInbox({item["id"]: content})
    reader = FakeReader({"error": "A kép nem olvasható"})

    process(item, conn, inbox, storage, reader, no_report)

    document_id = documents(conn, item["sha256"])[0][0]
    assert extractions(conn, document_id)[0][3] == {"error": "A kép nem olvasható"}
    assert inbox.closed == [item["id"]]


def test_new_model_version_reads_again(conn, storage):
    content = invented_receipt()
    item = make_item(content)
    inbox = FakeInbox({item["id"]: content})
    reader = FakeReader()

    process(item, conn, inbox, storage, reader, no_report)
    reader.version = lambda: "uj-valtozat"
    process(item, conn, inbox, storage, reader, no_report)

    document_id = documents(conn, item["sha256"])[0][0]
    assert {row[1] for row in extractions(conn, document_id)} == {"teszt-valtozat", "uj-valtozat"}


def test_hash_mismatch_keeps_item_open(conn, storage):
    item = make_item(invented_receipt())
    inbox = FakeInbox({item["id"]: b"serult fajl"})

    with pytest.raises(HashMismatch):
        process(item, conn, inbox, storage, FakeReader(), no_report)

    assert inbox.closed == []
    assert documents(conn, item["sha256"]) == []
    assert storage.written == []


def test_unreachable_garage_keeps_item_open(conn):
    class DownStorage:
        def put(self, key, content, content_type):
            raise EndpointConnectionError(endpoint_url="http://garage:3900")

    content = invented_receipt()
    item = make_item(content)
    inbox = FakeInbox({item["id"]: content})
    reader = FakeReader()

    with pytest.raises(EndpointConnectionError):
        process(item, conn, inbox, DownStorage(), reader, no_report)

    assert inbox.closed == []
    assert documents(conn, item["sha256"]) == []
    assert reader.calls == 0


def test_failed_item_does_not_stop_the_next_one(monkeypatch):
    processed = []

    def fake_process(item, *_):
        if item["id"] == "rossz":
            raise httpx.ConnectError("hiba")
        processed.append(item["id"])

    class Inbox:
        def list_new(self):
            return [{"id": "rossz"}, {"id": "jo"}]

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("app.main.process", fake_process)
    monkeypatch.setattr("app.main.psycopg.connect", lambda *_, **__: Connection())

    class Settings:
        database_url = "postgresql://unused"

    steps = []

    class Reporter:
        step = staticmethod(steps.append)

    run_once(Settings(), Inbox(), None, None, Reporter())

    assert processed == ["jo"]
    assert steps == ["idle", "idle"]


def test_steps_are_reported_in_order(conn, storage):
    content = invented_receipt()
    item = make_item(content)
    steps = []

    process(item, conn, FakeInbox({item["id"]: content}), storage, FakeReader(), steps.append)

    assert steps == ["download", "storage", "read_json", "close"]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (None, {"result": "duplicate"}),
        ({"error": "A kép nem olvasható"}, {"result": "unreadable"}),
        ({"parsed": None, "seconds": 80.0}, {"result": "unparsed", "seconds": 80.0}),
        (
            {"parsed": {"items": [{}, {}]}, "seconds": 80.0},
            {"result": "ok", "seconds": 80.0, "items": 2},
        ),
        ({"parsed": {}, "seconds": 80.0}, {"result": "ok", "seconds": 80.0, "items": 0}),
    ],
)
def test_outcome_has_no_receipt_content(payload, expected):
    assert outcome_of(payload) == expected


@pytest.mark.parametrize(
    ("content_type", "extension"),
    [
        ("image/jpeg", "jpg"),
        ("image/png", "png"),
        ("image/heic", "heic"),
        ("image/webp", "webp"),
    ],
)
def test_object_key_uses_month_and_extension(content_type, extension):
    item = {"purchase_date": "2026-12-05", "sha256": "ab", "content_type": content_type}

    assert object_key(item) == f"photo/2026/12/ab.{extension}"
