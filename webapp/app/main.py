import secrets
from html import escape
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import psycopg
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import inbox, store
from app import status as stack_status
from app.config import get_settings
from app.schemas import (
    CATEGORIES,
    CloseResult,
    HostReport,
    ManualEntry,
    UploadForm,
    WorkerReport,
)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MIN_GROUP_PAGES = 2
MAX_GROUP_PAGES = 5
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Pénzügyi nyomkövető")
bearer = HTTPBearer(auto_error=False)


def connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url)


def require_worker(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    expected = get_settings().worker_token.encode()
    if credentials is None or not secrets.compare_digest(credentials.credentials.encode(), expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Bearer"})


worker_api = APIRouter(prefix="/inbox", dependencies=[Depends(require_worker)])


@app.get("/health")
def health() -> dict[str, str]:
    with connect() as conn:
        conn.execute("select 1")
    return {"status": "ok"}


@app.post("/entries", status_code=status.HTTP_201_CREATED)
def create_entry(entry: ManualEntry, response: Response) -> dict[str, str]:
    with connect() as conn:
        created = store.insert_entry(conn, entry)
    if not created:
        response.status_code = status.HTTP_200_OK
    return {"id": str(entry.id), "status": "created" if created else "already_exists"}


@app.get("/", response_class=HTMLResponse)
def upload_page() -> str:
    members = "".join(
        f'<option value="{escape(member)}">{escape(member)}</option>'
        for member in sorted(get_settings().members)
    )
    tags = "".join(
        f'<label class="tag"><input type="checkbox" name="tags" value="{escape(category)}">'
        f"{escape(category)}</label>"
        for category in sorted(CATEGORIES)
    )
    page = (STATIC_DIR / "upload.html").read_text(encoding="utf-8")
    return page.replace("{{members}}", members).replace("{{tags}}", tags)


@app.get("/manifest.webmanifest")
def manifest() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json"
    )


@app.get("/icon.svg")
def icon() -> FileResponse:
    return FileResponse(STATIC_DIR / "icon.svg", media_type="image/svg+xml")


@app.get("/base.css")
def base_css() -> FileResponse:
    return FileResponse(STATIC_DIR / "base.css", media_type="text/css")


@app.get("/status", response_class=HTMLResponse)
def status_page() -> str:
    return (STATIC_DIR / "status.html").read_text(encoding="utf-8")


@app.get("/status.json")
def status_data() -> dict:
    return stack_status.build(
        inbox.reports(),
        inbox.queue_counts(),
        inbox.recent_results(stack_status.RECENT_LIMIT),
        get_settings().metabase_url,
    )


def read_upload(file: UploadFile) -> tuple[bytes, str, str]:
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "A fájl nagyobb 20 MB-nál.")
    content_type = inbox.detect_file_type(content)
    if content_type is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Nem támogatott fájltípus.")
    return content, file.filename or "", content_type


@app.post("/uploads", status_code=status.HTTP_201_CREATED)
def create_upload(file: UploadFile, form: Annotated[UploadForm, Form()]) -> dict[str, str]:
    item = inbox.add(form, *read_upload(file))
    return {"id": item["id"], "sha256": item["sha256"]}


@app.post("/uploads/group", status_code=status.HTTP_201_CREATED)
def create_group_upload(
    files: list[UploadFile], form: Annotated[UploadForm, Form()]
) -> dict[str, str]:
    if not MIN_GROUP_PAGES <= len(files) <= MAX_GROUP_PAGES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Egy blokkhoz {MIN_GROUP_PAGES}–{MAX_GROUP_PAGES} kép tartozhat.",
        )
    pages = [read_upload(file) for file in files]
    if any(content_type == inbox.PDF_TYPE for *_, content_type in pages):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "A PDF önmagában egy dokumentum, csak képek fűzhetők össze."
        )
    return {"group_id": inbox.add_group(form, pages)}


@worker_api.get("/items")
def list_inbox_items(
    item_status: Annotated[Literal["new", "closed"], Query(alias="status")] = "new",
) -> dict[str, list[dict]]:
    return {"items": inbox.list_items(item_status)}


@worker_api.get("/items/{item_id}/file")
def download_inbox_file(item_id: UUID) -> FileResponse:
    item = inbox.get_item(item_id)
    path = inbox.file_path(item_id)
    if item is None or not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return FileResponse(path, media_type=item["content_type"])


@worker_api.post("/items/{item_id}/close")
def close_inbox_item(item_id: UUID, outcome: CloseResult | None = None) -> dict[str, str]:
    if not inbox.close_item(item_id, outcome):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return {"id": str(item_id), "status": "closed"}


@worker_api.post("/status/host", status_code=status.HTTP_204_NO_CONTENT)
def report_host(report: HostReport) -> None:
    inbox.save_report("host", report.model_dump_json())


@worker_api.post("/status/worker", status_code=status.HTTP_204_NO_CONTENT)
def report_worker(report: WorkerReport) -> None:
    inbox.save_report("worker", report.model_dump_json())


app.include_router(worker_api)
