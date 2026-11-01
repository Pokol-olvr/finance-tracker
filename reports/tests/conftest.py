"""Kitalált adatok: a riportok a valódi goldot csak futás közben látják."""

import os
from datetime import date

import pandas as pd
import pytest
from app import data, metrics

os.environ.setdefault("WEBAPP_URL", "http://127.0.0.1:8000")


@pytest.fixture
def gold(monkeypatch):
    """A gold kitalált adatokkal; a teszt felül is írhatja a lekérdezések eredményét."""
    month = metrics.first_of_month(date.today())
    fake = {
        "monthly": pd.DataFrame(
            {
                "month": [metrics.shift_month(month, -offset) for offset in (3, 2, 1, 0)],
                "income": [400000.0, 400000.0, 500000.0, 500000.0],
                "expense": [300000.0, 320000.0, 340000.0, 250000.0],
            }
        ),
        "categories": pd.DataFrame(
            {"category": ["élelmiszer", "besorolatlan"], "expense": [200000.0, 50000.0]}
        ),
        "documents": pd.DataFrame(
            {
                "group_id": ["11111111-1111-1111-1111-111111111111"],
                "occurred_on": [date(2026, 10, 14)],
                "store_name": ["Kitalált Élelmiszer Kft."],
                "payer": ["shared"],
                "item_count": [2],
                "total": [649.0],
            }
        ),
        "items": pd.DataFrame(
            {
                "name": ["KENYÉR 500G", "DRS GÖNGYÖLEG"],
                "kind": ["item", "deposit"],
                "category": ["élelmiszer", None],
                "quantity": [1.0, None],
                "unit": ["DB", None],
                "value": [599.0, 50.0],
            }
        ),
        "pending": 0,
    }
    monkeypatch.setattr(data, "payers", lambda: ["person_a", "shared"])
    monkeypatch.setattr(data, "monthly", lambda payer: fake["monthly"])
    monkeypatch.setattr(data, "categories", lambda month, payer: fake["categories"])
    monkeypatch.setattr(data, "pending_documents", lambda: fake["pending"])
    monkeypatch.setattr(data, "expected_deposit", lambda: 1250.0)
    monkeypatch.setattr(
        data, "documents",
        lambda payer: fake["documents"][
            fake["documents"]["payer"].eq(payer) if payer else [True] * len(fake["documents"])
        ],
    )
    monkeypatch.setattr(data, "document_items", lambda group_id: fake["items"])
    return fake
