"""A postaláda API kliense. A kapcsolatot mindig a worker nyitja, a Pi-re költözéskor csak a cím változik."""

from uuid import UUID

import httpx


class Inbox:
    def __init__(self, base_url: str, token: str, transport: httpx.BaseTransport | None = None):
        self.client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
            transport=transport,
        )

    def list_new(self) -> list[dict]:
        response = self.client.get("/inbox/items", params={"status": "new"})
        response.raise_for_status()
        return response.json()["items"]

    def download(self, item_id: str) -> bytes:
        response = self.client.get(f"/inbox/items/{item_id}/file")
        response.raise_for_status()
        return response.content

    def close(self, item_id: str, outcome: dict | None) -> None:
        self.client.post(f"/inbox/items/{item_id}/close", json=outcome).raise_for_status()

    def known_reviews(self) -> dict[str, dict]:
        response = self.client.get("/inbox/reviews")
        response.raise_for_status()
        return {review["group_id"]: review for review in response.json()["reviews"]}

    def put_review_page(self, group_id: UUID, page_no: int, content: bytes) -> None:
        self.client.put(
            f"/inbox/reviews/{group_id}/pages/{page_no}", content=content
        ).raise_for_status()

    def put_review(self, group_id: UUID, package: dict) -> None:
        self.client.put(f"/inbox/reviews/{group_id}", json=package).raise_for_status()

    def open_decisions(self) -> list[dict]:
        response = self.client.get("/inbox/decisions")
        response.raise_for_status()
        return response.json()["decisions"]

    def reopen_review(self, group_id: UUID, decision_id: UUID, decided_by: str) -> None:
        self.client.post(
            f"/inbox/reviews/{group_id}/reopen",
            json={"id": str(decision_id), "decided_by": decided_by},
        ).raise_for_status()

    def open_events(self) -> list[dict]:
        response = self.client.get("/inbox/events")
        response.raise_for_status()
        return response.json()["events"]

    def close_event(self, event_id: str) -> None:
        self.client.post(f"/inbox/events/{event_id}/close").raise_for_status()

    def report_deposit(self, report: dict) -> None:
        self.client.post("/inbox/status/deposit", json=report).raise_for_status()

    def close_decision(self, decision_id: str) -> None:
        self.client.post(f"/inbox/decisions/{decision_id}/close").raise_for_status()
