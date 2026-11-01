"""A postaláda: fájlok és SQLite-tábla. Az írás csak itt történik, a FIN-308-cal a Pi-re költözik."""

import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from app.config import get_settings
from app.schemas import (
    CloseResult,
    ReviewDecision,
    ReviewPackage,
    UploadForm,
    WorkerReopen,
)

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
    # A worker által visszatöltött csomagok; a fájljaik a reviews/ mappában vannak.
    """
create table if not exists review (
  group_id       text primary key,
  parse_id       text not null,
  parser_version text not null,
  state          text not null check (state in ('open', 'closed')),
  result         text not null,
  document_type  text,
  parsed         text not null,
  checks         text not null,
  ocr_text       text not null,
  content_types  text not null,
  uploaded_at    text not null,
  closed_at      text
)
""",
    """
create table if not exists review_decision (
  id         text primary key,
  group_id   text not null references review (group_id),
  parse_id   text not null,
  action     text not null,
  corrected  text,
  decided_by text not null,
  decided_at text not null,
  synced_at  text
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

# A 2-es verzió: egy dokumentumhoz több döntés is tartozhat, mert az újranyitás is egy döntés.
MIGRATE_TO_2 = (
    """
create table review_decision_new (
  id         text primary key,
  group_id   text not null references review (group_id),
  parse_id   text not null,
  action     text not null,
  corrected  text,
  decided_by text not null,
  decided_at text not null,
  synced_at  text
)
""",
    """
insert into review_decision_new
  (id, group_id, parse_id, action, corrected, decided_by, decided_at, synced_at)
select id, group_id, parse_id, action, corrected, decided_by, decided_at, synced_at
from review_decision
""",
    "drop table review_decision",
    "alter table review_decision_new rename to review_decision",
    "pragma user_version = 2",
)
LATEST_VERSION = 2

INSERT_ITEM = """
insert into inbox_item
  (id, sha256, filename, content_type, size_bytes, uploaded_by, uploaded_at,
   purchased_by, purchase_date, payer, tags, group_id, page_no, page_count)
values
  (:id, :sha256, :filename, :content_type, :size_bytes, :uploaded_by, :uploaded_at,
   :purchased_by, :purchase_date, :payer, :tags, :group_id, :page_no, :page_count)
"""

UPSERT_REVIEW = """
insert into review
  (group_id, parse_id, parser_version, state, result, document_type, parsed, checks,
   ocr_text, content_types, uploaded_at, closed_at)
values
  (:group_id, :parse_id, :parser_version, :state, :result, :document_type, :parsed, :checks,
   :ocr_text, :content_types, :uploaded_at, :closed_at)
on conflict (group_id) do update set
  parse_id = excluded.parse_id,
  parser_version = excluded.parser_version,
  state = excluded.state,
  result = excluded.result,
  document_type = excluded.document_type,
  parsed = excluded.parsed,
  checks = excluded.checks,
  ocr_text = excluded.ocr_text,
  content_types = excluded.content_types,
  closed_at = case when excluded.state = 'open' then null
                   else coalesce(review.closed_at, excluded.closed_at) end
"""

# Az újrafeldolgozás után az állapotoldal is a friss eredményt mutassa.
REFRESH_RESULTS = """
update inbox_result set result = ?, items = ?
where result not in ('duplicate', 'reopened')
  and item_id in (select id from inbox_item where sha256 in (select value from json_each(?)))
