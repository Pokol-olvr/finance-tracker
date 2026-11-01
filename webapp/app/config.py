import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    members: frozenset[str]
    inbox_dir: Path
    worker_token: str
    reports_url: str


@lru_cache
def get_settings() -> Settings:
    members = frozenset(filter(None, os.environ["HOUSEHOLD_MEMBERS"].split(",")))
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        members=members,
        inbox_dir=Path(os.environ["INBOX_DIR"]),
        worker_token=os.environ["WORKER_API_TOKEN"],
        reports_url=os.environ["REPORTS_URL"],
    )
