import hashlib
import sqlite3
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from app import inbox, main
from fastapi.testclient import TestClient
from PIL import Image


def image_bytes(image_format: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 16), "white").save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.fixture
def client(inbox_dir):
    return TestClient(main.app)


@pytest.fixture
def worker_headers():
    return {"Authorization": "Bearer teszt-token"}


@pytest.fixture
def valid_form():
    return {
        "uploaded_by": "person_a",
        "purchase_date": date.today().isoformat(),
        "tags": ["élelmiszer", "háztartás"],
    }


def upload(client, form, content=None, filename="blokk.jpg"):
    files = {"file": (filename, image_bytes("JPEG") if content is None else content)}
    return client.post("/uploads", data=form, files=files)


def only_new_item(client, headers):
    items = client.get("/inbox/items", params={"status": "new"}, headers=headers).json()["items"]
    assert len(items) == 1
    return items[0]


def test_page_lists_members_and_categories(client):
    response = client.get("/")

    assert response.status_code == 200
    assert 'value="person_b"' in response.text
    assert 'value="élelmiszer"' in response.text
    assert "{{" not in response.text


def test_manifest_is_served(client):
    response = client.get("/manifest.webmanifest")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    assert client.get(response.json()["icons"][0]["src"]).status_code == 200


def test_upload_keeps_file_unchanged(client, valid_form, worker_headers):
    content = image_bytes("JPEG")

    response = upload(client, valid_form, content)

    assert response.status_code == 201
    item = only_new_item(client, worker_headers)
    assert item["sha256"] == hashlib.sha256(content).hexdigest()
    assert item["size_bytes"] == len(content)
    assert item["tags"] == ["élelmiszer", "háztartás"]
    file_response = client.get(f"/inbox/items/{item['id']}/file", headers=worker_headers)
    assert file_response.content == content
    assert file_response.headers["content-type"] == "image/jpeg"


def test_defaults_come_from_uploader(client, valid_form, worker_headers):
    upload(client, valid_form)

    item = only_new_item(client, worker_headers)
    assert item["purchased_by"] == "person_a"
    assert item["payer"] == "shared"


def test_single_tag_is_accepted(client, valid_form):
    assert upload(client, valid_form | {"tags": ["élelmiszer"]}).status_code == 201


def test_server_sets_upload_time(client, valid_form, worker_headers):
    upload(client, valid_form | {"uploaded_at": "2000-01-01T00:00:00+00:00"})

    uploaded_at = datetime.fromisoformat(only_new_item(client, worker_headers)["uploaded_at"])
    assert datetime.now(UTC) - uploaded_at < timedelta(minutes=1)


@pytest.mark.parametrize(
    ("image_format", "expected"),
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
def test_type_comes_from_content_not_name(image_format, expected):
    assert inbox.detect_file_type(image_bytes(image_format)) == expected


def test_heic_is_detected_from_header():
    assert inbox.detect_file_type(b"\x00\x00\x00\x18ftypheic" + bytes(16)) == "image/heic"


def test_pdf_is_detected_from_content():
    assert inbox.detect_file_type(b"%PDF-1.7 kitalalt") == "application/pdf"


def test_pdf_can_be_uploaded(client, valid_form, worker_headers):
    response = upload(client, valid_form, b"%PDF-1.7 kitalalt", "szamla.pdf")

    assert response.status_code == 201
    item = only_new_item(client, worker_headers)
    assert item["content_type"] == "application/pdf"
    assert (item["group_id"], item["page_count"]) == (None, 1)


def test_wrong_type_is_rejected(client, valid_form, worker_headers):
    response = upload(client, valid_form, b"GIF89a nem blokk", "blokk.jpg")

    assert response.status_code == 415
    assert client.get("/inbox/items", params={"status": "new"}, headers=worker_headers).json() == {
        "items": []
    }


def test_too_large_file_is_rejected(client, valid_form, monkeypatch, worker_headers):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 8)

    response = upload(client, valid_form)

    assert response.status_code == 413
    assert client.get("/inbox/items", params={"status": "new"}, headers=worker_headers).json() == {
        "items": []
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"uploaded_by": "ismeretlen"},
        {"purchased_by": "ismeretlen"},
        {"payer": "ismeretlen"},
        {"purchased_by": "shared"},
        {"purchase_date": (date.today() + timedelta(days=2)).isoformat()},
        {"purchase_date": "nem dátum"},
        {"tags": ["nem kategória"]},
    ],
)
def test_invalid_field_is_rejected(client, valid_form, changes, worker_headers):
    response = upload(client, valid_form | changes)

    assert response.status_code == 422
    assert client.get("/inbox/items", params={"status": "new"}, headers=worker_headers).json() == {
        "items": []
    }


def test_date_is_optional(client, valid_form, worker_headers):
    response = upload(client, valid_form | {"purchase_date": ""})

    assert response.status_code == 201
    assert only_new_item(client, worker_headers)["purchase_date"] is None


