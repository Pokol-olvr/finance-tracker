import psycopg
from fastapi import FastAPI, Response, status

from app import store
from app.config import get_settings
from app.schemas import ManualEntry

app = FastAPI(title="Pénzügyi nyomkövető")


def connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url)


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
