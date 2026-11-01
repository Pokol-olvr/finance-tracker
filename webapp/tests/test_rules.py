"""Kitalált szabályok; a webapp a bronzot nem éri el, minden a kimenő soron át megy."""

from uuid import uuid4

import pytest
from app import inbox, main
from fastapi.testclient import TestClient


@pytest.fixture
def client(inbox_dir):
    return TestClient(main.app)


@pytest.fixture
def headers():
    return {"Authorization": "Bearer teszt-token"}


def category_rule(**changes) -> dict:
    return {
        "rule_type": "category",
        "pattern": "MOSÓGÉL",
        "target": "háztartás",
        "created_by": "person_a",
    } | changes


def store_rule(**changes) -> dict:
    return {
        "rule_type": "store",
        "pattern": "12345678-2-41",
        "target": "Kitalált Bolt",
        "created_by": "person_a",
    } | changes


def events(client, headers) -> list[dict]:
    return client.get("/inbox/events", headers=headers).json()["events"]


def test_new_rule_is_listed_and_waits_for_the_worker(client, headers):
    response = client.post("/rules", json=category_rule())

    assert response.status_code == 201
    rule = client.get("/rules.json").json()["rules"][0]
    assert (rule["pattern"], rule["target"], rule["active"]) == ("MOSÓGÉL", "háztartás", True)
    event = events(client, headers)[0]
    assert event["event_type"] == "rule_event"
    assert event["data"]["rule_id"] == response.json()["rule_id"]
    assert event["data"]["target_value"] == "háztartás"
    assert event["data"]["active"] is True


def test_page_offers_the_categories(client):
    assert "háztartás" in client.get("/rules.json").json()["categories"]
    assert "person_a" in client.get("/rules").text


@pytest.mark.parametrize(
    "rule",
    [
        category_rule(target="ismeretlen"),
        category_rule(target="besorolatlan"),
        category_rule(pattern="x"),
        category_rule(pattern="   "),
        category_rule(created_by="idegen"),
        store_rule(pattern="nem adószám"),
        store_rule(target=""),
    ],
)
def test_invalid_rule_is_rejected(client, headers, rule):
    assert client.post("/rules", json=rule).status_code == 422
    assert events(client, headers) == []


def test_store_rule_needs_a_tax_number(client):
    assert client.post("/rules", json=store_rule()).status_code == 201


def test_switching_off_is_a_new_event(client, headers):
    rule_id = client.post("/rules", json=category_rule()).json()["rule_id"]

    response = client.post(
        f"/rules/{rule_id}/active", json={"active": False, "created_by": "person_b"}
    )

    assert response.status_code == 204
    assert client.get("/rules.json").json()["rules"][0]["active"] is False
    first, second = events(client, headers)
    assert (first["data"]["active"], second["data"]["active"]) == (True, False)
    assert second["data"]["rule_id"] == rule_id
    assert second["data"]["created_by"] == "person_b"


def test_same_state_makes_no_event(client, headers):
    rule_id = client.post("/rules", json=category_rule()).json()["rule_id"]

    client.post(f"/rules/{rule_id}/active", json={"active": True, "created_by": "person_a"})

    assert len(events(client, headers)) == 1


def test_unknown_rule_is_not_found(client):
    response = client.post(
        f"/rules/{uuid4()}/active", json={"active": False, "created_by": "person_a"}
    )

    assert response.status_code == 404


def test_closed_event_is_not_offered_again(client, headers):
    client.post("/rules", json=category_rule())
    event_id = events(client, headers)[0]["id"]

    for _ in range(2):
        response = client.post(f"/inbox/events/{event_id}/close", headers=headers)
        assert response.status_code == 204

    assert events(client, headers) == []


def test_event_api_needs_a_token(client):
    assert client.get("/inbox/events").status_code == 401
    assert client.post(f"/inbox/events/{uuid4()}/close").status_code == 401


def test_unknown_event_is_not_found(client, headers):
    assert client.post(f"/inbox/events/{uuid4()}/close", headers=headers).status_code == 404


def test_rule_and_its_event_stay_together(client, headers, monkeypatch):
    def broken(*_):
        raise RuntimeError("hiba")

    monkeypatch.setattr(inbox, "add_event", broken)

    with pytest.raises(RuntimeError):
        client.post("/rules", json=category_rule())

    assert client.get("/rules.json").json()["rules"] == []
