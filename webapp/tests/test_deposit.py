"""A betétdíj oldal: az egyenleget a worker tölti vissza, a kézi művelet a kimenő soron megy."""

import pytest
from app import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(inbox_dir):
    return TestClient(main.app)


@pytest.fixture
def headers():
    return {"Authorization": "Bearer teszt-token"}


def report(balance: float = 1250.0) -> dict:
    return {
        "balance": balance,
        "movements": [
            {
                "movement": "deposit",
                "moved_at": "2026-10-14T00:00:00+00:00",
                "amount": 50.0,
                "balance": balance,
            }
        ],
    }


def test_without_a_report_the_page_says_so(client):
    data = client.get("/deposit.json").json()

    assert data["balance"] is None
    assert data["movements"] == []
    assert data["waiting"] == 0


def test_worker_report_is_shown(client, headers):
    response = client.post("/inbox/status/deposit", json=report(), headers=headers)

    assert response.status_code == 204
    data = client.get("/deposit.json").json()
    assert data["balance"] == 1250.0
    assert data["movements"][0]["movement"] == "deposit"
    assert data["updated_at"]


def test_report_needs_a_token(client):
    assert client.post("/inbox/status/deposit", json=report()).status_code == 401


def test_adjustment_goes_to_the_worker(client, headers):
    response = client.post(
        "/deposit/changes", json={"kind": "adjust", "amount": -300, "created_by": "person_a"}
    )

    assert response.status_code == 201
    assert client.get("/deposit.json").json()["waiting"] == 1
    event = client.get("/inbox/events", headers=headers).json()["events"][0]
    assert event["event_type"] == "deposit_correction"
    assert event["data"]["kind"] == "adjust"
    assert event["data"]["amount"] == -300


def test_reset_has_no_amount(client, headers):
    response = client.post("/deposit/changes", json={"kind": "reset", "created_by": "person_a"})

    assert response.status_code == 201
    event = client.get("/inbox/events", headers=headers).json()["events"][0]
    assert (event["data"]["kind"], event["data"]["amount"]) == ("reset", None)


def test_closed_change_is_no_longer_waiting(client, headers):
    client.post("/deposit/changes", json={"kind": "reset", "created_by": "person_a"})
    event_id = client.get("/inbox/events", headers=headers).json()["events"][0]["id"]

    client.post(f"/inbox/events/{event_id}/close", headers=headers)

    assert client.get("/deposit.json").json()["waiting"] == 0


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "adjust", "created_by": "person_a"},
        {"kind": "adjust", "amount": 0, "created_by": "person_a"},
        {"kind": "reset", "amount": 100, "created_by": "person_a"},
        {"kind": "adjust", "amount": 100, "created_by": "idegen"},
        {"kind": "ismeretlen", "amount": 100, "created_by": "person_a"},
        {"kind": "adjust", "amount": 5000000, "created_by": "person_a"},
    ],
)
def test_invalid_change_is_rejected(client, change):
    assert client.post("/deposit/changes", json=change).status_code == 422
