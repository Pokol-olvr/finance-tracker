"""A postaláda: fájlok és SQLite-tábla. Az írás csak itt történik, a FIN-308-cal a Pi-re költözik."""

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.config import get_settings
from app.schemas import CloseResult, UploadForm

CREATE_TABLES = (
    """
create table if not exists inbox_item (
  id            text primary key,
  sha256        text not null,
  filename      text not null,
  content_type  text not null,
  size_bytes    integer not null,
  uploaded_by   text not null,
  uploaded_at   text not null,
  purchased_by  text not null,
  purchase_date text not null,
  payer         text not null,
  tags          text not null,
  status        text not null default 'new' check (status in ('new', 'closed')),
  closed_at     text
)
""",
    """
create table if not exists inbox_result (
  item_id     text primary key references inbox_item (id),
  result      text not null,
  seconds     real,
  items       integer,
  finished_at text not null
)
""",
    # Forrásonként csak a legutóbbi jelentés: az oldal a pillanatnyi állapotot mutatja.
    """
create table if not exists status_report (
  source      text primary key,
  payload     text not null,
  received_at text not null
)
""",
)

# Az 1-es verzió: opcionális dátum és több képből álló blokk. A SQLite egy oszlop kötelezőségét
# nem tudja módosítani, ezért a tábla újraépül.
MIGRATE_TO_1 = (
    """
create table inbox_item_new (
  id            text primary key,
  sha256        text not null,
  filename      text not null,
  content_type  text not null,
  size_bytes    integer not null,
  uploaded_by   text not null,
  uploaded_at   text not null,
  purchased_by  text not null,
  purchase_date text,
  payer         text not null,
  tags          text not null,
  group_id      text,
  page_no       integer not null default 1,
  page_count    integer not null default 1,
  status        text not null default 'new' check (status in ('new', 'closed')),
  closed_at     text
)
""",
    """
insert into inbox_item_new
  (id, sha256, filename, content_type, size_bytes, uploaded_by, uploaded_at,
   purchased_by, purchase_date, payer, tags, status, closed_at)
select
  id, sha256, filename, content_type, size_bytes, uploaded_by, uploaded_at,
  purchased_by, purchase_date, payer, tags, status, closed_at
from inbox_item
""",
    "drop table inbox_item",
    "alter table inbox_item_new rename to inbox_item",
    "pragma user_version = 1",
)

INSERT_ITEM = """
insert into inbox_item
  (id, sha256, filename, content_type, size_bytes, uploaded_by, uploaded_at,
   purchased_by, purchase_date, payer, tags, group_id, page_no, page_count)
values
  (:id, :sha256, :filename, :content_type, :size_bytes, :uploaded_by, :uploaded_at,
   :purchased_by, :purchase_date, :payer, :tags, :group_id, :page_no, :page_count)
"""

# A HEIC fájl a típusát az ftyp dobozban adja meg.
HEIC_BRANDS = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"})


