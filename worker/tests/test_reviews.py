"""Valódi Garage és Postgres; a bronz írás visszagörget, a Garage-objektumok törlődnek."""

from io import BytesIO
from uuid import uuid4

import httpx
import pytest
from app import bronze, reviews
from app.inbox import Inbox
from app.main import process
from conftest import (
    SAMPLE_TEXT,
    FakeInbox,
    FakeReader,
    invented_receipt,
    make_group,
    make_item,
    no_report,
)
from PIL import Image

BAD_TEXT = "NYUGTA\nC00 KENYÉR 500G 599\nÖSSZESEN: 700 FT\n"


@pytest.fixture(autouse=True)
def only_this_test(request, monkeypatch):
    """A tesztek a helyi stacken is futnak, ahol már vannak dokumentumok."""
    if "conn" in request.fixturenames:
        original = bronze.review_candidates
        existing = {row["group_id"] for row in original(request.getfixturevalue("conn"))}

        def new_ones(conn):
            return [row for row in original(conn) if row["group_id"] not in existing]

        monkeypatch.setattr("app.bronze.review_candidates", new_ones)


def stored_review(conn, storage, inbox, text=SAMPLE_TEXT, **changes) -> dict:
    content = invented_receipt()
    item = make_item(content) | changes
    inbox.files[item["id"]] = content
    process([item], conn, inbox, storage, FakeReader({"ocr_text": text}), no_report)
    return item


def test_new_document_gets_a_package_with_its_file(conn, storage):
    inbox = FakeInbox({})
    content = invented_receipt()
    item = make_item(content)
    inbox.files[item["id"]] = content
    process([item], conn, inbox, storage, FakeReader({"ocr_text": BAD_TEXT}), no_report)

    reviews.sync(conn, inbox, storage)

    (group_id, package), = inbox.reviews.items()
    assert package["result"] == "review"
    assert package["parsed"]["total"] == 700
    assert package["checks"]["sum"]["ok"] is False
    assert package["ocr_text"] == BAD_TEXT
    assert package["content_types"] == ["image/png"]
    assert package["sha256s"] == [item["sha256"]]
    assert inbox.pages[(group_id, 1)] == content


def test_package_is_not_sent_twice(conn, storage):
    inbox = FakeInbox({})
    stored_review(conn, storage, inbox)
    reviews.sync(conn, inbox, storage)
    inbox.pages.clear()
    package = next(iter(inbox.reviews.values()))
    inbox.reviews[next(iter(inbox.reviews))] = package | {"sent_once": True}

    reviews.sync(conn, inbox, storage)

    assert next(iter(inbox.reviews.values()))["sent_once"] is True
    assert inbox.pages == {}


def test_new_reading_replaces_the_data_without_the_files(conn, storage):
    inbox = FakeInbox({})
    stored_review(conn, storage, inbox, text=BAD_TEXT)
    reviews.sync(conn, inbox, storage)
    inbox.pages.clear()
    group_id, package = next(iter(inbox.reviews.items()))
    assert package["result"] == "review"
    # A teszt egy tranzakció, ezért a sorrendhez kell a későbbi időpont.
    conn.execute(
        "insert into bronze.receipt_parse "
        "(group_id, extraction_ids, parser_version, status, payload, checks, created_at) "
        "values (%s, '{}', 'teszt-uj', 'ok', '{\"total\": 599}', '{}', now() + interval '1 minute')",
        (group_id,),
    )

    reviews.sync(conn, inbox, storage)

    assert inbox.reviews[group_id]["result"] == "ok"
    assert inbox.reviews[group_id]["parser_version"] == "teszt-uj"
    assert inbox.pages == {}


def test_lost_package_is_sent_again_with_files(conn, storage):
    inbox = FakeInbox({})
    stored_review(conn, storage, inbox)
    reviews.sync(conn, inbox, storage)
    inbox.reviews.clear()
    inbox.pages.clear()

    reviews.sync(conn, inbox, storage)

    assert len(inbox.reviews) == 1
    assert len(inbox.pages) == 1


