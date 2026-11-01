"""A worker állapotjelentése. Külön szálon fut, mert a modell hívása percekig blokkol."""

import logging
import threading
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.extract import full_model_name

log = logging.getLogger("worker")

# A Compose healthcheckje ennek a fájlnak a korát nézi.
HEARTBEAT_FILE = Path("/tmp/worker-heartbeat")
REPORT_SECONDS = 15


class StatusReporter:
    def __init__(
        self,
        inbox_url: str,
        token: str,
        ollama_url: str,
        model: str,
        transport: httpx.BaseTransport | None = None,
        heartbeat_file: Path = HEARTBEAT_FILE,
    ):
        self.client = httpx.Client(
            base_url=inbox_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
            transport=transport,
        )
        self.ollama = httpx.Client(base_url=ollama_url, timeout=5, transport=transport)
        self.model = model
        self.heartbeat_file = heartbeat_file
        self.current = ("idle", datetime.now(UTC))
        self.changed = threading.Event()

    def step(self, name: str) -> None:
        """Csak feljegyzi a lépést, a küldés a szálé, így a feldolgozást semmi nem tartja fel."""
        if name != self.current[0]:
            self.current = (name, datetime.now(UTC))
            self.changed.set()

    def ollama_state(self) -> dict:
        state = {
            "ollama_reachable": False,
            "model_name": self.model,
            "model_version": None,
            "model_downloaded": False,
            "model_loaded": False,
            "model_memory_bytes": 0,
        }
        try:
            downloaded = self.ollama.get("/api/tags")
            downloaded.raise_for_status()
            running = self.ollama.get("/api/ps")
            running.raise_for_status()
        except httpx.HTTPError:
            return state

        wanted = full_model_name(self.model)
        state["ollama_reachable"] = True
        for model in downloaded.json()["models"]:
            if model["name"] == wanted:
                state["model_downloaded"] = True
                state["model_version"] = model["digest"]
        for model in running.json()["models"]:
            if model["name"] == wanted:
                state["model_loaded"] = True
                state["model_memory_bytes"] = model["size"]
        return state

    def send(self) -> None:
        name, started = self.current
        report = {"step": name, "step_started_at": started.isoformat()} | self.ollama_state()
        self.client.post("/inbox/status/worker", json=report).raise_for_status()

    def report_once(self) -> None:
        """A webapp kiesése nem hiba a feldolgozásnak, a következő kör újra próbálja."""
        try:
            self.send()
        except (httpx.HTTPError, KeyError, ValueError) as error:
            log.warning("Az állapotjelentés nem ment át: %s", error)
        self.heartbeat_file.touch()

    def loop(self) -> None:
        while True:
            self.changed.clear()
            self.report_once()
            self.changed.wait(REPORT_SECONDS)

    def start(self) -> None:
        threading.Thread(target=self.loop, name="status", daemon=True).start()
