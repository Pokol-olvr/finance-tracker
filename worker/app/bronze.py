"""A bronz írása. A réteg csak hozzáfűzhető, ezért minden lépés újrafuttatható."""

from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

INSERT_DOCUMENT = """
insert into bronze.raw_document
  (sha256, object_key, source_type, uploaded_by, uploaded_at,
   purchased_by, purchase_date, payer, tags, group_id, page_no, page_count)
values
  (%(sha256)s, %(object_key)s, %(source_type)s, %(uploaded_by)s, %(uploaded_at)s,
   %(purchased_by)s, %(purchase_date)s, %(payer)s, %(tags)s,
   %(group_id)s, %(page_no)s, %(page_count)s)
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


INSERT_PARSE = """
insert into bronze.receipt_parse
  (group_id, extraction_ids, parser_version, status, payload, checks)
values (%s, %s, %s, %s, %s, %s)
on conflict (group_id, parser_version) do nothing
"""

# Dokumentumonként a legutóbbi kiolvasás; a régi sorok szövege is feldolgozható.
PENDING_PAGES = """
select pages.group_id, pages.extraction_id, pages.page_count, pages.purchase_date,
       pages.uploaded_at, pages.payload
from (
  select
    coalesce(d.group_id, d.id) as group_id,
    e.id as extraction_id,
    d.page_no,
    d.page_count,
    d.purchase_date,
    d.uploaded_at,
    e.payload,
    row_number() over (partition by d.id order by e.created_at desc) as recency
  from bronze.raw_document as d
  join bronze.extraction as e on e.document_id = d.id
) as pages
where pages.recency = 1
  and (%(group_id)s::uuid is null or pages.group_id = %(group_id)s)
  and not exists (
    select 1 from bronze.receipt_parse as p
    where p.group_id = pages.group_id and p.parser_version = %(version)s
  )
order by pages.group_id, pages.page_no
"""

SEEN_ELSEWHERE = """
select 1 from bronze.receipt_parse
where group_id <> %s and payload ->> 'tax_number' = %s and payload ->> 'receipt_number' = %s
limit 1
"""


# A legfrissebb feldolgozás; a csomag a döntésig marad, a rendben lévő régi dokumentum nem kell.
REVIEW_CANDIDATES = """
with latest as (
  select distinct on (group_id)
    id, group_id, status, payload ->> 'document_type' as document_type
  from bronze.receipt_parse
  order by group_id, created_at desc
)
select l.id as parse_id, l.group_id, min(d.uploaded_at) as uploaded_at
from latest as l
join bronze.raw_document as d on coalesce(d.group_id, d.id) = l.group_id
where coalesce(
  (
    select r.decision from bronze.review_decision as r
    where r.group_id = l.group_id
    order by r.decided_at desc
    limit 1
  ),
  'reopened'
) = 'reopened'
group by l.id, l.group_id, l.status, l.document_type
having min(d.uploaded_at) > now() - make_interval(days => %s)
  or (l.status <> 'ok' and l.document_type is distinct from 'non_expense')
order by uploaded_at
"""

REVIEW_PAGES = """
select d.object_key, d.sha256, d.page_no, e.payload ->> 'ocr_text' as ocr_text
from bronze.raw_document as d
left join lateral (
  select payload from bronze.extraction
  where document_id = d.id
  order by created_at desc
  limit 1
) as e on true
where coalesce(d.group_id, d.id) = %s
order by d.page_no
"""

INSERT_DECISION = """
insert into bronze.review_decision
  (id, group_id, parse_id, decision, corrected, decided_by, decided_at)
values
  (%(id)s, %(group_id)s, %(parse_id)s, %(action)s, %(corrected)s, %(decided_by)s, %(decided_at)s)
on conflict (id) do nothing
"""

# A webapp 30 napig tartja a lezárt csomagot, ezért ennél régebbit nem érdemes visszatölteni.
REVIEW_KEEP_DAYS = 30


def find_document(conn: psycopg.Connection, sha256: str) -> UUID | None:
    row = conn.execute(
        "select id from bronze.raw_document where sha256 = %s", (sha256,)
    ).fetchone()
    return row[0] if row else None


def insert_document(
    conn: psycopg.Connection, item: dict, object_key: str, source_type: str = "photo"
) -> UUID:
    fields = item | {"object_key": object_key, "source_type": source_type}
    row = conn.execute(INSERT_DOCUMENT, fields).fetchone()
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


def group_of(conn: psycopg.Connection, document_id: UUID) -> UUID:
    row = conn.execute(
        "select coalesce(group_id, id) from bronze.raw_document where id = %s", (document_id,)
    ).fetchone()
    return row[0]


def pending_pages(
    conn: psycopg.Connection, parser_version: str, group_id: UUID | None = None
) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(PENDING_PAGES, {"group_id": group_id, "version": parser_version})
        return cursor.fetchall()


def parse_result(conn: psycopg.Connection, group_id: UUID, parser_version: str) -> tuple | None:
    """Az állapot és a tételek száma; a blokk tartalma nem hagyja el a bronzot."""
    return conn.execute(
        "select status, jsonb_array_length(coalesce(payload -> 'items', '[]')) "
        "from bronze.receipt_parse where group_id = %s and parser_version = %s",
        (group_id, parser_version),
    ).fetchone()


def seen_elsewhere(
    conn: psycopg.Connection, group_id: UUID, tax_number: str | None, receipt_number: str | None
) -> bool:
    if tax_number is None or receipt_number is None:
        return False
    row = conn.execute(SEEN_ELSEWHERE, (group_id, tax_number, receipt_number)).fetchone()
    return row is not None


def review_candidates(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(REVIEW_CANDIDATES, (REVIEW_KEEP_DAYS,))
        return cursor.fetchall()


def review_parse(conn: psycopg.Connection, parse_id: UUID) -> dict:
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "select id, parser_version, status, payload, checks "
            "from bronze.receipt_parse where id = %s",
            (parse_id,),
        )
        return cursor.fetchone()


def review_pages(conn: psycopg.Connection, group_id: UUID) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(REVIEW_PAGES, (group_id,))
        return cursor.fetchall()


def latest_decision(conn: psycopg.Connection, group_id: UUID) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "select id, decision from bronze.review_decision where group_id = %s "
            "order by decided_at desc limit 1",
            (group_id,),
        )
        return cursor.fetchone()


def latest_parse_id(conn: psycopg.Connection, group_id: UUID) -> UUID:
    row = conn.execute(
        "select id from bronze.receipt_parse where group_id = %s order by created_at desc limit 1",
        (group_id,),
    ).fetchone()
    return row[0]


def insert_decision(conn: psycopg.Connection, decision: dict) -> None:
    corrected = decision["corrected"]
    conn.execute(
        INSERT_DECISION,
        decision | {"corrected": Jsonb(corrected) if corrected is not None else None},
    )


def insert_parse(
    conn: psycopg.Connection,
    group_id: UUID,
    extraction_ids: list[UUID],
    parser_version: str,
    status: str,
    payload: dict,
    checks: dict,
) -> None:
    conn.execute(
        INSERT_PARSE,
        (group_id, extraction_ids, parser_version, status, Jsonb(payload), Jsonb(checks)),
    )
