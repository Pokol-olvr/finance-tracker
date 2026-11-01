"""A repón kívüli mappa képeit és PDF-jeit olvassa ki, a Garage-hoz és a bronzhoz nem nyúl.

Használat: python -m tools.read_folder /be /ki
A kimenet fájlonként a szöveg és a feldolgozott adat; saját adat is lehet, a repóba nem kerülhet.
"""

import json
import sys
from collections import Counter
from pathlib import Path

from app import pdf
from app.config import get_settings
from app.document_parser import parse_document
from app.extract import ReceiptReader
from app.receipt_checks import run_checks, status_of

SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".pdf"}


def main() -> int:
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    settings = get_settings()
    reader = ReceiptReader(settings.ollama_url, settings.ollama_model, settings.ollama_num_thread)
    files = sorted(path for path in source.iterdir() if path.suffix.lower() in SUFFIXES)

    counts: Counter[str] = Counter()
    for position, file in enumerate(files, 1):
        text_file = target / f"{file.stem}.txt"
        # A már kiolvasott fájlt nem olvassa újra, így a futás megszakítás után folytatható.
        if not text_file.exists():
            content = file.read_bytes()
            active = pdf.reader_for(content, reader) if file.suffix.lower() == ".pdf" else reader
            result = active.read(content, lambda step: None)
            text_file.write_text(result.get("ocr_text", ""), encoding="utf-8")
        parsed = parse_document([text_file.read_text(encoding="utf-8")])
        checks = run_checks(parsed, None, False)
        status = status_of(parsed, checks)
        counts[status] += 1
        report = {"status": status, "parsed": parsed, "checks": checks}
        (target / f"{file.stem}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{position}/{len(files)} {status}", flush=True)
    print(dict(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
