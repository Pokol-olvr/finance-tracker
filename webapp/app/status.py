"""A /status oldal adatai. Csak jelentésekből és a postaládából dolgozik, a régi jelentés nem zöld."""

from datetime import UTC, datetime

STALE_SECONDS = 60
RECENT_LIMIT = 10

OK = "ok"
BUSY = "busy"
WAITING = "waiting"
ERROR = "error"
STALE = "stale"

STEP_LABELS = {
    "idle": "Nincs feldolgozás",
    "download": "Letöltés a postaládából",
    "storage": "Mentés a Garage-ba",
    "read_text": "Szöveges olvasat",
    "parse": "Feldolgozás",
    "close": "Lezárás",
}
RESULT_LABELS = {
    "ok": "rendben",
    "review": "ellenőrzés kell",
    "unparsed": "nem feldolgozható",
    "unreadable": "olvashatatlan fájl",
    "duplicate": "már megvolt",
    "reopened": "újranyitva",
}
NO_DATA = "Nincs friss adat"


def age_seconds(report: dict | None, now: datetime) -> float | None:
    if report is None:
        return None
    return (now - datetime.fromisoformat(report["received_at"])).total_seconds()


def fresh_payload(report: dict | None, now: datetime) -> dict | None:
    age = age_seconds(report, now)
    return report["payload"] if age is not None and age <= STALE_SECONDS else None


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def format_gigabytes(value: int) -> str:
    return f"{value / 1e9:.1f} GB".replace(".", ",")


def format_decimal(value: float, unit: str) -> str:
    return f"{value:.1f}".replace(".", ",") + f" {unit}"


def processor_share(worker: dict) -> str:
    """Az Ollama `ollama ps` PROCESSOR oszlopa: mennyi van a modellből a GPU memóriájában."""
    size, vram = worker["model_memory_bytes"], worker.get("model_vram_bytes", 0)
    if not size or not vram:
        return "CPU"
    if vram >= size:
        return "GPU"
    return f"{round(vram / size * 100)}% GPU"


def card(key: str, title: str, state: str, summary: str, facts: list | None = None) -> dict:
    return {"key": key, "title": title, "state": state, "summary": summary, "facts": facts or []}


def fact(label: str, value: str) -> dict:
    return {"label": label, "value": value}


def time_fact(label: str, value: str | None) -> dict:
    return {"label": label, "time": value} if value else fact(label, "nincs adat")


def service_state(host: dict | None, name: str) -> tuple[str, str]:
    """A kártya állapota a `compose ps` alapján; ami nincs a listában, az nem fut."""
    if host is None:
        return STALE, NO_DATA
    service = next((row for row in host["services"] if row["name"] == name), None)
    if service is None or service["state"] != "running":
        return ERROR, "Nem fut"
    if service["health"] == "unhealthy":
        return ERROR, "Nem egészséges"
    if service["health"] == "starting":
        return BUSY, "Indul"
    return OK, "Egészséges" if service["health"] == "healthy" else "Fut"


def upload_card(host: dict | None, queue: dict) -> dict:
    state, summary = service_state(host, "webapp")
    facts = [
        fact("Várakozik", format_number(queue.get("new", 0))),
        fact("Lezárt", format_number(queue.get("closed", 0))),
        fact("Ellenőrzésre vár", format_number(queue.get("review", 0))),
    ]
    result = card("upload", "Feltöltés", state, summary, facts)
    return result | {"link": {"label": "Ellenőrzés megnyitása", "url": "/review"}}


def worker_card(host: dict | None, worker: dict | None) -> dict:
    state, summary = service_state(host, "worker")
    if state == ERROR:
        return card("worker", "Worker", state, summary)
    if worker is None:
        return card("worker", "Worker", STALE, NO_DATA)
    if worker["step"] == "idle":
        return card("worker", "Worker", state, summary, [fact("Lépés", STEP_LABELS["idle"])])
    return card("worker", "Worker", BUSY, STEP_LABELS[worker["step"]])


