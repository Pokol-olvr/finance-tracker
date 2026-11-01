"""Valódi Garage és Postgres; a bronz írás visszagörget, a Garage-objektumok törlődnek."""

import hashlib

import httpx
import pytest
from app.main import HashMismatch, group_items, object_key, process, run_once
from app.storage import BUCKET
from botocore.exceptions import EndpointConnectionError
from conftest import (
    FIRST_PAGE,
    SAMPLE_TEXT,
    SECOND_PAGE,
    FakeInbox,
    FakeReader,
    invented_pdf,
    invented_receipt,
    make_group,
    make_item,
    no_report,
    scanned_pdf,
)


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
    reader = FakeReader({"ocr_text": SAMPLE_TEXT, "seconds": 80.0})

    process([item], conn, inbox, storage, reader, no_report)

    rows = documents(conn, item["sha256"])
    assert len(rows) == 1
    document_id, key, source_type, *fields = rows[0]
    assert key == f"photo/2026/11/{item['sha256']}.png"
    assert source_type == "photo"
    assert fields == ["person_a", "person_b", "shared", "2026-11-30", ["élelmiszer", "háztartás"]]
    assert hashlib.sha256(stored_bytes(storage, key)).hexdigest() == item["sha256"]
    assert extractions(conn, document_id) == [
        ("teszt-modell", "teszt-valtozat", "2", {"ocr_text": SAMPLE_TEXT, "seconds": 80.0})
    ]
    assert inbox.closed == [item["id"]]
    assert inbox.outcomes == [{"result": "ok", "seconds": 80.0, "items": 2}]


def pdf_item(content):
    return make_item(content) | {"content_type": "application/pdf"}


def test_text_pdf_is_stored_as_pdf_without_the_model(conn, storage):
    rows = [(50, 800 - 15 * row, line) for row, line in enumerate(SAMPLE_TEXT.splitlines())]
    content = invented_pdf([*rows, (50, 500, "Ez a sor a szovegreteg elegendo hosszat adja meg.")])
    item = pdf_item(content)
    inbox = FakeInbox({item["id"]: content})
    reader = FakeReader()

    process([item], conn, inbox, storage, reader, no_report)

    document_id, key, source_type, *_ = documents(conn, item["sha256"])[0]
    assert key == f"pdf/2026/11/{item['sha256']}.pdf"
    assert source_type == "pdf"
    assert reader.calls == 0
    model_name, _version, _prompt, payload = extractions(conn, document_id)[0]
    assert model_name == "pdfium"
    assert "1 048 FT" in payload["ocr_text"]
    assert inbox.outcomes == [{"result": "ok", "seconds": None, "items": 2}]


def test_scanned_pdf_goes_through_the_model(conn, storage):
    content = scanned_pdf(2)
    item = pdf_item(content)
    inbox = FakeInbox({item["id"]: content})
    reader = FakeReader({"ocr_text": SAMPLE_TEXT, "seconds": 80.0})

    process([item], conn, inbox, storage, reader, no_report)

    document_id = documents(conn, item["sha256"])[0][0]
    assert len(reader.images) == 2
    assert extractions(conn, document_id)[0][0] == "teszt-modell"
    assert inbox.outcomes[0]["seconds"] == 160.0


def test_broken_pdf_closes_as_unreadable_and_the_next_one_runs(conn, storage):
    broken = b"%PDF-1.7 serult, nincs benne semmi"
    next_content = invented_receipt()
    first = pdf_item(broken)
    second = make_item(next_content)
    inbox = FakeInbox({first["id"]: broken, second["id"]: next_content})
    reader = FakeReader()

    process([first], conn, inbox, storage, reader, no_report)
    process([second], conn, inbox, storage, reader, no_report)

    assert inbox.closed == [first["id"], second["id"]]
    assert inbox.outcomes[0] == {"result": "unreadable"}
    assert inbox.outcomes[1]["result"] == "ok"


def test_same_image_twice_is_written_once_and_both_close(conn, storage):
    content = invented_receipt()
    first = make_item(content)
    second = make_item(content) | {"purchase_date": "2026-12-05"}
    inbox = FakeInbox({first["id"]: content, second["id"]: content})
    reader = FakeReader()

    process([first], conn, inbox, storage, reader, no_report)
    process([second], conn, inbox, storage, reader, no_report)

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

    def die(_item_id, _outcome=None):
        raise httpx.ConnectError("a worker itt leállt")

    inbox.close = die
    with pytest.raises(httpx.ConnectError):
        process([item], conn, inbox, storage, reader, no_report)

    restarted = FakeInbox({item["id"]: content})
    process([item], conn, restarted, storage, reader, no_report)

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
        process([item], conn, inbox, storage, down, no_report)

    assert inbox.closed == []
    rows = documents(conn, item["sha256"])
    assert extractions(conn, rows[0][0]) == []
    assert hashlib.sha256(stored_bytes(storage, rows[0][1])).hexdigest() == item["sha256"]

    process([item], conn, inbox, storage, FakeReader(), no_report)

    assert len(extractions(conn, rows[0][0])) == 1
    assert inbox.closed == [item["id"]]


def test_failed_read_is_kept_and_item_closes(conn, storage):
    content = invented_receipt()
    item = make_item(content)
    inbox = FakeInbox({item["id"]: content})
    reader = FakeReader({"error": "A kép nem olvasható"})

    process([item], conn, inbox, storage, reader, no_report)

    document_id = documents(conn, item["sha256"])[0][0]
    assert extractions(conn, document_id)[0][3] == {"error": "A kép nem olvasható"}
    assert inbox.closed == [item["id"]]


