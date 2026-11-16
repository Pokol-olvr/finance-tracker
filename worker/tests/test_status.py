import json

import httpx
from app.status import StatusReporter


def reporter_with(handler, tmp_path) -> StatusReporter:
    return StatusReporter(
        "http://webapp:8000",
        "titok",
        "http://ollama:11434",
        "glm-ocr",
        transport=httpx.MockTransport(handler),
        heartbeat_file=tmp_path / "heartbeat",
    )


def stack(sent: list, loaded: bool = False):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "glm-ocr:latest", "digest": "abc"}]}
            )
        if request.url.path == "/api/ps":
            running = [{"name": "glm-ocr:latest", "size": 5_000_000_000}] if loaded else []
            return httpx.Response(200, json={"models": running})
        sent.append(request)
        return httpx.Response(204)

    return handler


def test_report_contains_step_and_model_state(tmp_path):
    sent = []
    reporter = reporter_with(stack(sent, loaded=True), tmp_path)
    reporter.step("read_text")

    reporter.report_once()

    assert sent[0].url.path == "/inbox/status/worker"
    assert sent[0].headers["authorization"] == "Bearer titok"
    report = json.loads(sent[0].content)
    assert report["step"] == "read_text"
    assert report["ollama_reachable"] is True
    assert report["model_version"] == "abc"
    assert report["model_downloaded"] is True
    assert report["model_loaded"] is True
    assert report["model_memory_bytes"] == 5_000_000_000


def test_idle_model_is_not_loaded(tmp_path):
    state = reporter_with(stack([]), tmp_path).ollama_state()

    assert state["model_loaded"] is False
    assert state["model_memory_bytes"] == 0


def test_missing_model_is_reported(tmp_path):
    def handler(_request):
        return httpx.Response(200, json={"models": []})

    state = reporter_with(handler, tmp_path).ollama_state()

    assert state["ollama_reachable"] is True
    assert state["model_downloaded"] is False


def test_unreachable_ollama_does_not_stop_the_report(tmp_path):
    sent = []

    def handler(request):
        if request.url.path.startswith("/api/"):
            raise httpx.ConnectError("az Ollama nem érhető el")
        sent.append(request)
        return httpx.Response(204)

    reporter_with(handler, tmp_path).report_once()

    assert json.loads(sent[0].content)["ollama_reachable"] is False


def test_failed_report_is_swallowed_and_heartbeat_still_updates(tmp_path):
    def handler(_request):
        raise httpx.ConnectError("a webapp nem érhető el")

    reporter_with(handler, tmp_path).report_once()

    assert (tmp_path / "heartbeat").exists()


def test_step_change_wakes_the_sender_but_same_step_does_not(tmp_path):
    reporter = reporter_with(stack([]), tmp_path)

    reporter.step("idle")
    assert not reporter.changed.is_set()

    started = reporter.current[1]
    reporter.step("download")
    assert reporter.changed.is_set()
    assert reporter.current[1] >= started


class FinishedReader:
    def __init__(self):
        self.last_stats = {
            "finished_at": "2026-12-01T12:00:00+00:00",
            "seconds": 2.2,
            "tokens_per_second": 321.2,
        }


def test_report_contains_video_memory_and_last_read(tmp_path):
    sent = []

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "glm-ocr:latest", "digest": "abc"}]})
        if request.url.path == "/api/ps":
            running = [{"name": "glm-ocr:latest", "size": 2_000_000_000, "size_vram": 2_000_000_000}]
            return httpx.Response(200, json={"models": running})
        sent.append(request)
        return httpx.Response(204)

    reporter = StatusReporter(
        "http://webapp:8000",
        "titok",
        "http://ollama:11434",
        "glm-ocr",
        transport=httpx.MockTransport(handler),
        heartbeat_file=tmp_path / "heartbeat",
        reader=FinishedReader(),
    )
    reporter.report_once()

    report = json.loads(sent[0].content)
    assert report["model_vram_bytes"] == 2_000_000_000
    assert report["last_read"]["tokens_per_second"] == 321.2


def test_report_without_reader_has_no_last_read(tmp_path):
    sent = []
    reporter_with(stack(sent), tmp_path).report_once()

    assert json.loads(sent[0].content)["last_read"] is None