def test_all_pages_of_a_long_receipt_are_sent(conn, storage):
    inbox = FakeInbox({})
    contents = [invented_receipt(), invented_receipt()]
    pages = make_group(contents)
    inbox.files |= {item["id"]: content for item, content in zip(pages, contents, strict=True)}
    process(pages, conn, inbox, storage, FakeReader(), no_report)

    reviews.sync(conn, inbox, storage)

    (group_id, package), = inbox.reviews.items()
    assert package["content_types"] == ["image/png", "image/png"]
    assert inbox.pages[(group_id, 1)] == contents[0]
    assert inbox.pages[(group_id, 2)] == contents[1]


def test_heic_goes_back_as_jpeg(conn, storage):
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format="HEIF")
    item = make_item(buffer.getvalue()) | {"content_type": "image/heic"}
    inbox = FakeInbox({item["id"]: buffer.getvalue()})
    process([item], conn, inbox, storage, FakeReader(), no_report)

    reviews.sync(conn, inbox, storage)

    (group_id, package), = inbox.reviews.items()
    assert package["content_types"] == ["image/jpeg"]
    assert inbox.pages[(group_id, 1)].startswith(b"\xff\xd8\xff")


def test_unreadable_document_is_marked(conn, storage):
    inbox = FakeInbox({})
    content = invented_receipt()
    item = make_item(content)
    inbox.files[item["id"]] = content
    process([item], conn, inbox, storage, FakeReader({"error": "nem olvasható"}), no_report)

    reviews.sync(conn, inbox, storage)

    assert next(iter(inbox.reviews.values()))["result"] == "unreadable"


def decision_for(conn, inbox, action="approved", corrected=None) -> dict:
    group_id, package = next(iter(inbox.reviews.items()))
    return {
        "id": str(uuid4()),
        "group_id": group_id,
        "parse_id": package["parse_id"],
        "action": action,
        "corrected": corrected,
        "decided_by": "person_a",
        "decided_at": "2026-10-01T10:00:00+00:00",
    }


def decisions_in_bronze(conn, group_id):
    return conn.execute(
        "select decision, corrected, decided_by from bronze.review_decision "
        "where group_id = %s order by decided_at",
        (group_id,),
    ).fetchall()


def test_decision_reaches_bronze_and_is_acknowledged(conn, storage):
    inbox = FakeInbox({})
    stored_review(conn, storage, inbox)
    reviews.sync(conn, inbox, storage)
    corrected = {"total": 1000, "items": [{"name": "KENYÉR", "value": 1000}]}
    decision = decision_for(conn, inbox, "corrected", corrected)
    inbox.decisions.append(decision)

    reviews.sync(conn, inbox, storage)

    assert decisions_in_bronze(conn, decision["group_id"]) == [("corrected", corrected, "person_a")]
    assert inbox.synced == [decision["id"]]


def test_repeated_decision_is_stored_once(conn, storage):
    inbox = FakeInbox({})
    stored_review(conn, storage, inbox)
    reviews.sync(conn, inbox, storage)
    decision = decision_for(conn, inbox)

    bronze.insert_decision(conn, decision)
    inbox.decisions.append(decision)
    reviews.sync(conn, inbox, storage)

    assert len(decisions_in_bronze(conn, decision["group_id"])) == 1


def rejected_document(conn, storage, inbox) -> tuple[dict, bytes, str]:
    content = invented_receipt()
    item = make_item(content)
    inbox.files[item["id"]] = content
    process([item], conn, inbox, storage, FakeReader({"ocr_text": BAD_TEXT}), no_report)
    reviews.sync(conn, inbox, storage)
    group_id = next(iter(inbox.reviews))
    inbox.decisions.append(decision_for(conn, inbox, "rejected"))
    reviews.sync(conn, inbox, storage)
    return item, content, group_id


def test_uploading_a_rejected_file_again_reopens_it_without_the_model(conn, storage):
    inbox = FakeInbox({})
    first, content, group_id = rejected_document(conn, storage, inbox)
    again = make_item(content)
    inbox.files[again["id"]] = content
    reader = FakeReader()

    process([again], conn, inbox, storage, reader, no_report)

    assert reader.calls == 0
    assert inbox.outcomes[-1] == {"result": "reopened"}
    assert [row[0] for row in inbox.reopened] == [group_id]
    assert [row[0] for row in decisions_in_bronze(conn, group_id)] == ["rejected", "reopened"]
    assert first["sha256"] == again["sha256"]


