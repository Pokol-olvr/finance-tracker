import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from app import inbox, main
from fastapi.testclient import TestClient
from PIL import Image


def image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


PARSED = {
    "document_type": "receipt",
    "store_name": "Kitalált Bolt Kft.",
    "tax_number": "12345678-2-41",
    "receipt_number": "0042/00017",
    "purchased_on": "2026-12-14",
    "total": 1000,
    "items": [{"name": "KENYÉR", "value": 900, "kind": "item", "quantity": 1, "unit": "DB", "unit_price": 900}],
    "payments": [{"method": "card", "amount": 1000}],
}
CHECKS = {
    "sum": {"ok": False, "expected": 1000, "actual": 900},
    "date": {"ok": None},
}


def package(**changes) -> dict:
    return {
        "parse_id": str(uuid4()),
        "parser_version": "3",
        "result": "review",
        "document_type": "receipt",
        "parsed": PARSED,
        "checks": CHECKS,
        "ocr_text": "NYUGTA\nKENYÉR 900",
        "uploaded_at": "2026-12-14T10:00:00+00:00",
        "content_types": ["image/jpeg"],
        "sha256s": ["a" * 64],
    } | changes


@pytest.fixture
def client(inbox_dir):
    return TestClient(main.app)


@pytest.fixture
def headers():
    return {"Authorization": "Bearer teszt-token"}


def push(client, headers, group_id=None, **changes) -> tuple[str, dict]:
    group_id = group_id or str(uuid4())
    body = package(**changes)
    client.put(f"/inbox/reviews/{group_id}/pages/1", content=image_bytes(), headers=headers)
    response = client.put(f"/inbox/reviews/{group_id}", json=body, headers=headers)
    assert response.status_code == 204
    return group_id, body


def decision(body: dict, **changes) -> dict:
    return {"parse_id": body["parse_id"], "action": "approved", "decided_by": "person_a"} | changes


CORRECTED = {
    "store_name": "Kitalált Bolt Kft.",
    "purchased_on": "2026-12-14",
    "total": 1000,
    "items": [{"name": "KENYÉR", "value": 1000, "kind": "item"}],
}


def test_review_needs_a_decision_and_opens_with_data(client, headers):
    group_id, _ = push(client, headers)

    listing = client.get("/reviews.json").json()
    assert [row["group_id"] for row in listing["open"]] == [group_id]
    assert listing["closed"] == []
    assert listing["open"][0]["failed"] == ["A tételek összege 900 Ft, a végösszeg 1 000 Ft."]
    assert listing["open"][0]["label"] == "ellenőrzés kell"
    detail = client.get(f"/reviews/{group_id}.json").json()
    assert detail["parsed"]["store_name"] == "Kitalált Bolt Kft."
    assert detail["pages"] == [{"url": f"/reviews/{group_id}/pages/1", "is_pdf": False}]
    assert detail["ocr_text"].startswith("NYUGTA")


@pytest.mark.parametrize(
    ("result", "document_type", "state"),
    [
        ("ok", "receipt", "closed"),
        ("ok", "invoice", "closed"),
        ("unparsed", "non_expense", "closed"),
        ("review", "invoice", "open"),
        ("unparsed", "receipt", "open"),
        ("unreadable", None, "open"),
    ],
)
def test_state_follows_the_result(client, headers, result, document_type, state):
    group_id, _ = push(client, headers, result=result, document_type=document_type)

    assert client.get(f"/reviews/{group_id}.json").json()["state"] == state


def test_file_is_served_for_the_page(client, headers):
    group_id, _ = push(client, headers)

    response = client.get(f"/reviews/{group_id}/pages/1")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].startswith("inline")
    assert client.get(f"/reviews/{group_id}/pages/2").status_code == 404


def test_pdf_page_is_marked(client, headers):
    group_id, _ = push(client, headers, content_types=["application/pdf"])

    assert client.get(f"/reviews/{group_id}.json").json()["pages"][0]["is_pdf"] is True


def test_worker_api_needs_token(client):
    group_id = uuid4()

    assert client.get("/inbox/reviews").status_code == 401
    assert client.get("/inbox/decisions").status_code == 401
    assert client.put(f"/inbox/reviews/{group_id}", json=package()).status_code == 401
    assert client.put(f"/inbox/reviews/{group_id}/pages/1", content=b"x").status_code == 401
    assert client.post(f"/inbox/decisions/{group_id}/close").status_code == 401