def test_new_model_version_reads_again(conn, storage):
    content = invented_receipt()
    item = make_item(content)
    inbox = FakeInbox({item["id"]: content})
    reader = FakeReader()

    process([item], conn, inbox, storage, reader, no_report)
    reader.version = lambda: "uj-valtozat"
    process([item], conn, inbox, storage, reader, no_report)

    document_id = documents(conn, item["sha256"])[0][0]
    assert {row[1] for row in extractions(conn, document_id)} == {"teszt-valtozat", "uj-valtozat"}


def test_hash_mismatch_keeps_item_open(conn, storage):
    item = make_item(invented_receipt())
    inbox = FakeInbox({item["id"]: b"serult fajl"})

    with pytest.raises(HashMismatch):
        process([item], conn, inbox, storage, FakeReader(), no_report)

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
        process([item], conn, inbox, DownStorage(), reader, no_report)

    assert inbox.closed == []
    assert documents(conn, item["sha256"]) == []
    assert reader.calls == 0


def test_failed_item_does_not_stop_the_next_one(monkeypatch):
    processed = []

    def fake_process(items, *_):
        if items[0]["id"] == "rossz":
            raise httpx.ConnectError("hiba")
        processed.append(items[0]["id"])

    class Inbox:
        def list_new(self):
            return [
                {"id": "rossz", "group_id": None, "page_no": 1, "page_count": 1},
                {"id": "jo", "group_id": None, "page_no": 1, "page_count": 1},
            ]

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

    process([item], conn, FakeInbox({item["id"]: content}), storage, FakeReader(), steps.append)

    assert steps == ["download", "storage", "read_text", "parse", "close"]


def test_unreadable_image_is_reported_as_such(conn, storage):
    content = invented_receipt()
    item = make_item(content)
    inbox = FakeInbox({item["id"]: content})

    process([item], conn, inbox, storage, FakeReader({"error": "rossz kép"}), no_report)

    assert inbox.outcomes == [{"result": "unreadable"}]


def test_same_image_again_is_reported_as_duplicate(conn, storage):
    content = invented_receipt()
    first, second = make_item(content), make_item(content)
    inbox = FakeInbox({first["id"]: content, second["id"]: content})
    reader = FakeReader()

    process([first], conn, inbox, storage, reader, no_report)
    process([second], conn, inbox, storage, reader, no_report)

    assert inbox.outcomes[1] == {"result": "duplicate"}


def test_group_is_stored_read_and_closed_together(conn, storage):
    contents = [invented_receipt(), invented_receipt()]
    items = make_group(contents)
    inbox = FakeInbox({item["id"]: content for item, content in zip(items, contents, strict=True)})
    pages = iter([{"ocr_text": FIRST_PAGE, "seconds": 80.0}, {"ocr_text": SECOND_PAGE, "seconds": 70.0}])
    reader = FakeReader()
    reader.read = lambda _content, _report: next(pages)

    process(items, conn, inbox, storage, reader, no_report)

    assert len(storage.written) == 2
    assert inbox.closed == [item["id"] for item in items]
    assert inbox.outcomes == [{"result": "ok", "seconds": 150.0, "items": 3}, None]


def test_group_restart_does_not_read_finished_pages_again(conn, storage):
    contents = [invented_receipt(), invented_receipt()]
    items = make_group(contents)
    files = {item["id"]: content for item, content in zip(items, contents, strict=True)}
    calls = []

    def read(_content, _report):
        calls.append(1)
        if len(calls) == 2:
            raise httpx.ConnectError("a worker itt leállt")
        return {"ocr_text": FIRST_PAGE, "seconds": 80.0}

    reader = FakeReader()
    reader.read = read
    with pytest.raises(httpx.ConnectError):
        process(items, conn, FakeInbox(files), storage, reader, no_report)

    reader.read = lambda _content, _report: {"ocr_text": SECOND_PAGE, "seconds": 70.0}
    inbox = FakeInbox(files)
    process(items, conn, inbox, storage, reader, no_report)

    assert len(calls) == 2
    assert inbox.outcomes[0]["result"] == "ok"


def test_groups_wait_for_all_pages_and_sort_them():
    first = {"id": "a", "group_id": "g", "page_no": 2, "page_count": 2}
    second = {"id": "b", "group_id": "g", "page_no": 1, "page_count": 2}
    single = {"id": "c", "group_id": None, "page_no": 1, "page_count": 1}
    partial = {"id": "d", "group_id": "h", "page_no": 1, "page_count": 2}

    groups = group_items([first, second, single, partial])

    assert [[item["id"] for item in pages] for pages in groups] == [["b", "a"], ["c"]]


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


def test_object_key_keeps_pdfs_apart():
    item = {"purchase_date": "2026-12-05", "sha256": "ab", "content_type": "application/pdf"}

    assert object_key(item) == "pdf/2026/12/ab.pdf"


def test_object_key_falls_back_to_upload_month():
    item = {
        "purchase_date": None,
        "uploaded_at": "2026-11-01T10:00:00+00:00",
        "sha256": "ab",
        "content_type": "image/png",
    }

    assert object_key(item) == "photo/2026/11/ab.png"