def ollama_card(host: dict | None, worker: dict | None) -> dict:
    state, summary = service_state(host, "ollama")
    if state == ERROR:
        return card("ollama", "Ollama", state, summary)
    if worker is None:
        return card("ollama", "Ollama", STALE, NO_DATA)
    if not worker["ollama_reachable"]:
        return card("ollama", "Ollama", ERROR, "A worker nem éri el")
    if not worker["model_downloaded"]:
        return card("ollama", "Ollama", ERROR, "A modell nincs letöltve")
    loaded = worker["model_loaded"]
    size = " · ".join(
        part for part in (worker.get("model_parameters"), worker.get("model_quantization")) if part
    )
    facts = [
        fact("Modell", worker["model_name"] + (f" ({size})" if size else "")),
        fact("Azonosító", (worker["model_version"] or "")[:12]),
    ]
    if loaded:
        facts.append(
            fact(
                "Fut",
                f"{processor_share(worker)} · {format_gigabytes(worker['model_memory_bytes'])}",
            )
        )
    else:
        facts.append(fact("Betöltve", "nem"))
    facts.extend(read_facts(worker))
    # GPU-n a modell a futások között is betöltve marad, ezért a betöltés még nem munka.
    if worker["step"] == "read_text":
        return card("ollama", "Ollama", BUSY, "A modell fut", facts)
    if loaded:
        return card("ollama", "Ollama", state, "A modell betöltve", facts)
    return card("ollama", "Ollama", state, summary, facts)


def read_facts(worker: dict) -> list[dict]:
    """Az utolsó olvasás és az utolsó olvasások átlaga, idővel és token/s sebességgel."""
    facts = []
    last = worker.get("last_read")
    if last:
        speed = last.get("tokens_per_second")
        value = format_decimal(last["seconds"], "s")
        facts.append(fact("Utolsó olvasás", value + (f" · {round(speed)} token/s" if speed else "")))
    recent = worker.get("recent_reads")
    if recent:
        speed = recent.get("average_tokens_per_second")
        value = format_decimal(recent["average_seconds"], "s")
        facts.append(
            fact(
                f"Átlag ({recent['count']} olvasás)",
                value + (f" · {round(speed)} token/s" if speed else ""),
            )
        )
    return facts


def meter(label: str, percent: float | None, detail: str | None = None) -> dict:
    return {"label": label, "percent": None if percent is None else round(percent, 1), "detail": detail}


def share(used: int, total: int) -> float | None:
    return used / total * 100 if total else None


def resources_card(host: dict | None) -> dict:
    """A gép erőforrásai sávokkal: magonkénti CPU, memória, és ha van, GPU.

    A jelentés 15 másodpercenkénti pillanatkép, a CPU egy másodperces mintából számol.
    """
    if host is None:
        return card("resources", "Erőforrások", STALE, NO_DATA) | {"wide": True}
    groups = []
    cpu = host.get("cpu")
    if cpu:
        groups.append(
            {
                "title": "CPU",
                "summary": " · ".join(
                    part
                    for part in (f"{round(cpu['percent'])}%", f"{len(cpu['cores'])} szál", cpu.get("model"))
                    if part
                ),
                "meters": [meter(f"#{index}", value) for index, value in enumerate(cpu["cores"])],
                "cores": True,
            }
        )
    used_memory = host["memory_total_bytes"] - host["memory_available_bytes"]
    memory = [
        meter(
            "RAM",
            share(used_memory, host["memory_total_bytes"]),
            f"{format_gigabytes(used_memory)} / {format_gigabytes(host['memory_total_bytes'])}",
        )
    ]
    if host.get("swap_total_bytes"):
        memory.append(
            meter(
                "Swap",
                share(host["swap_used_bytes"] or 0, host["swap_total_bytes"]),
                f"{format_gigabytes(host['swap_used_bytes'] or 0)} / "
                f"{format_gigabytes(host['swap_total_bytes'])}",
            )
        )
    groups.append({"title": "Memória", "summary": "", "meters": memory, "cores": False})
    gpu = host.get("gpu")
    if gpu:
        extra = [
            f"{round(gpu['temperature_c'])} °C" if gpu.get("temperature_c") is not None else None,
            f"{round(gpu['power_w'])} W" if gpu.get("power_w") is not None else None,
        ]
        groups.append(
            {
                "title": "GPU",
                "summary": " · ".join(part for part in (gpu["name"], *extra) if part),
                "meters": [
                    meter("Kihasználtság", gpu.get("utilization_percent")),
                    meter(
                        "Videomemória",
                        share(gpu["memory_used_bytes"], gpu["memory_total_bytes"]),
                        f"{format_gigabytes(gpu['memory_used_bytes'])} / "
                        f"{format_gigabytes(gpu['memory_total_bytes'])}",
                    ),
                ],
                "cores": False,
            }
        )
    summary = f"Terhelés {host['load']:.2f}".replace(".", ",")
    return card("resources", "Erőforrások", OK, summary) | {"wide": True, "groups": groups}


def garage_card(host: dict | None) -> dict:
    state, summary = service_state(host, "garage")
    if state != OK or host["garage_objects"] is None:
        return card("garage", "Garage", state, summary)
    facts = [
        fact("Objektumok", format_number(host["garage_objects"])),
        fact("Méret", (host["garage_size"] or "nincs adat").replace(".", ",")),
    ]
    return card("garage", "Garage", state, summary, facts)


