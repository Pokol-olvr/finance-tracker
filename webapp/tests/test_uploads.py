import hashlib
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
    assert inbox.detect_image_type(image_bytes(image_format)) == expected


def test_heic_is_detected_from_header():
    assert inbox.detect_image_type(b"\x00\x00\x00\x18ftypheic" + bytes(16)) == "image/heic"


def test_wrong_type_is_rejected(client, valid_form, worker_headers):
    response = upload(client, valid_form, b"%PDF-1.7 nem kep", "blokk.jpg")

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
        {"purchase_date": ""},
        {"tags": ["nem kategória"]},
    ],
)
def test_invalid_field_is_rejected(client, valid_form, changes, worker_headers):
    response = upload(client, valid_form | changes)

    assert response.status_code == 422
    assert client.get("/inbox/items", params={"status": "new"}, headers=worker_headers).json() == {
        "items": []
    }


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
