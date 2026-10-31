import csv
from decimal import Decimal
from pathlib import Path

import pytest
from app import main
from app.schemas import CATEGORIES
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    written = []

    def insert_entry(_conn, entry):
        created = entry.id not in {seen.id for seen in written}
        if created:
            written.append(entry)
        return created

    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main.store, "insert_entry", insert_entry)
    test_client = TestClient(main.app)
    test_client.written = written
    return test_client


def test_valid_entry_is_written(client, valid_entry):
    response = client.post("/entries", json=valid_entry)

    assert response.status_code == 201
    assert client.written[0].amount == Decimal("18450.10")
    assert client.written[0].purchased_by == "person_a"
    assert client.written[0].currency == "HUF"


def test_same_id_is_written_once(client, valid_entry):
    assert client.post("/entries", json=valid_entry).status_code == 201
    response = client.post("/entries", json=valid_entry)

    assert response.status_code == 200
    assert response.json()["status"] == "already_exists"
    assert len(client.written) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"amount": "0"},
        {"amount": "-5"},
        {"amount": "1.234"},
        {"amount": "12345678901.00"},
        {"kind": "refund"},
        {"currency": "huf"},
        {"payer": "ismeretlen"},
        {"entered_by": "ismeretlen"},
        {"purchased_by": "shared"},
        {"tags": []},
        {"tags": ["élelmiszer", "háztartás"]},
        {"tags": ["ismeretlen"]},
        {"kind": "income", "tags": ["élelmiszer"]},
        {"occurred_on": "nem dátum"},
        {"id": "nem uuid"},
        {"extra_mezo": "x"},
    ],
)
def test_invalid_entry_is_rejected(client, valid_entry, change):
    response = client.post("/entries", json=valid_entry | change)

    assert response.status_code == 422
    assert client.written == []


def test_mock_author_needs_real_purchaser(client, valid_entry):
    entry = valid_entry | {"entered_by": "mock"}
    assert client.post("/entries", json=entry).status_code == 422

    entry |= {"purchased_by": "person_b"}
    assert client.post("/entries", json=entry).status_code == 201


def test_no_update_or_delete_route(client, valid_entry):
    url = f"/entries/{valid_entry['id']}"
    for method in (client.put, client.patch, client.delete):
        assert method(url).status_code in (404, 405)


def test_categories_match_dbt_seed():
    seed = Path(__file__).parents[2] / "dbt" / "seeds" / "categories.csv"
    with seed.open(encoding="utf-8") as file:
        assert {row["category"] for row in csv.DictReader(file)} == CATEGORIES
