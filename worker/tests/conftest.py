import hashlib
import os
from io import BytesIO
from uuid import uuid4

import psycopg
import pytest
from app.storage import BUCKET, Storage
from PIL import Image

test_database_url = os.environ.get("TEST_DATABASE_URL")
test_garage_endpoint = os.environ.get("TEST_GARAGE_ENDPOINT")


def invented_receipt() -> bytes:
    """Minden hívás más hash-t ad, mert a bronzban a hash egyedi."""
    image = Image.frombytes("RGB", (16, 16), os.urandom(16 * 16 * 3))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_item(content: bytes) -> dict:
    return {
        "id": str(uuid4()),
        "sha256": hashlib.sha256(content).hexdigest(),
        "content_type": "image/png",
        "uploaded_by": "person_a",
        "uploaded_at": "2026-12-01T10:00:00+00:00",
        "purchased_by": "person_b",
        "purchase_date": "2026-11-30",
        "payer": "shared",
        "tags": ["élelmiszer", "háztartás"],
    }


def no_report(_step: str) -> None:
    pass


class FakeInbox:
    def __init__(self, files: dict[str, bytes]):
        self.files = files
        self.closed: list[str] = []
        self.outcomes: list[dict] = []

    def download(self, item_id: str) -> bytes:
        return self.files[item_id]

    def close(self, item_id: str, outcome: dict) -> None:
        self.closed.append(item_id)
        self.outcomes.append(outcome)


class FakeReader:
    name = "teszt-modell"

    def __init__(self, payload: dict | None = None, error: Exception | None = None):
        self.payload = payload or {"raw_text": "{}", "parsed": {}}
        self.error = error
        self.calls = 0

    def version(self) -> str:
        return "teszt-valtozat"

    def read(self, content: bytes, report) -> dict:
        self.calls += 1
        report("read_json")
        if self.error:
            raise self.error
        return self.payload


@pytest.fixture
def conn():
    if not test_database_url:
        pytest.skip("nincs TEST_DATABASE_URL")
    with psycopg.connect(test_database_url) as connection:
        yield connection
        connection.rollback()


@pytest.fixture
def storage():
    """Valódi Garage; a teszt alatt írt objektumok a végén törlődnek."""
    if not test_garage_endpoint:
        pytest.skip("nincs TEST_GARAGE_ENDPOINT")
    garage = Storage(
        test_garage_endpoint, os.environ["GARAGE_ACCESS_KEY"], os.environ["GARAGE_SECRET_KEY"]
    )
    written: list[str] = []
    original_put = garage.put

    def put(key: str, content: bytes, content_type: str) -> None:
        written.append(key)
        original_put(key, content, content_type)

    garage.put = put
    garage.written = written
    yield garage
    for key in written:
        garage.client.delete_object(Bucket=BUCKET, Key=key)
