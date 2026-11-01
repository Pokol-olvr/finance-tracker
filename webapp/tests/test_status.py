from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app import main, status
from app.schemas import CloseResult
from fastapi.testclient import TestClient

NOW = datetime(2026, 12, 1, 12, 0, tzinfo=UTC)
HEADERS = {"Authorization": "Bearer teszt-token"}

HOST_REPORT = {
    "services": [
        {"name": name, "state": "running", "health": "healthy"}
        for name in ("postgres", "garage", "reports", "webapp", "ollama", "worker")
    ],
    "jobs": [
        {
            "name": name,
            "active": "inactive",
            "result": "success",
            "last_run": "2026-12-01T03:00:00+01:00",
            "next_run": "2026-12-02T03:00:00+01:00",
        }
        for name in ("dbt", "backup")
    ],
    "row_counts": {"bronze.manual_entry": 108, "silver.transactions": 108, "gold.category_month": 48},
    "garage_objects": 2,
    "garage_size": "3.8 MB",
    "disk_free_bytes": 600_000_000_000,
    "disk_total_bytes": 700_000_000_000,
    "memory_available_bytes": 20_000_000_000,
    "memory_total_bytes": 32_000_000_000,
    "load": 0.5,
}
WORKER_REPORT = {
    "step": "idle",
    "step_started_at": "2026-12-01T11:00:00+00:00",
    "ollama_reachable": True,
    "model_name": "glm-ocr",
    "model_version": "89d735dd9c07791953756edd",
    "model_downloaded": True,
    "model_loaded": False,
    "model_memory_bytes": 0,
}


def report(payload: dict, age_seconds: int = 5) -> dict:
    received_at = NOW - timedelta(seconds=age_seconds)
    return {"payload": deepcopy(payload), "received_at": received_at.isoformat()}


def build(host=None, worker=None, queue=None, recent=None, host_age=5, worker_age=5) -> dict:
    reports = {
        "host": report(HOST_REPORT if host is None else host, host_age),
        "worker": report(WORKER_REPORT if worker is None else worker, worker_age),
    }
    return status.build(reports, queue or {}, recent or [], "http://127.0.0.1:8501", NOW)


def card(result: dict, key: str) -> dict:
    return next(item for item in result["cards"] if item["key"] == key)


def without_service(name: str) -> dict:
    host = deepcopy(HOST_REPORT)
    host["services"] = [row for row in host["services"] if row["name"] != name]
    return host


def with_service_health(name: str, health: str) -> dict:
    host = deepcopy(HOST_REPORT)
    next(row for row in host["services"] if row["name"] == name)["health"] = health
    return host


def with_job(name: str, **changes) -> dict:
    host = deepcopy(HOST_REPORT)
    next(row for row in host["jobs"] if row["name"] == name).update(changes)
    return host


def test_all_nine_cards_are_present():
    result = build()

    assert [item["title"] for item in result["cards"]] == [
        "Feltöltés",
        "Worker",
        "Ollama",
        "Garage",
        "Postgres",
        "Riportok",
        "dbt",
        "Mentés",
        "Gép",
    ]
    assert {item["state"] for item in result["cards"]} == {"ok"}


def test_healthy_stack_is_all_right():
    assert build()["overall"] == {"state": "ok", "label": "Minden rendben"}


@pytest.mark.parametrize("name", ["ollama", "worker", "garage", "postgres", "reports", "webapp"])
def test_stopped_service_is_an_error(name):
    result = build(host=without_service(name))

    assert result["overall"]["state"] == "error"
    failed = [item for item in result["cards"] if item["state"] == "error"]
    assert [item["summary"] for item in failed] == ["Nem fut"]


def test_stopped_worker_is_error_even_with_stale_worker_report():
    result = build(host=without_service("worker"), worker_age=120)

    assert result["overall"] == {"state": "error", "label": "Hiba: Worker"}


def test_unhealthy_service_is_an_error():
    result = build(host=with_service_health("ollama", "unhealthy"))

    assert card(result, "ollama")["state"] == "error"
    assert result["overall"]["label"] == "Hiba: Ollama"


