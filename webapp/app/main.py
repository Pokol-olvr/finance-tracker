import secrets
from html import escape
from pathlib import Path as FilePath
from typing import Annotated, Literal
from uuid import UUID

import psycopg
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import inbox, reviews, store
from app import status as stack_status
from app.config import get_settings
from app.schemas import (
    CATEGORIES,
    CloseResult,
    DepositChange,
    DepositReport,
    HostReport,
    ManualEntry,
    NewRule,
    ReviewDecision,
    ReviewPackage,
    ReviewReopen,
    RuleChange,
    UploadForm,
    WorkerReopen,
    WorkerReport,
)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MIN_GROUP_PAGES = 2
MAX_GROUP_PAGES = 5
STATIC_DIR = FilePath(__file__).parent / "static"

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


def member_options() -> str:
    return "".join(
        f'<option value="{escape(member)}">{escape(member)}</option>'
        for member in sorted(get_settings().members)
    )


@app.get("/", response_class=HTMLResponse)
def upload_page() -> str:
    tags = "".join(
        f'<label class="tag"><input type="checkbox" name="tags" value="{escape(category)}">'
        f"{escape(category)}</label>"
        for category in sorted(CATEGORIES)
    )
    page = (STATIC_DIR / "upload.html").read_text(encoding="utf-8")
    return page.replace("{{members}}", member_options()).replace("{{tags}}", tags)


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
        get_settings().reports_url,
    )


@app.get("/riportok")
def reports_link() -> RedirectResponse:
    """A menü a riportfelület címét így nem a statikus oldalakban tárolja."""
    return RedirectResponse(get_settings().reports_url)


@app.get("/rules", response_class=HTMLResponse)
def rules_page() -> str:
    page = (STATIC_DIR / "rules.html").read_text(encoding="utf-8")
    return page.replace("{{members}}", member_options())


@app.get("/rules.json")
def rules_data() -> dict:
    return {"rules": inbox.list_rules(), "categories": sorted(CATEGORIES)}


@app.post("/rules", status_code=status.HTTP_201_CREATED)
def create_rule(rule: NewRule) -> dict[str, str]:
    return {"rule_id": inbox.add_rule(rule)["rule_id"]}


@app.post("/rules/{rule_id}/active", status_code=status.HTTP_204_NO_CONTENT)
def change_rule(rule_id: UUID, change: RuleChange) -> None:
    if not inbox.set_rule_active(rule_id, change.active, change.created_by):
        raise HTTPException(status.HTTP_404_NOT_FOUND)


@app.get("/deposit", response_class=HTMLResponse)
def deposit_page() -> str:
    page = (STATIC_DIR / "deposit.html").read_text(encoding="utf-8")
    return page.replace("{{members}}", member_options())


@app.get("/deposit.json")
def deposit_data() -> dict:
    report = inbox.reports().get("deposit")
    return {
        "balance": report["payload"]["balance"] if report else None,
        "movements": report["payload"]["movements"] if report else [],
        "updated_at": report["received_at"] if report else None,
        "waiting": inbox.waiting_deposit_changes(),
    }


@app.post("/deposit/changes", status_code=status.HTTP_201_CREATED)
def create_deposit_change(change: DepositChange) -> dict[str, str]:
    return {"id": inbox.add_deposit_change(change)}


@app.get("/review", response_class=HTMLResponse)
def review_list_page() -> str:
    return (STATIC_DIR / "review.html").read_text(encoding="utf-8")


@app.get("/review/{group_id}", response_class=HTMLResponse)
def review_page(group_id: UUID) -> str:
    page = (STATIC_DIR / "review_detail.html").read_text(encoding="utf-8")
    return page.replace("{{members}}", member_options())


@app.get("/reviews.json")
def review_list() -> dict:
    return reviews.build_list(inbox.list_reviews())