def test_only_known_file_types_are_stored(client, headers):
    response = client.put(f"/inbox/reviews/{uuid4()}/pages/1", content=b"GIF89a", headers=headers)

    assert response.status_code == 415


def test_page_number_is_limited(client, headers):
    response = client.put(f"/inbox/reviews/{uuid4()}/pages/0", content=image_bytes(), headers=headers)

    assert response.status_code == 422


def test_approval_lowers_the_count_and_waits_for_the_worker(client, headers):
    group_id, body = push(client, headers)
    assert inbox.queue_counts()["review"] == 1

    response = client.post(f"/reviews/{group_id}/decision", json=decision(body))

    assert response.status_code == 201
    assert response.json()["next"] is None
    assert inbox.queue_counts()["review"] == 0
    decisions = client.get("/inbox/decisions", headers=headers).json()["decisions"]
    assert [(row["group_id"], row["action"]) for row in decisions] == [(group_id, "approved")]
    assert decisions[0]["parse_id"] == body["parse_id"]


def test_decision_offers_the_next_open_document(client, headers):
    first, body = push(client, headers, uploaded_at="2026-12-14T10:00:00+00:00")
    second, _ = push(client, headers, uploaded_at="2026-12-15T10:00:00+00:00")

    response = client.post(f"/reviews/{first}/decision", json=decision(body))

    assert response.json()["next"] == second


def test_closed_decision_is_not_offered_again(client, headers):
    group_id, body = push(client, headers)
    client.post(f"/reviews/{group_id}/decision", json=decision(body))
    decision_id = client.get("/inbox/decisions", headers=headers).json()["decisions"][0]["id"]

    assert client.post(f"/inbox/decisions/{decision_id}/close", headers=headers).status_code == 204
    assert client.post(f"/inbox/decisions/{decision_id}/close", headers=headers).status_code == 204
    assert client.get("/inbox/decisions", headers=headers).json()["decisions"] == []


def test_second_decision_is_refused(client, headers):
    group_id, body = push(client, headers)
    client.post(f"/reviews/{group_id}/decision", json=decision(body))

    response = client.post(f"/reviews/{group_id}/decision", json=decision(body, action="rejected"))

    assert response.status_code == 409
    assert len(client.get("/inbox/decisions", headers=headers).json()["decisions"]) == 1


def test_decision_on_an_old_reading_is_refused(client, headers):
    group_id, body = push(client, headers)
    push(client, headers, group_id=group_id)

    response = client.post(f"/reviews/{group_id}/decision", json=decision(body))

    assert response.status_code == 409


def test_unknown_document_is_not_found(client):
    body = package()

    assert client.post(f"/reviews/{uuid4()}/decision", json=decision(body)).status_code == 404
    assert client.get(f"/reviews/{uuid4()}.json").status_code == 404


def test_correction_is_stored_and_shown(client, headers):
    group_id, body = push(client, headers)

    response = client.post(
        f"/reviews/{group_id}/decision",
        json=decision(body, action="corrected", corrected=CORRECTED),
    )

    assert response.status_code == 201
    detail = client.get(f"/reviews/{group_id}.json").json()
    assert detail["parsed"]["items"][0]["value"] == 1000
    assert detail["label"] == "javítva"
    assert detail["decision"]["decided_by"] == "person_a"
    stored = client.get("/inbox/decisions", headers=headers).json()["decisions"][0]
    assert stored["corrected"]["total"] == 1000


@pytest.mark.parametrize("total", [1003, 997])
def test_correction_must_add_up(client, headers, total):
    group_id, body = push(client, headers)
    corrected = CORRECTED | {"total": total}

    response = client.post(
        f"/reviews/{group_id}/decision",
        json=decision(body, action="corrected", corrected=corrected),
    )

    assert response.status_code == 422
    assert inbox.queue_counts()["review"] == 1


