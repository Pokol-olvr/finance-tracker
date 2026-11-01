"""A postaláda API kliense. A kapcsolatot mindig a worker nyitja, a Pi-re költözéskor csak a cím változik."""

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
