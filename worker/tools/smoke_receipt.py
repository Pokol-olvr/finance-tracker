"""Kódból rajzolt, kitalált blokkot küld a modellnek, és ellenőrzi a kimenetet. A bronzba nem ír."""

import json
import sys
import time
from io import BytesIO

from app.config import get_settings
from app.extract import ReceiptReader
from app.receipt_parser import parse
from PIL import Image, ImageDraw, ImageFont

LINES = [
    "TESZT ÉLELMISZER KFT",
    "1111 Budapest, Próba utca 1.",
    "ADÓSZÁM: 12345678-2-41",
    "",
    "NYUGTA",
    "",
    "C00 TÚRÓ RUDI 30G           189",
    "C00 MOSÓGÉL 1,1L          2 790",
    "A00 CSIRKEMELL FILÉ 1KG   3 149",
    "C00 ŐSZIBARACK BEFŐTT       899",
    "B00 KENYÉR FEHÉR 500G       599",
    "",
    "ÖSSZESEN:             7 626 Ft",
    "BANKKÁRTYA:           7 626 Ft",
    "",
    "2026.10.29  09:15  NYUGTASZÁM: 0043",
]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
EXPECTED_ITEMS = 5
EXPECTED_TOTAL = 7626
TIME_LIMIT_SECONDS = 60


def draw_receipt() -> bytes:
    font = ImageFont.truetype(FONT, 26)
    image = Image.new("RGB", (620, 40 + 34 * len(LINES)), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(LINES):
        draw.text((20, 20 + index * 34), line, fill="black", font=font)
    output = BytesIO()
    image.rotate(1.2, expand=True, fillcolor="white").save(output, format="PNG")
    return output.getvalue()


def main() -> int:
    settings = get_settings()
    reader = ReceiptReader(settings.ollama_url, settings.ollama_model, settings.ollama_num_thread)
    print(f"Modell: {reader.name} ({reader.version()})")

    started = time.monotonic()
    result = reader.read(draw_receipt(), lambda step: None)
    elapsed = time.monotonic() - started

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Idő: {elapsed:.0f} mp")
    parsed = parse(result.get("ocr_text") or "")
    print(f"Tételek: {len(parsed['items'])}, végösszeg: {parsed['total']}")
    if len(parsed["items"]) != EXPECTED_ITEMS or parsed["total"] != EXPECTED_TOTAL:
        print(f"HIBA: {EXPECTED_ITEMS} tétel és {EXPECTED_TOTAL} Ft a helyes.")
        return 1
    if elapsed > TIME_LIMIT_SECONDS:
        print(f"HIBA: {TIME_LIMIT_SECONDS} másodpercnél tovább tartott.")
        return 1
    print("A mintablokk kiolvasása sikeres.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