def test_small_rounding_is_accepted_in_a_correction(client, headers):
    group_id, body = push(client, headers)
    corrected = CORRECTED | {"total": 1002}

    response = client.post(
        f"/reviews/{group_id}/decision",
        json=decision(body, action="corrected", corrected=corrected),
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "changes",
    [
        {"action": "corrected"},
        {"action": "approved", "corrected": CORRECTED},
        {"decided_by": "idegen"},
        {"action": "ismeretlen"},
    ],
)
def test_invalid_decision_is_rejected(client, headers, changes):
    group_id, body = push(client, headers)

    response = client.post(f"/reviews/{group_id}/decision", json=decision(body, **changes))

    assert response.status_code == 422


def test_rejection_is_recorded(client, headers):
    group_id, body = push(client, headers)

    client.post(f"/reviews/{group_id}/decision", json=decision(body, action="rejected"))

    assert client.get(f"/reviews/{group_id}.json").json()["label"] == "elvetve"


def test_ok_document_can_still_be_corrected(client, headers):
    group_id, body = push(client, headers, result="ok")

    response = client.post(
        f"/reviews/{group_id}/decision",
        json=decision(body, action="corrected", corrected=CORRECTED),
    )

    assert response.status_code == 201


def test_new_reading_closes_an_open_review(client, headers):
    group_id, _ = push(client, headers)

    push(client, headers, group_id=group_id, result="ok", checks={})

    assert inbox.queue_counts()["review"] == 0
    assert client.get(f"/reviews/{group_id}.json").json()["label"] == "rendben"


def test_new_reading_can_reopen_a_closed_document(client, headers):
    group_id, _ = push(client, headers, result="ok")

    push(client, headers, group_id=group_id, result="review")

    assert client.get(f"/reviews/{group_id}.json").json()["state"] == "open"


def test_decided_document_keeps_its_decision(client, headers):
    group_id, body = push(client, headers)
    client.post(f"/reviews/{group_id}/decision", json=decision(body))

    push(client, headers, group_id=group_id, result="unparsed")

    detail = client.get(f"/reviews/{group_id}.json").json()
    assert detail["parse_id"] == body["parse_id"]
    assert detail["decision"]["action"] == "approved"
    assert inbox.queue_counts()["review"] == 0


def test_known_reviews_tell_the_worker_what_exists(client, headers):
    group_id, body = push(client, headers)

    assert client.get("/inbox/reviews", headers=headers).json()["reviews"] == [
        {"group_id": group_id, "parse_id": body["parse_id"], "decided": False}
    ]

    client.post(f"/reviews/{group_id}/decision", json=decision(body))

    assert client.get("/inbox/reviews", headers=headers).json()["reviews"][0]["decided"] is True


def test_recent_results_follow_the_new_reading(client, headers, inbox_dir):
    response = client.post(
        "/uploads",
        data={"uploaded_by": "person_a", "tags": ["élelmiszer"]},
        files={"file": ("blokk.jpg", image_bytes())},
    )
    item_id = response.json()["id"]
    sha256 = response.json()["sha256"]
    client.post(
        f"/inbox/items/{item_id}/close",
        json={"result": "unparsed", "seconds": 60, "items": 0},
        headers=headers,
    )

    push(client, headers, result="ok", sha256s=[sha256], checks={})

    assert inbox.recent_results(10)[0]["result"] == "ok"
    assert inbox.recent_results(10)[0]["items"] == 1


def closed_since(group_id: str, days: int) -> None:
    moment = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    with inbox.connect() as conn:
        conn.execute("update review set closed_at = ? where group_id = ?", (moment, group_id))


def test_closed_package_disappears_after_the_keep_days(client, headers):
    old, _ = push(client, headers, result="ok")
    recent, _ = push(client, headers, result="ok")
    closed_since(old, inbox.KEEP_DAYS + 1)
    closed_since(recent, inbox.KEEP_DAYS - 1)

    client.get("/inbox/reviews", headers=headers)

    assert client.get(f"/reviews/{old}.json").status_code == 404
    assert client.get(f"/reviews/{old}/pages/1").status_code == 404
    assert not inbox.review_folder(old).exists()
    assert client.get(f"/reviews/{recent}.json").status_code == 200


def test_open_package_stays_however_old(client, headers):
    group_id, _ = push(client, headers)

    inbox.purge_reviews(datetime.now(UTC) + timedelta(days=400))

    assert client.get(f"/reviews/{group_id}.json").status_code == 200


