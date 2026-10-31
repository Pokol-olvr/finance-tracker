"""A bronz írása. A réteg csak hozzáfűzhető, ezért minden lépés újrafuttatható."""

from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

INSERT_DOCUMENT = """
insert into bronze.raw_document
  (sha256, object_key, source_type, uploaded_by, uploaded_at,
   purchased_by, purchase_date, payer, tags)
values
  (%(sha256)s, %(object_key)s, 'photo', %(uploaded_by)s, %(uploaded_at)s,
   %(purchased_by)s, %(purchase_date)s, %(payer)s, %(tags)s)
on conflict (sha256) do nothing
returning id
"""

INSERT_EXTRACTION = """
insert into bronze.extraction (document_id, model_name, model_version, prompt_version, payload)
values (%s, %s, %s, %s, %s)
"""

HAS_EXTRACTION = """
select 1 from bronze.extraction
where document_id = %s and model_name = %s and model_version = %s and prompt_version = %s
"""


def find_document(conn: psycopg.Connection, sha256: str) -> UUID | None:
    row = conn.execute(
        "select id from bronze.raw_document where sha256 = %s", (sha256,)
    ).fetchone()
    return row[0] if row else None


def insert_document(conn: psycopg.Connection, item: dict, object_key: str) -> UUID:
    row = conn.execute(INSERT_DOCUMENT, item | {"object_key": object_key}).fetchone()
    return row[0] if row else find_document(conn, item["sha256"])


def has_extraction(
    conn: psycopg.Connection, document_id: UUID, model_name: str, model_version: str, prompt_version: str
) -> bool:
    row = conn.execute(
        HAS_EXTRACTION, (document_id, model_name, model_version, prompt_version)
    ).fetchone()
    return row is not None


def insert_extraction(
    conn: psycopg.Connection,
    document_id: UUID,
    model_name: str,
    model_version: str,
    prompt_version: str,
    payload: dict,
) -> None:
    conn.execute(
        INSERT_EXTRACTION,
        (document_id, model_name, model_version, prompt_version, Jsonb(payload)),
    )