def test_starting_service_is_not_an_error():
    result = build(host=with_service_health("garage", "starting"))

    assert card(result, "garage")["summary"] == "Indul"
    assert result["overall"]["state"] == "ok"


def test_service_without_healthcheck_is_running():
    assert card(build(host=with_service_health("worker", "")), "worker")["state"] == "ok"


def test_old_host_report_is_never_green():
    result = build(host_age=61)

    assert result["overall"] == {"state": "stale", "label": "Nincs friss adat"}
    assert "ok" not in {card(result, key)["state"] for key in ("garage", "postgres", "dbt")}


def test_old_worker_report_is_never_green():
    result = build(worker_age=61)

    assert result["overall"]["state"] == "stale"
    assert card(result, "worker")["state"] == "stale"
    assert card(result, "ollama")["state"] == "stale"
    assert result["processing"] is None


def test_missing_reports_are_stale():
    result = status.build({}, {}, [], "http://127.0.0.1:8501", NOW)

    assert result["overall"]["state"] == "stale"
    assert result["report_age_seconds"] is None
    assert {item["state"] for item in result["cards"]} == {"stale"}


def test_processing_shows_step_elapsed_time_and_queue():
    worker = WORKER_REPORT | {
        "step": "read_text",
        "step_started_at": "2026-12-01T11:58:48+00:00",
        "model_loaded": True,
        "model_memory_bytes": 5_000_000_000,
    }

    result = build(worker=worker, queue={"new": 3})

    assert result["overall"] == {"state": "busy", "label": "Feldolgozás fut"}
    assert result["processing"] == {
        "step": "read_text",
        "label": "Szöveges olvasat",
        "seconds": 72,
        "waiting": 2,
    }
    assert card(result, "worker")["summary"] == "Szöveges olvasat"
    ollama = card(result, "ollama")
    assert ollama["state"] == "busy"
    assert {"label": "Memória", "value": "5,0 GB"} in ollama["facts"]


def test_open_item_without_processing_is_waiting():
    result = build(queue={"new": 1})

    assert result["overall"] == {"state": "waiting", "label": "Várakozik"}


def test_missing_model_is_an_error():
    result = build(worker=WORKER_REPORT | {"model_downloaded": False})

    assert card(result, "ollama")["summary"] == "A modell nincs letöltve"
    assert result["overall"]["state"] == "error"


def test_unreachable_ollama_is_an_error():
    result = build(worker=WORKER_REPORT | {"ollama_reachable": False})

    assert card(result, "ollama")["summary"] == "A worker nem éri el"


def test_failed_backup_is_an_error_with_next_run():
    result = build(host=with_job("backup", result="exit-code"))

    backup = card(result, "backup")
    assert backup["state"] == "error"
    assert {"label": "Következő", "time": "2026-12-02T03:00:00+01:00"} in backup["facts"]
    assert result["overall"]["label"] == "Hiba: Mentés"


def test_running_job_is_busy():
    assert card(build(host=with_job("dbt", active="activating")), "dbt")["summary"] == "Most fut"


def test_job_that_never_ran_is_not_an_error():
    dbt = card(build(host=with_job("dbt", last_run=None)), "dbt")

    assert (dbt["state"], dbt["summary"]) == ("stale", "Még nem futott")


def test_postgres_card_sums_layers():
    facts = card(build(), "postgres")["facts"]

    assert facts == [
        {"label": "Bronz", "value": "108 sor"},
        {"label": "Silver", "value": "108 sor"},
        {"label": "Gold", "value": "48 sor"},
    ]


def test_reports_card_links_to_the_reports():
    assert card(build(), "reports")["link"]["url"] == "http://127.0.0.1:8501"


@pytest.fixture
def client(inbox_dir):
    return TestClient(main.app)


def test_status_page_is_served(client):
    response = client.get("/status")

    assert response.status_code == 200
    assert "Stack állapota" in response.text
    assert client.get("/base.css").status_code == 200


def test_reports_need_token(client):
    responses = [
        client.post("/inbox/status/host", json=HOST_REPORT),
        client.post("/inbox/status/worker", json=WORKER_REPORT, headers={"Authorization": "Bearer x"}),
    ]

    assert [response.status_code for response in responses] == [401, 401]