def test_decision_not_yet_in_bronze_stays(client, headers):
    group_id, body = push(client, headers)
    client.post(f"/reviews/{group_id}/decision", json=decision(body))
    closed_since(group_id, inbox.KEEP_DAYS + 1)

    client.get("/inbox/reviews", headers=headers)

    assert client.get(f"/reviews/{group_id}.json").status_code == 200


def test_error_payload_is_explained(client, headers):
    group_id, _ = push(
        client, headers, result="unreadable", parsed={"error": "A kép nem olvasható"}, checks={},
        document_type=None,
    )

    assert client.get("/reviews.json").json()["open"][0]["failed"] == ["A kép nem olvasható"]
    assert client.get(f"/reviews/{group_id}.json").json()["parsed"]["error"]


@pytest.mark.parametrize(
    ("key", "check", "expected"),
    [
        ("line_total", {"ok": False, "wrong_lines": 2}, "2 sorban"),
        ("payment", {"ok": False, "paid": 950}, "950 Ft"),
        ("date", {"ok": False, "entered": "2026-12-01", "read": "2026-12-02"}, "2026-12-02"),
        ("duplicate", {"ok": False}, "már szerepel"),
        ("vat_summary", {"ok": False, "gross": 1100}, "1 100 Ft"),
        ("currency", {"ok": False, "currency": "EUR"}, "EUR"),
    ],
)
def test_failed_checks_are_explained(client, headers, key, check, expected):
    push(client, headers, checks={key: check})

    assert expected in client.get("/reviews.json").json()["open"][0]["failed"][0]


def test_pages_are_served(client, headers):
    group_id, _ = push(client, headers)

    listing = client.get("/review")
    detail = client.get(f"/review/{group_id}")

    assert "Ellenőrzés" in listing.text
    assert "person_a" in detail.text
    assert "{{members}}" not in detail.text
    assert client.get("/review/nem-azonosito").status_code == 422


def reopen(client, group_id, who="person_a"):
    return client.post(f"/reviews/{group_id}/reopen", json={"decided_by": who})


def test_rejected_document_can_be_reopened(client, headers):
    group_id, body = push(client, headers)
    client.post(f"/reviews/{group_id}/decision", json=decision(body, action="rejected"))
    assert inbox.queue_counts()["review"] == 0

    response = reopen(client, group_id)

    assert response.status_code == 201
    assert inbox.queue_counts()["review"] == 1
    detail = client.get(f"/reviews/{group_id}.json").json()
    assert detail["state"] == "open"
    assert detail["decision"] is None


def test_both_decisions_reach_the_worker_in_order(client, headers):
    group_id, body = push(client, headers)
    client.post(f"/reviews/{group_id}/decision", json=decision(body, action="rejected"))

    reopen(client, group_id)

    decisions = client.get("/inbox/decisions", headers=headers).json()["decisions"]
    assert [row["action"] for row in decisions] == ["rejected", "reopened"]


def test_reopened_document_can_be_decided_again(client, headers):
    group_id, body = push(client, headers)
    client.post(f"/reviews/{group_id}/decision", json=decision(body, action="rejected"))
    reopen(client, group_id)

    response = client.post(f"/reviews/{group_id}/decision", json=decision(body))

    assert response.status_code == 201
    assert client.get(f"/reviews/{group_id}.json").json()["label"] == "jóváhagyva"


def test_any_decision_can_be_reopened(client, headers):
    group_id, body = push(client, headers)
    client.post(
        f"/reviews/{group_id}/decision",
        json=decision(body, action="corrected", corrected=CORRECTED),
    )

    assert reopen(client, group_id).status_code == 201
    assert client.get(f"/reviews/{group_id}.json").json()["parsed"]["total"] == 1000


def test_undecided_document_cannot_be_reopened(client, headers):
    group_id, _ = push(client, headers)

    assert reopen(client, group_id).status_code == 409


def test_reopen_checks_the_person_and_the_document(client, headers):
    group_id, body = push(client, headers)
    client.post(f"/reviews/{group_id}/decision", json=decision(body, action="rejected"))

    assert reopen(client, group_id, "idegen").status_code == 422
    assert reopen(client, uuid4()).status_code == 404


def test_reopened_document_takes_a_new_reading_again(client, headers):
    group_id, body = push(client, headers)
    client.post(f"/reviews/{group_id}/decision", json=decision(body, action="rejected"))
    reopen(client, group_id)

    push(client, headers, group_id=group_id, result="ok", checks={})

    assert client.get(f"/reviews/{group_id}.json").json()["label"] == "rendben"