def test_missing_date_field_is_accepted(client, valid_form, worker_headers):
    form = {key: value for key, value in valid_form.items() if key != "purchase_date"}

    assert upload(client, form).status_code == 201


def group_upload(client, form, contents):
    files = [("files", (f"kep{page}.jpg", content)) for page, content in enumerate(contents, 1)]
    return client.post("/uploads/group", data=form, files=files)


def test_group_keeps_page_order(client, valid_form, worker_headers):
    contents = [image_bytes("JPEG"), image_bytes("PNG")]

    response = group_upload(client, valid_form, contents)

    assert response.status_code == 201
    params = {"status": "new"}
    items = client.get("/inbox/items", params=params, headers=worker_headers).json()["items"]
    assert [item["page_no"] for item in sorted(items, key=lambda row: row["page_no"])] == [1, 2]
    assert {item["group_id"] for item in items} == {response.json()["group_id"]}
    assert {item["page_count"] for item in items} == {2}


def test_group_counts_as_one_receipt(client, valid_form):
    group_upload(client, valid_form, [image_bytes("JPEG"), image_bytes("PNG")])

    assert inbox.queue_counts()["new"] == 1


def test_bad_file_stops_the_whole_group(client, valid_form, worker_headers, inbox_dir):
    response = group_upload(client, valid_form, [image_bytes("JPEG"), b"GIF89a nem blokk"])

    assert response.status_code == 415
    assert client.get("/inbox/items", params={"status": "new"}, headers=worker_headers).json() == {
        "items": []
    }
    assert [path.name for path in inbox_dir.iterdir() if path.name != "inbox.sqlite3"] == []


def test_pdf_cannot_join_a_group(client, valid_form, worker_headers, inbox_dir):
    response = group_upload(client, valid_form, [image_bytes("JPEG"), b"%PDF-1.7 kitalalt"])

    assert response.status_code == 422
    assert "PDF" in response.json()["detail"]
    assert client.get("/inbox/items", params={"status": "new"}, headers=worker_headers).json() == {
        "items": []
    }
    assert [path.name for path in inbox_dir.iterdir() if path.name != "inbox.sqlite3"] == []


@pytest.mark.parametrize("pages", [1, 6])
def test_group_size_is_limited(client, valid_form, pages):
    response = group_upload(client, valid_form, [image_bytes("JPEG")] * pages)

    assert response.status_code == 422


def test_old_inbox_is_migrated_keeping_items(inbox_dir):
    with closing(sqlite3.connect(inbox_dir / "inbox.sqlite3")) as conn, conn:
        conn.execute(inbox.CREATE_TABLES[0])
        conn.execute(
            "insert into inbox_item (id, sha256, filename, content_type, size_bytes, uploaded_by,"
            " uploaded_at, purchased_by, purchase_date, payer, tags)"
            " values ('a', 'b', 'c', 'image/png', 1, 'person_a', 'd', 'person_a', '2026-11-01',"
            " 'shared', '[]')"
        )

    items = inbox.list_items("new")

    assert [(item["id"], item["page_no"], item["group_id"]) for item in items] == [("a", 1, None)]
    with closing(inbox.connect()) as conn:
        assert conn.execute("pragma user_version").fetchone()[0] == 1


def test_missing_tags_are_rejected(client, valid_form):
    form = {key: value for key, value in valid_form.items() if key != "tags"}

    assert upload(client, form).status_code == 422


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer rossz"}, {"Authorization": "Basic teszt-token"}]
)
def test_inbox_needs_token(client, headers):
    item_id = uuid4()
    responses = [
        client.get("/inbox/items", params={"status": "new"}, headers=headers),
        client.get(f"/inbox/items/{item_id}/file", headers=headers),
        client.post(f"/inbox/items/{item_id}/close", headers=headers),
    ]

    assert [response.status_code for response in responses] == [401, 401, 401]


def test_close_removes_file_and_can_be_repeated(client, valid_form, worker_headers, inbox_dir):
    upload(client, valid_form)
    item = only_new_item(client, worker_headers)
    path = f"/inbox/items/{item['id']}"

    assert (inbox_dir / item["id"]).exists()
    assert client.post(f"{path}/close", headers=worker_headers).status_code == 200
    assert client.post(f"{path}/close", headers=worker_headers).status_code == 200

    assert not (inbox_dir / item["id"]).exists()
    assert client.get(f"{path}/file", headers=worker_headers).status_code == 404
    closed = client.get("/inbox/items", params={"status": "closed"}, headers=worker_headers)
    assert [row["id"] for row in closed.json()["items"]] == [item["id"]]


def test_unknown_item_is_not_found(client, worker_headers):
    path = f"/inbox/items/{uuid4()}"

    assert client.get(f"{path}/file", headers=worker_headers).status_code == 404
    assert client.post(f"{path}/close", headers=worker_headers).status_code == 404


def test_open_items_survive_a_restart(client, valid_form, worker_headers):
    upload(client, valid_form)

    restarted = TestClient(main.app)

    assert only_new_item(restarted, worker_headers)["uploaded_by"] == "person_a"
