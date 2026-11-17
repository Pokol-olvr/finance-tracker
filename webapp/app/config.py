import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # A Pi-n nincs adatbázis: a webapp ott csak postaláda, minden a kimenő soron megy (ADR 0006).
    database_url: str | None
    members: frozenset[str]
    inbox_dir: Path
    worker_token: str
    reports_url: str
    # Az Authelia ebben a fejlécben adja a belépett felhasználót; üresen nincs belépés (helyi futás).
    auth_header: str | None = None


@lru_cache
def get_settings() -> Settings:
    members = frozenset(filter(None, os.environ["HOUSEHOLD_MEMBERS"].split(",")))
    return Settings(
        database_url=os.environ.get("DATABASE_URL") or None,
        members=members,
        inbox_dir=Path(os.environ["INBOX_DIR"]),
        worker_token=os.environ["WORKER_API_TOKEN"],
        reports_url=os.environ["REPORTS_URL"],
        auth_header=os.environ.get("AUTH_HEADER") or None,
    )