def postgres_card(host: dict | None) -> dict:
    state, summary = service_state(host, "postgres")
    if state != OK or not host["row_counts"]:
        return card("postgres", "Postgres", state, summary)
    facts = [
        fact(
            label,
            format_number(
                sum(rows for table, rows in host["row_counts"].items() if table.startswith(schema))
            )
            + " sor",
        )
        for label, schema in (("Bronz", "bronze."), ("Silver", "silver."), ("Gold", "gold."))
    ]
    return card("postgres", "Postgres", state, summary, facts)


def reports_card(host: dict | None, reports_url: str) -> dict:
    state, summary = service_state(host, "reports")
    result = card("reports", "Riportok", state, summary)
    return result | {"link": {"label": "Riportok megnyitása", "url": reports_url}}


def job_card(host: dict | None, name: str, title: str) -> dict:
    if host is None:
        return card(name, title, STALE, NO_DATA)
    job = next((row for row in host["jobs"] if row["name"] == name), None)
    if job is None:
        return card(name, title, STALE, "Nincs időzítő")
    facts = [time_fact("Utolsó futás", job["last_run"]), time_fact("Következő", job["next_run"])]
    if job["active"] == "activating":
        return card(name, title, BUSY, "Most fut", facts)
    if job["last_run"] is None:
        return card(name, title, STALE, "Még nem futott", facts)
    if job["result"] != "success":
        return card(name, title, ERROR, "Hibás futás", facts)
    return card(name, title, OK, "Sikeres", facts)


def machine_card(host: dict | None) -> dict:
    if host is None:
        return card("machine", "Gép", STALE, NO_DATA)
    facts = [
        fact(
            "Szabad lemez",
            f"{format_gigabytes(host['disk_free_bytes'])} / "
            f"{format_gigabytes(host['disk_total_bytes'])}",
        ),
        fact(
            "Szabad memória",
            f"{format_gigabytes(host['memory_available_bytes'])} / "
            f"{format_gigabytes(host['memory_total_bytes'])}",
        ),
        fact("Terhelés", f"{host['load']:.2f}".replace(".", ",")),
    ]
    return card("machine", "Gép", OK, "Jelentkezik", facts)


def processing_state(worker: dict | None, queue: dict, now: datetime) -> dict | None:
    if worker is None:
        return None
    step = worker["step"]
    open_items = queue.get("new", 0)
    if step == "idle":
        return {"step": step, "label": STEP_LABELS[step], "seconds": None, "waiting": open_items}
    started = datetime.fromisoformat(worker["step_started_at"])
    return {
        "step": step,
        "label": STEP_LABELS[step],
        "seconds": max(0, round((now - started).total_seconds())),
        "waiting": max(0, open_items - 1),
    }


def overall_state(cards: list[dict], host: dict | None, processing: dict | None) -> dict:
    failed = [item["title"] for item in cards if item["state"] == ERROR]
    if failed:
        return {"state": ERROR, "label": "Hiba: " + ", ".join(failed)}
    if host is None or processing is None:
        return {"state": STALE, "label": NO_DATA}
    if processing["step"] != "idle":
        return {"state": BUSY, "label": "Feldolgozás fut"}
    if processing["waiting"]:
        return {"state": WAITING, "label": "Várakozik"}
    return {"state": OK, "label": "Minden rendben"}


def build(
    reports: dict, queue: dict, recent: list[dict], reports_url: str, now: datetime | None = None
) -> dict:
    now = now or datetime.now(UTC)
    host = fresh_payload(reports.get("host"), now)
    worker = fresh_payload(reports.get("worker"), now)
    cards = [
        upload_card(host, queue),
        worker_card(host, worker),
        ollama_card(host, worker),
        garage_card(host),
        postgres_card(host),
        reports_card(host, reports_url),
        job_card(host, "dbt", "dbt"),
        job_card(host, "backup", "Mentés"),
        machine_card(host),
        resources_card(host),
    ]
    processing = processing_state(worker, queue, now)
    ages = [age_seconds(reports.get(source), now) for source in ("host", "worker")]
    known_ages = [age for age in ages if age is not None]
    return {
        "overall": overall_state(cards, host, processing),
        "report_age_seconds": round(max(known_ages)) if known_ages else None,
        "processing": processing,
        "cards": cards,
        "recent": [
            {
                "finished_at": row["finished_at"],
                "seconds": row["seconds"],
                "items": row["items"],
                "result": RESULT_LABELS[row["result"]],
            }
            for row in recent
        ],
    }
