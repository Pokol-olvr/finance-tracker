"""Kitalált bejegyzések; ugyanaz a hónap mindig ugyanazokat az id-kat kapja, így újrafuttatható."""

import json
import os
import random
import urllib.request
import uuid
from datetime import date

MONTHS = 6
NAMESPACE = uuid.UUID("7d1b6a44-3f0e-4c55-9a51-2b6ad0a5c111")

SHARED_EXPENSES = [
    ("lakbér", 1, 210_000, 210_000),
    ("élelmiszer", 4, 14_000, 38_000),
    ("háztartás", 2, 6_000, 24_000),
    ("közlekedés", 1, 18_000, 26_000),
]
PERSONAL_EXPENSES = [
    ("szórakozás", 2, 5_000, 30_000),
    ("egészség", 1, 3_000, 16_000),
]


def month_starts(today: date) -> list[date]:
    index = today.year * 12 + today.month - 1
    return [date(i // 12, i % 12 + 1, 1) for i in range(index - MONTHS + 1, index + 1)]


def entries_for(month: date, today: date, members: list[str]) -> list[dict]:
    rng = random.Random(month.isoformat())

    def entry(kind: str, amount: int, payer: str, category: str | None = None) -> dict:
        day = rng.randint(1, 28)
        if month.year == today.year and month.month == today.month:
            day = min(day, today.day)
        return {
            "kind": kind,
            "amount": str(amount),
            "occurred_on": month.replace(day=day).isoformat(),
            "entered_by": "mock",
            "purchased_by": rng.choice(members) if payer == "shared" else payer,
            "payer": payer,
            "tags": [category] if category else [],
            "note": "mock",
        }

    entries = []
    for member, salary in zip(members, (640_000, 520_000)):
        entries.append(entry("income", salary + rng.randint(-20_000, 20_000), member))
        entries.append(entry("transfer", 220_000, member))
    for category, count, low, high in SHARED_EXPENSES:
        entries += [entry("expense", rng.randint(low, high), "shared", category) for _ in range(count)]
    for member in members:
        for category, count, low, high in PERSONAL_EXPENSES:
            entries += [entry("expense", rng.randint(low, high), member, category) for _ in range(count)]

    for index, item in enumerate(entries):
        item["id"] = str(uuid.uuid5(NAMESPACE, f"{month.isoformat()}:{index}"))
    return entries


def post(url: str, entry: dict) -> str:
    request = urllib.request.Request(
        url, json.dumps(entry).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)["status"]


def main() -> None:
    url = f"http://127.0.0.1:{os.environ.get('WEBAPP_PORT') or 8000}/entries"
    members = (os.environ.get("HOUSEHOLD_MEMBERS") or "person_a,person_b").split(",")
    today = date.today()
    statuses = [
        post(url, entry)
        for month in month_starts(today)
        for entry in entries_for(month, today, members)
    ]
    print(f"Mock bejegyzések: {statuses.count('created')} új, {statuses.count('already_exists')} már megvolt.")


if __name__ == "__main__":
    main()
