import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    inbox_url: str
    worker_token: str
    poll_seconds: int
    garage_endpoint: str
    garage_access_key: str
    garage_secret_key: str
    ollama_url: str
    ollama_model: str
    ollama_num_thread: int


def get_settings() -> Settings:
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        inbox_url=os.environ["INBOX_URL"],
        worker_token=os.environ["WORKER_API_TOKEN"],
        poll_seconds=int(os.environ["WORKER_POLL_SECONDS"]),
        garage_endpoint=os.environ["GARAGE_ENDPOINT"],
        garage_access_key=os.environ["GARAGE_ACCESS_KEY"],
        garage_secret_key=os.environ["GARAGE_SECRET_KEY"],
        ollama_url=os.environ["OLLAMA_URL"],
        ollama_model=os.environ["OLLAMA_MODEL"],
        ollama_num_thread=int(os.environ["OLLAMA_NUM_THREAD"]),
    )
