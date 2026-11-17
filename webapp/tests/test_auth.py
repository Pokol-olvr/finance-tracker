"""Az Authelia mögötti belépés: a fejlécben érkező felhasználó, kitalált adatokkal."""

import pytest
from app import main
from app.config import get_settings
from fastapi.testclient import TestClient

HEADER = "Remote-User"
TOKEN = {"Authorization": "Bearer teszt-token"}


@pytest.fixture
def client(inbox_dir, monkeypatch):
    monkeypatch.setenv("AUTH_HEADER", HEADER)
    get_settings.cache_clear()
    yield TestClient(main.app)
    get_settings.cache_clear()


def rule(created_by: str) -> dict:
    return {"rule_type": "category", "pattern": "MOSÓGÉL", "target": "háztartás", "created_by": created_by}


def test_pages_need_a_signed_in_member(client):
    assert client.get("/rules").status_code == 401
    assert client.get("/rules", headers={HEADER: "idegen"}).status_code == 401
    assert client.get("/rules", headers={HEADER: "person_a"}).status_code == 200


def test_only_the_signed_in_member_is_offered(client):
    page = client.get("/", headers={HEADER: "person_b"}).text

    assert 'value="person_b"' in page
    assert 'value="person_a"' not in page


def test_saving_in_someone_elses_name_is_refused(client):
    assert client.post("/rules", json=rule("person_a"), headers={HEADER: "person_b"}).status_code == 403
    assert client.post("/rules", json=rule("person_b"), headers={HEADER: "person_b"}).status_code == 201


def test_worker_api_and_health_need_no_sign_in(client):
    assert client.get("/inbox/items", headers=TOKEN).status_code == 200
    assert client.get("/inbox/items").status_code == 401


def test_without_auth_header_setting_everyone_can_be_chosen(inbox_dir):
    get_settings.cache_clear()
    page = TestClient(main.app).get("/").text

    assert 'value="person_a"' in page and 'value="person_b"' in page


def test_without_database_health_checks_the_inbox_and_entries_are_unavailable(inbox_dir, monkeypatch, valid_entry):
    monkeypatch.delenv("DATABASE_URL")
    get_settings.cache_clear()
    client = TestClient(main.app)

    assert client.get("/health").status_code == 200
    assert client.post("/entries", json=valid_entry).status_code == 503
    get_settings.cache_clear()
