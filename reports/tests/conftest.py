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
                "product": ["kenyér", None],
                "quantity": [1.0, None],
                "unit": ["DB", None],
                "value": [599.0, 50.0],
                "base_unit": ["kg", None],
                "base_unit_price": [1198.0, None],
            }
        ),
        "products": pd.DataFrame(
            {
                "category": ["élelmiszer"],
                "product_family": ["gomba"],
                "product": ["csiperke"],
                "base_unit": ["kg"],
            }
        ),
        "prices": pd.DataFrame(
            {
                "month": [date(2026, 9, 1), date(2026, 10, 1), date(2026, 10, 1)],
                "store_name": ["Kitalált Bolt", "Kitalált Bolt", "Másik Bolt"],
                "unit_price": [1000.0, 1200.0, 1100.0],
                "min_unit_price": [1000.0, 1200.0, 1100.0],
                "max_unit_price": [1000.0, 1200.0, 1100.0],
                "quantity": [1.0, 1.0, 1.0],
                "purchase_count": [2, 1, 1],
            }
        ),
        "pending": 0,
    }
    monkeypatch.setattr(data, "payers", lambda: ["person_a", "shared"])
    monkeypatch.setattr(data, "monthly", lambda payer: fake["monthly"])
    monkeypatch.setattr(data, "categories", lambda month, payer: fake["categories"])
    monkeypatch.setattr(data, "pending_documents", lambda: fake["pending"])
    monkeypatch.setattr(data, "expected_deposit", lambda: 1250.0)
    monkeypatch.setattr(data, "products", lambda: fake["products"])
    monkeypatch.setattr(data, "product_prices", lambda product, base_unit: fake["prices"])
    monkeypatch.setattr(
        data, "documents",
        lambda payer: fake["documents"][
            fake["documents"]["payer"].eq(payer) if payer else [True] * len(fake["documents"])
        ],
    )
    monkeypatch.setattr(data, "document_items", lambda group_id: fake["items"])
    return fake