def test_reports_reach_the_status_data(client):
    assert client.post("/inbox/status/host", json=HOST_REPORT, headers=HEADERS).status_code == 204
    assert client.post("/inbox/status/worker", json=WORKER_REPORT, headers=HEADERS).status_code == 204

    data = client.get("/status.json").json()

    assert data["overall"]["state"] == "ok"
    assert data["report_age_seconds"] == 0
    assert card(data, "garage")["facts"][0] == {"label": "Objektumok", "value": "2"}


def test_new_report_replaces_the_old_one(client):
    client.post("/inbox/status/worker", json=WORKER_REPORT, headers=HEADERS)
    client.post("/inbox/status/worker", json=WORKER_REPORT | {"step": "close"}, headers=HEADERS)

    assert list(main.inbox.reports()) == ["worker"]
    assert main.inbox.reports()["worker"]["payload"]["step"] == "close"


def test_unknown_report_field_is_rejected(client):
    response = client.post(
        "/inbox/status/worker", json=WORKER_REPORT | {"filename": "blokk.jpg"}, headers=HEADERS
    )

    assert response.status_code == 422


def test_unknown_step_is_rejected(client):
    response = client.post(
        "/inbox/status/worker", json=WORKER_REPORT | {"step": "ismeretlen"}, headers=HEADERS
    )

    assert response.status_code == 422


def upload_item(client) -> str:
    response = client.post(
        "/uploads",
        data={
            "uploaded_by": "person_a",
            "purchase_date": "2026-11-01",
            "tags": ["élelmiszer"],
        },
        files={"file": ("titkos-bolt.jpg", b"\xff\xd8\xff kitalalt")},
    )
    return response.json()["id"]


def test_result_shows_in_recent_list_without_file_name(client):
    item_id = upload_item(client)
    outcome = {"result": "ok", "seconds": 145.5, "items": 4}

    client.post(f"/inbox/items/{item_id}/close", json=outcome, headers=HEADERS)
    response = client.get("/status.json")

    recent = response.json()["recent"]
    assert len(recent) == 1
    assert (recent[0]["result"], recent[0]["seconds"], recent[0]["items"]) == ("rendben", 145.5, 4)
    assert "titkos-bolt" not in response.text


def test_receipts_needing_review_are_counted(client):
    item_id = upload_item(client)

    client.post(f"/inbox/items/{item_id}/close", json={"result": "review"}, headers=HEADERS)
    package = {
        "parse_id": str(uuid4()),
        "parser_version": "1",
        "result": "review",
        "parsed": {},
        "checks": {},
        "ocr_text": "",
        "uploaded_at": "2026-12-14T10:00:00+00:00",
        "content_types": ["image/jpeg"],
        "sha256s": ["a" * 64],
    }
    client.put(f"/inbox/reviews/{uuid4()}", json=package, headers=HEADERS)
    data = client.get("/status.json").json()

    assert {"label": "Ellenőrzésre vár", "value": "1"} in card(data, "upload")["facts"]
    assert data["recent"][0]["result"] == "ellenőrzés kell"


def test_close_without_result_still_works(client):
    item_id = upload_item(client)

    assert client.post(f"/inbox/items/{item_id}/close", headers=HEADERS).status_code == 200
    assert client.get("/status.json").json()["recent"] == []


def test_repeated_close_keeps_first_result(client):
    item_id = upload_item(client)
    path = f"/inbox/items/{item_id}/close"

    client.post(path, json={"result": "ok", "seconds": 10}, headers=HEADERS)
    client.post(path, json={"result": "duplicate"}, headers=HEADERS)

    assert [row["result"] for row in main.inbox.recent_results(10)] == ["ok"]


def test_unknown_result_is_rejected(client):
    response = client.post(
        f"/inbox/items/{uuid4()}/close", json={"result": "ismeretlen"}, headers=HEADERS
    )

    assert response.status_code == 422


def test_close_result_model_allows_missing_numbers():
    assert CloseResult(result="duplicate").seconds is None