def test_interrupted_reopen_uses_the_same_decision_again(conn, storage):
    inbox = FakeInbox({})
    _, _, group_id = rejected_document(conn, storage, inbox)

    assert reviews.reopen_rejected(conn, inbox, group_id, "person_a") is True
    assert reviews.reopen_rejected(conn, inbox, group_id, "person_a") is True

    assert len(decisions_in_bronze(conn, group_id)) == 2
    assert inbox.reopened[0] == inbox.reopened[1]


def test_uploading_an_accepted_file_again_stays_a_duplicate(conn, storage):
    inbox = FakeInbox({})
    content = invented_receipt()
    first = make_item(content)
    second = make_item(content)
    inbox.files |= {first["id"]: content, second["id"]: content}
    reader = FakeReader()
    process([first], conn, inbox, storage, reader, no_report)

    process([second], conn, inbox, storage, reader, no_report)

    assert inbox.outcomes[-1] == {"result": "duplicate"}
    assert inbox.reopened == []


def test_reopened_document_is_sent_again_when_its_package_is_gone(conn, storage):
    inbox = FakeInbox({})
    _, _, group_id = rejected_document(conn, storage, inbox)
    reviews.reopen_rejected(conn, inbox, group_id, "person_a")
    inbox.reviews.clear()
    inbox.pages.clear()

    reviews.sync(conn, inbox, storage)

    assert list(inbox.reviews) == [group_id]
    assert len(inbox.pages) == 1


def test_decided_document_is_not_sent_again(conn, storage):
    inbox = FakeInbox({})
    stored_review(conn, storage, inbox)
    reviews.sync(conn, inbox, storage)
    decision = decision_for(conn, inbox)
    inbox.decisions.append(decision)
    reviews.sync(conn, inbox, storage)
    inbox.reviews.clear()

    reviews.sync(conn, inbox, storage)

    assert inbox.reviews == {}


def test_old_ok_document_is_not_sent_but_an_old_open_one_is(conn, storage):
    inbox = FakeInbox({})
    stored_review(conn, storage, inbox, uploaded_at="2020-01-01T10:00:00+00:00")
    assert inbox.reviews == {}
    reviews.sync(conn, inbox, storage)
    assert inbox.reviews == {}

    stored_review(conn, storage, inbox, text=BAD_TEXT, uploaded_at="2020-01-01T10:00:00+00:00")
    reviews.sync(conn, inbox, storage)

    assert [package["result"] for package in inbox.reviews.values()] == ["review"]


def test_failure_does_not_stop_the_processing(conn):
    class BrokenInbox:
        def open_decisions(self):
            raise httpx.ConnectError("hiba")

    reviews.sync(conn, BrokenInbox(), None)


def test_failed_package_does_not_stop_the_others(conn, storage):
    class Unreliable(FakeInbox):
        failed = False

        def put_review(self, group_id, package):
            if not self.failed:
                self.failed = True
                raise httpx.ConnectError("hiba")
            super().put_review(group_id, package)

    inbox = Unreliable({})
    stored_review(conn, storage, inbox)
    stored_review(conn, storage, inbox)

    reviews.sync(conn, inbox, storage)

    assert len(inbox.reviews) == 1


@pytest.mark.parametrize(
    ("key", "expected"),
    [("photo/2026/12/ab.heic", "image/heic"), ("pdf/2026/12/ab.pdf", "application/pdf")],
)
def test_type_comes_from_the_stored_name(key, expected):
    assert reviews.stored_type(key) == expected


def test_inbox_client_paths():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.url.path == "/inbox/reviews":
            return httpx.Response(200, json={"reviews": [{"group_id": "a", "decided": False}]})
        if request.url.path == "/inbox/decisions":
            return httpx.Response(200, json={"decisions": []})
        return httpx.Response(204)

    client = Inbox("http://webapp:8000", "titok", transport=httpx.MockTransport(handler))

    assert client.known_reviews() == {"a": {"group_id": "a", "decided": False}}
    assert client.open_decisions() == []
    client.put_review_page("a", 1, b"x")
    client.put_review("a", {})
    client.close_decision("b")

    assert seen == [
        ("GET", "/inbox/reviews"),
        ("GET", "/inbox/decisions"),
        ("PUT", "/inbox/reviews/a/pages/1"),
        ("PUT", "/inbox/reviews/a"),
        ("POST", "/inbox/decisions/b/close"),
    ]
