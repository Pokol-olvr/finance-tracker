import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    members: frozenset[str]


@lru_cache
def get_settings() -> Settings:
    members = frozenset(filter(None, os.environ["HOUSEHOLD_MEMBERS"].split(",")))
    return Settings(database_url=os.environ["DATABASE_URL"], members=members)
