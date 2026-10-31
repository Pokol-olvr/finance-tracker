"""Valódi bronz írás; a tranzakció a végén visszagörgetődik, így nem hagy adatot."""

import os
from uuid import uuid4

import psycopg
import pytest
from app import store
from app.schemas import ManualEntry

test_database_url = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not test_database_url, reason="nincs TEST_DATABASE_URL")


@pytest.fixture
def conn():
    with psycopg.connect(test_database_url) as connection:
        yield connection
        connection.rollback()


def test_insert_writes_row_once(conn, valid_entry):
    entry = ManualEntry.model_validate(valid_entry | {"id": str(uuid4())})

    assert store.insert_entry(conn, entry) is True
    assert store.insert_entry(conn, entry) is False

    row = conn.execute(
        "select amount, currency, payer, purchased_by, tags from bronze.manual_entry where id = %s",
        (entry.id,),
    ).fetchall()
    assert row == [(entry.amount, "HUF", "shared", "person_a", ["élelmiszer"])]


def test_app_writer_cannot_update(conn):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("update bronze.manual_entry set note = 'x'")