def test_worker_reopen_needs_no_second_pull(client, headers):
    group_id, body = push(client, headers)
    client.post(f"/reviews/{group_id}/decision", json=decision(body, action="rejected"))
    decision_id = client.get("/inbox/decisions", headers=headers).json()["decisions"][0]["id"]
    client.post(f"/inbox/decisions/{decision_id}/close", headers=headers)
    request = {"id": str(uuid4()), "decided_by": "person_a"}

    for _ in range(2):
        response = client.post(f"/inbox/reviews/{group_id}/reopen", json=request, headers=headers)
        assert response.status_code == 204

    assert client.get(f"/reviews/{group_id}.json").json()["state"] == "open"
    assert client.get("/inbox/decisions", headers=headers).json()["decisions"] == []


def test_worker_reopen_needs_token_and_tolerates_a_missing_package(client, headers):
    request = {"id": str(uuid4()), "decided_by": "person_a"}

    assert client.post(f"/inbox/reviews/{uuid4()}/reopen", json=request).status_code == 401
    response = client.post(f"/inbox/reviews/{uuid4()}/reopen", json=request, headers=headers)
    assert response.status_code == 204


def test_old_inbox_with_one_decision_per_document_is_migrated(client, headers, inbox_dir):
    group_id, body = push(client, headers)
    client.post(f"/reviews/{group_id}/decision", json=decision(body, action="rejected"))
    with inbox.connect() as conn:
        conn.execute("alter table review_decision rename to review_decision_mostani")
        conn.execute(
            "create table review_decision (id text primary key, "
            "group_id text not null unique references review (group_id), parse_id text not null, "
            "action text not null, corrected text, decided_by text not null, "
            "decided_at text not null, synced_at text)"
        )
        conn.execute("insert into review_decision select * from review_decision_mostani")
        conn.execute("drop table review_decision_mostani")
        conn.execute("pragma user_version = 1")

    assert reopen(client, group_id).status_code == 201

    with inbox.connect() as conn:
        assert conn.execute("pragma user_version").fetchone()[0] == inbox.LATEST_VERSION
    assert inbox.queue_counts()["review"] == 1


def test_non_expense_explains_itself_without_failed_checks(client, headers):
    draft = {"store_name": "Példa Kft.", "purchased_on": "2026-10-18", "total": 2540, "items": []}
    group_id, _ = push(
        client,
        headers,
        result="unparsed",
        document_type="non_expense",
        parsed={"document_type": "non_expense", "items": [], "total": None, "draft": draft},
        checks={"sum": {"ok": False, "expected": None, "actual": 0}},
    )

    detail = client.get(f"/reviews/{group_id}.json").json()

    assert detail["failed"] == []
    assert "nem kiadás" in detail["note"]
    assert detail["show_text"] is True
    assert detail["parsed"]["draft"]["total"] == 2540
    assert detail["items"] == 0
    assert detail["store_name"] == "Példa Kft."
    assert detail["purchased_on"] == "2026-10-18"
    assert detail["total"] is None


def test_unknown_table_says_that_rows_are_only_suggested(client, headers):
    parsed = PARSED | {"items": [], "draft": {"items": [{"name": "Havi díj", "value": 1270}]}}
    group_id, _ = push(client, headers, parsed=parsed)

    assert "Javítom" in client.get(f"/reviews/{group_id}.json").json()["note"]


def test_decided_document_has_no_note(client, headers):
    group_id, body = push(client, headers, document_type="non_expense", result="unparsed")
    client.post(f"/reviews/{group_id}/decision", json=decision(body, action="rejected"))

    assert client.get(f"/reviews/{group_id}.json").json()["note"] is None


@pytest.mark.parametrize("path", ["/", "/review", "/status"])
def test_every_page_has_the_menu(client, path):
    page = client.get(path).text

    assert 'class="menu"' in page
    assert all(f'href="{target}"' in page for target in ("/", "/review", "/status"))
    assert 'aria-current="page"' in page


def test_status_card_links_to_the_review_page():
    from app import status

    card = status.upload_card(None, {"review": 2})

    assert card["link"]["url"] == "/review"
    assert json.dumps(card["facts"], ensure_ascii=False).count("Ellenőrzésre vár") == 1
