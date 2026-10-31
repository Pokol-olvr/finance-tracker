"""A bronz írása. A Pi-re költözéskor ez a modul cserélődik a postaládára."""

import psycopg

from app.schemas import ManualEntry

INSERT_ENTRY = """
insert into bronze.manual_entry
  (id, entered_by, kind, amount, currency, occurred_on, purchased_by, payer, tags, note)
values
  (%(id)s, %(entered_by)s, %(kind)s, %(amount)s, %(currency)s, %(occurred_on)s,
   %(purchased_by)s, %(payer)s, %(tags)s, %(note)s)
on conflict (id) do nothing
returning id
"""


def insert_entry(conn: psycopg.Connection, entry: ManualEntry) -> bool:
    """Beszúrja a bejegyzést; False, ha ez az id már megvan."""
    return conn.execute(INSERT_ENTRY, entry.model_dump()).fetchone() is not None
