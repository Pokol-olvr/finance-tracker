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

INSERT_ITEM = """
insert into inbox_item
  (id, sha256, filename, content_type, size_bytes, uploaded_by, uploaded_at,
   purchased_by, purchase_date, payer, tags)
values
  (:id, :sha256, :filename, :content_type, :size_bytes, :uploaded_by, :uploaded_at,
   :purchased_by, :purchase_date, :payer, :tags)
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
    return conn


def file_path(item_id: UUID) -> Path:
    return get_settings().inbox_dir / str(item_id)


def to_item(row: sqlite3.Row) -> dict:
    return dict(row) | {"tags": json.loads(row["tags"])}


def add(form: UploadForm, content: bytes, filename: str, content_type: str) -> dict:
    """Elteszi a fájlt változatlanul; a sor csak a teljes fájl után jelenik meg a workernek."""
    item = {
        "id": str(uuid4()),
        "sha256": hashlib.sha256(content).hexdigest(),
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(content),
        "uploaded_by": form.uploaded_by,
        "uploaded_at": datetime.now(UTC).isoformat(),
        "purchased_by": form.purchased_by,
        "purchase_date": form.purchase_date.isoformat(),
        "payer": form.payer,
        "tags": json.dumps(form.tags, ensure_ascii=False),
    }
    path = file_path(item["id"])
    path.write_bytes(content)
    try:
        with closing(connect()) as conn, conn:
            conn.execute(INSERT_ITEM, item)
    except sqlite3.Error:
        path.unlink(missing_ok=True)
        raise
    return item


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
    with closing(connect()) as conn:
        rows = conn.execute("select status, count(*) from inbox_item group by status").fetchall()
    return {row[0]: row[1] for row in rows}


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