"""

# Döntést kér, amit a feldolgozó nem tudott rendben lévőnek mondani, kivéve a nem kiadást.
OPEN_RESULTS = frozenset({"review", "unparsed", "unreadable"})
# Az újranyitás is a döntések közé kerül, így a korábbi döntés nem vész el.
REOPENED = "reopened"
NON_EXPENSE = "non_expense"
# A lezárt csomag ennyi napig nézhető vissza; a nyitott a döntésig marad.
KEEP_DAYS = 30
MAX_REVIEW_PAGES = 20

# A HEIC fájl a típusát az ftyp dobozban adja meg.
PDF_TYPE = "application/pdf"
HEIC_BRANDS = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"})


def detect_file_type(content: bytes) -> str | None:
    """A fájl típusa a tartalma alapján; None, ha nem támogatott."""
    if content.startswith(b"%PDF-"):
        return PDF_TYPE
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
    if conn.execute("pragma user_version").fetchone()[0] < LATEST_VERSION:
        migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.execute("begin immediate")
    # A zárolás után újra kell nézni: közben egy másik kérés is elvégezhette.
    version = conn.execute("pragma user_version").fetchone()[0]
    if version < 1:
        for statement in MIGRATE_TO_1:
            conn.execute(statement)
    if version < 2:
        for statement in MIGRATE_TO_2:
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
    """Egy dokumentum fájljai, képek vagy PDF-ek: vagy mind bekerül, vagy egyik sem."""
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
        review = conn.execute("select count(*) from review where state = 'open'").fetchone()[0]
    return {row[0]: row[1] for row in rows} | {"review": review}


def recent_results(limit: int) -> list[dict]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "select result, seconds, items, finished_at from inbox_result "
            "order by finished_at desc limit ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


class ReviewConflict(Exception):
    pass


def review_folder(group_id: UUID) -> Path:
    return get_settings().inbox_dir / "reviews" / str(group_id)


def review_page_path(group_id: UUID, page_no: int) -> Path:
    return review_folder(group_id) / str(page_no)


def save_review_page(group_id: UUID, page_no: int, content: bytes) -> None:
    review_folder(group_id).mkdir(parents=True, exist_ok=True)
    review_page_path(group_id, page_no).write_bytes(content)


def needs_decision(package: ReviewPackage) -> bool:
    return package.result in OPEN_RESULTS and package.document_type != NON_EXPENSE


def save_review(group_id: UUID, package: ReviewPackage) -> bool:
    """Felveszi vagy frissíti a csomagot; a meghozott döntés mellett nem változik."""
    is_open = needs_decision(package)
    fields = package.model_dump(mode="json", exclude={"sha256s"}) | {
        "group_id": str(group_id),
        "state": "open" if is_open else "closed",
        "parsed": json.dumps(package.parsed, ensure_ascii=False),
        "checks": json.dumps(package.checks, ensure_ascii=False),
        "content_types": json.dumps(package.content_types),
        "closed_at": None if is_open else datetime.now(UTC).isoformat(),
    }
    items = len(package.parsed.get("items", []))
    with closing(connect()) as conn, conn:
        if is_decided(conn, group_id):
            return False
        conn.execute(UPSERT_REVIEW, fields)
        conn.execute(REFRESH_RESULTS, (package.result, items, json.dumps(package.sha256s)))
    return True


def latest_action(conn: sqlite3.Connection, group_id: UUID) -> str | None:
    row = conn.execute(
        "select action from review_decision where group_id = ? "
        "order by decided_at desc, rowid desc limit 1",
        (str(group_id),),
    ).fetchone()
    return row["action"] if row else None


def is_decided(conn: sqlite3.Connection, group_id: UUID) -> bool:
    return latest_action(conn, group_id) not in (None, REOPENED)


def known_reviews() -> list[dict]:
    with closing(connect()) as conn:
        rows = conn.execute(f"{SELECT_REVIEW}").fetchall()
    return [
        {
            "group_id": row["group_id"],
            "parse_id": row["parse_id"],
            "decided": row["action"] not in (None, REOPENED),
        }
        for row in rows
    ]


def to_review(row: sqlite3.Row) -> dict:
    review = dict(row)
    decision = {key: review.pop(key) for key in ("action", "corrected", "decided_by", "decided_at")}
    for key in ("parsed", "checks", "content_types"):
        review[key] = json.loads(review[key])
    if decision["corrected"]:
        decision["corrected"] = json.loads(decision["corrected"])
    decided = decision["action"] not in (None, REOPENED)
    return review | {"decision": decision if decided else None}


# Dokumentumonként a legutóbbi döntés; a korábbiak a bronzba kerültek, itt nem számítanak.
SELECT_REVIEW = """
select r.*, d.action, d.corrected, d.decided_by, d.decided_at
from review as r
left join review_decision as d on d.rowid = (
  select last.rowid from review_decision as last
  where last.group_id = r.group_id
  order by last.decided_at desc, last.rowid desc
  limit 1
)
"""


def get_review(group_id: UUID) -> dict | None:
    with closing(connect()) as conn:
        row = conn.execute(f"{SELECT_REVIEW} where r.group_id = ?", (str(group_id),)).fetchone()
    return to_review(row) if row else None


def list_reviews() -> list[dict]:
    """Elöl a döntésre várók, a legrégebbi az első; utána a lezártak, a legfrissebb az első."""
    with closing(connect()) as conn:
        rows = conn.execute(
            f"{SELECT_REVIEW} order by r.state = 'closed', "
            "case when r.state = 'open' then r.uploaded_at end, r.uploaded_at desc"
        ).fetchall()
    return [to_review(row) for row in rows]


def decide(group_id: UUID, decision: ReviewDecision) -> str | None:
    """Egyszerre egy érvényes döntés van, ezért a dupla kattintásból is egy lesz."""
    now = datetime.now(UTC).isoformat()
    corrected = decision.corrected.model_dump(mode="json") if decision.corrected else None
    with closing(connect()) as conn, conn:
        conn.execute("begin immediate")
        row = conn.execute(
            "select parse_id from review where group_id = ?", (str(group_id),)
        ).fetchone()
        if row is None:
            return None
        if row["parse_id"] != str(decision.parse_id):
            raise ReviewConflict("A dokumentum közben újra feldolgozódott, töltsd be újra.")
        if is_decided(conn, group_id):
            raise ReviewConflict("Erről a dokumentumról már született döntés.")
        decision_id = str(uuid4())
        conn.execute(
            "insert into review_decision "
            "(id, group_id, parse_id, action, corrected, decided_by, decided_at) "
            "values (?, ?, ?, ?, ?, ?, ?)",
            (
                decision_id,
                str(group_id),
                row["parse_id"],
                decision.action,
                json.dumps(corrected, ensure_ascii=False) if corrected else None,
                decision.decided_by,
                now,
            ),
        )
        conn.execute(
            "update review set state = 'closed', closed_at = ? where group_id = ?",
            (now, str(group_id)),
        )
    return decision_id


def write_reopen(
    conn: sqlite3.Connection,
    group_id: UUID,
    parse_id: str,
    decision_id: str,
    decided_by: str,
    synced_at: str | None,
) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "insert or ignore into review_decision "
        "(id, group_id, parse_id, action, decided_by, decided_at, synced_at) "
        "values (?, ?, ?, ?, ?, ?, ?)",
        (decision_id, str(group_id), parse_id, REOPENED, decided_by, now, synced_at),
    )
    conn.execute(
        "update review set state = 'open', closed_at = null where group_id = ?", (str(group_id),)
    )


def reopen(group_id: UUID, decided_by: str) -> bool:
    """A képernyő gombja: a döntést a worker húzza le a bronzba, mint a többit."""
    with closing(connect()) as conn, conn:
        conn.execute("begin immediate")
        row = conn.execute(
            "select parse_id from review where group_id = ?", (str(group_id),)
        ).fetchone()
        if row is None:
            return False
        if not is_decided(conn, group_id):
            raise ReviewConflict("Ennél a dokumentumnál nincs visszavonható döntés.")
        write_reopen(conn, group_id, row["parse_id"], str(uuid4()), decided_by, None)
    return True


def reopen_from_worker(group_id: UUID, request: WorkerReopen) -> None:
    """Újrafeltöltéskor a döntés már a bronzban van; a hiányzó csomagot a worker pótolja."""
    now = datetime.now(UTC).isoformat()
    with closing(connect()) as conn, conn:
        conn.execute("begin immediate")
        row = conn.execute(
            "select parse_id from review where group_id = ?", (str(group_id),)
        ).fetchone()
        if row:
            write_reopen(conn, group_id, row["parse_id"], str(request.id), request.decided_by, now)


def next_open_review() -> str | None:
    with closing(connect()) as conn:
        row = conn.execute(
            "select group_id from review where state = 'open' order by uploaded_at limit 1"
        ).fetchone()
    return row["group_id"] if row else None


def open_decisions() -> list[dict]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "select id, group_id, parse_id, action, corrected, decided_by, decided_at "
            "from review_decision where synced_at is null order by decided_at"
        ).fetchall()
    return [
        dict(row) | {"corrected": json.loads(row["corrected"]) if row["corrected"] else None}
        for row in rows
    ]


def close_decision(decision_id: UUID) -> bool:
    now = datetime.now(UTC).isoformat()
    with closing(connect()) as conn, conn:
        found = conn.execute(
            "update review_decision set synced_at = coalesce(synced_at, ?) where id = ?",
            (now, str(decision_id)),
        ).rowcount
    return bool(found)


def purge_reviews(now: datetime | None = None) -> None:
    """A lezárt csomag a megőrzési idő után eltűnik; a bronzba még nem jutott döntés marad."""
    limit = ((now or datetime.now(UTC)) - timedelta(days=KEEP_DAYS)).isoformat()
    with closing(connect()) as conn, conn:
        rows = conn.execute(
            "select r.group_id from review as r "
            "where r.state = 'closed' and r.closed_at < ? and not exists ("
            "select 1 from review_decision as d "
            "where d.group_id = r.group_id and d.synced_at is null)",
            (limit,),
        ).fetchall()
        groups = [(row["group_id"],) for row in rows]
        conn.executemany("delete from review_decision where group_id = ?", groups)
        conn.executemany("delete from review where group_id = ?", groups)
    for (group_id,) in groups:
        shutil.rmtree(review_folder(UUID(group_id)), ignore_errors=True)


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