@app.get("/reviews/{group_id}.json")
def review_data(group_id: UUID) -> dict:
    review = inbox.get_review(group_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return reviews.build_detail(review)


@app.get("/reviews/{group_id}/pages/{page_no}")
def review_file(group_id: UUID, page_no: int) -> FileResponse:
    review = inbox.get_review(group_id)
    path = inbox.review_page_path(group_id, page_no)
    if review is None or not path.exists() or not 1 <= page_no <= len(review["content_types"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return FileResponse(
        path,
        media_type=review["content_types"][page_no - 1],
        content_disposition_type="inline",
        filename=f"{page_no}",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.post("/reviews/{group_id}/decision", status_code=status.HTTP_201_CREATED)
def create_review_decision(group_id: UUID, decision: ReviewDecision) -> dict[str, str | None]:
    try:
        saved = inbox.decide(group_id, decision)
    except inbox.ReviewConflict as conflict:
        raise HTTPException(status.HTTP_409_CONFLICT, str(conflict)) from conflict
    if saved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return {"id": saved, "next": inbox.next_open_review()}


@app.post("/reviews/{group_id}/reopen", status_code=status.HTTP_201_CREATED)
def reopen_review(group_id: UUID, request: ReviewReopen) -> dict[str, str]:
    try:
        reopened = inbox.reopen(group_id, request.decided_by)
    except inbox.ReviewConflict as conflict:
        raise HTTPException(status.HTTP_409_CONFLICT, str(conflict)) from conflict
    if not reopened:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return {"status": "reopened"}


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
            f"Egy dokumentumhoz {MIN_GROUP_PAGES}–{MAX_GROUP_PAGES} fájl tartozhat.",
        )
    return {"group_id": inbox.add_group(form, [read_upload(file) for file in files])}


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


@worker_api.get("/reviews")
def list_known_reviews() -> dict[str, list[dict]]:
    """A worker körönként hívja, ezért itt fut a régi csomagok takarítása is."""
    inbox.purge_reviews()
    return {"reviews": inbox.known_reviews()}


@worker_api.put("/reviews/{group_id}/pages/{page_no}", status_code=status.HTTP_204_NO_CONTENT)
async def put_review_page(
    group_id: UUID,
    page_no: Annotated[int, Path(ge=1, le=inbox.MAX_REVIEW_PAGES)],
    request: Request,
) -> None:
    content = await request.body()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "A fájl nagyobb 20 MB-nál.")
    if inbox.detect_file_type(content) is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Nem támogatott fájltípus.")
    inbox.save_review_page(group_id, page_no, content)


@worker_api.put("/reviews/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def put_review(group_id: UUID, package: ReviewPackage) -> None:
    inbox.save_review(group_id, package)


@worker_api.post("/reviews/{group_id}/reopen", status_code=status.HTTP_204_NO_CONTENT)
def reopen_review_from_worker(group_id: UUID, request: WorkerReopen) -> None:
    inbox.reopen_from_worker(group_id, request)


@worker_api.get("/events")
def list_open_events() -> dict[str, list[dict]]:
    return {"events": inbox.open_events()}


@worker_api.post("/events/{event_id}/close", status_code=status.HTTP_204_NO_CONTENT)
def close_outbox_event(event_id: UUID) -> None:
    if not inbox.close_event(event_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND)


@worker_api.post("/status/deposit", status_code=status.HTTP_204_NO_CONTENT)
def report_deposit(report: DepositReport) -> None:
    inbox.save_report("deposit", report.model_dump_json())


@worker_api.get("/decisions")
def list_open_decisions() -> dict[str, list[dict]]:
    return {"decisions": inbox.open_decisions()}


@worker_api.post("/decisions/{decision_id}/close", status_code=status.HTTP_204_NO_CONTENT)
def close_review_decision(decision_id: UUID) -> None:
    if not inbox.close_decision(decision_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND)


@worker_api.post("/status/host", status_code=status.HTTP_204_NO_CONTENT)
def report_host(report: HostReport) -> None:
    inbox.save_report("host", report.model_dump_json())


@worker_api.post("/status/worker", status_code=status.HTTP_204_NO_CONTENT)
def report_worker(report: WorkerReport) -> None:
    inbox.save_report("worker", report.model_dump_json())


app.include_router(worker_api)
