import os

import pytest

os.environ.setdefault("HOUSEHOLD_MEMBERS", "person_a,person_b")
os.environ.setdefault("DATABASE_URL", "postgresql://unused")


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