def detect_image_type(content: bytes) -> str | None:
    """A fájl típusa a tartalma alapján; None, ha nem támogatott kép."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content[4:8] == b"ftyp" and content[8:12] in HEIC_BRANDS:
        return "image/heic"
    return None


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().inbox_dir / "inbox.sqlite3")
    conn.row_factory = sqlite3.Row
    for statement in CREATE_TABLES:
        conn.execute(statement)
    if conn.execute("pragma user_version").fetchone()[0] < 1:
        migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.execute("begin immediate")
    # A zárolás után újra kell nézni: közben egy másik kérés is elvégezhette.
    if conn.execute("pragma user_version").fetchone()[0] < 1:
        for statement in MIGRATE_TO_1:
            conn.execute(statement)
    conn.commit()


def file_path(item_id: UUID) -> Path:
    return get_settings().inbox_dir / str(item_id)


def to_item(row: sqlite3.Row) -> dict:
    return dict(row) | {"tags": json.loads(row["tags"])}


def new_item(form: UploadForm, content: bytes, filename: str, content_type: str) -> dict:
    return {
        "id": str(uuid4()),
        "sha256": hashlib.sha256(content).hexdigest(),
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(content),
        "uploaded_by": form.uploaded_by,
        "uploaded_at": datetime.now(UTC).isoformat(),
        "purchased_by": form.purchased_by,
        "purchase_date": form.purchase_date.isoformat() if form.purchase_date else None,
        "payer": form.payer,
        "tags": json.dumps(form.tags, ensure_ascii=False),
        "group_id": None,
        "page_no": 1,
        "page_count": 1,
    }


def store_items(items: list[dict], contents: list[bytes]) -> None:
    """A sorok egyszerre, a teljes fájlok után jelennek meg a workernek."""
    paths = [file_path(item["id"]) for item in items]
    try:
        for path, content in zip(paths, contents, strict=True):
            path.write_bytes(content)
        with closing(connect()) as conn, conn:
            conn.executemany(INSERT_ITEM, items)
    except (OSError, sqlite3.Error):
        for path in paths:
            path.unlink(missing_ok=True)
        raise


def add(form: UploadForm, content: bytes, filename: str, content_type: str) -> dict:
    """Elteszi a fájlt változatlanul."""
    item = new_item(form, content, filename, content_type)
    store_items([item], [content])
    return item


def add_group(form: UploadForm, files: list[tuple[bytes, str, str]]) -> str:
    """Egy hosszú blokk képei: vagy mind bekerül, vagy egyik sem."""
    group_id = str(uuid4())
    items = [
        new_item(form, content, filename, content_type)
        | {"group_id": group_id, "page_no": page_no, "page_count": len(files)}
        for page_no, (content, filename, content_type) in enumerate(files, 1)
    ]
    store_items(items, [content for content, _, _ in files])
    return group_id


def list_items(status: str) -> list[dict]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "select * from inbox_item where status = ? order by uploaded_at", (status,)
        ).fetchall()
    return [to_item(row) for row in rows]


def get_item(item_id: UUID) -> dict | None:
    with closing(connect()) as conn:
        row = conn.execute("select * from inbox_item where id = ?", (str(item_id),)).fetchone()
    return to_item(row) if row else None


def close_item(item_id: UUID, outcome: CloseResult | None = None) -> bool:
    """Lezárja a tételt és törli a fájlt; ismételt hívásra is igaz, False, ha nincs ilyen tétel."""
    now = datetime.now(UTC).isoformat()
    with closing(connect()) as conn, conn:
        found = conn.execute(
            "update inbox_item set status = 'closed', closed_at = coalesce(closed_at, ?) "
            "where id = ?",
            (now, str(item_id)),
        ).rowcount
        if found and outcome:
            conn.execute(
                "insert or ignore into inbox_result (item_id, result, seconds, items, finished_at) "
                "values (?, ?, ?, ?, ?)",
                (str(item_id), outcome.result, outcome.seconds, outcome.items, now),
            )
    if found:
        file_path(item_id).unlink(missing_ok=True)
    return bool(found)


def queue_counts() -> dict[str, int]:
    """Blokkokat számol: a több képből álló blokk egynek számít."""
    with closing(connect()) as conn:
        rows = conn.execute(
            "select status, count(distinct coalesce(group_id, id)) from inbox_item group by status"
        ).fetchall()
        review = conn.execute(
            "select count(*) from inbox_result where result = 'review'"
        ).fetchone()[0]
    return {row[0]: row[1] for row in rows} | {"review": review}


def recent_results(limit: int) -> list[dict]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "select result, seconds, items, finished_at from inbox_result "
            "order by finished_at desc limit ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_report(source: str, payload: str) -> None:
    with closing(connect()) as conn, conn:
        conn.execute(
            "insert into status_report (source, payload, received_at) values (?, ?, ?) "
            "on conflict (source) do update set "
            "payload = excluded.payload, received_at = excluded.received_at",
            (source, payload, datetime.now(UTC).isoformat()),
        )


def reports() -> dict[str, dict]:
    with closing(connect()) as conn:
        rows = conn.execute("select source, payload, received_at from status_report").fetchall()
    return {
        row["source"]: {"payload": json.loads(row["payload"]), "received_at": row["received_at"]}
        for row in rows
    }
