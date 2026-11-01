import os

import pytest
from app.config import get_settings

os.environ.setdefault("HOUSEHOLD_MEMBERS", "person_a,person_b")
os.environ.setdefault("DATABASE_URL", "postgresql://unused")
os.environ.setdefault("INBOX_DIR", "/nonexistent")
os.environ.setdefault("WORKER_API_TOKEN", "teszt-token")
os.environ.setdefault("METABASE_URL", "http://127.0.0.1:3000")


@pytest.fixture
def inbox_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("INBOX_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def valid_entry() -> dict:
    return {
        "id": "2f5b9c1e-7a54-4f0e-9d3a-0c1b2a3d4e5f",
        "kind": "expense",
        "amount": "18450.10",
        "occurred_on": "2026-11-16",
        "entered_by": "person_a",
        "payer": "shared",
        "tags": ["élelmiszer"],
    }
