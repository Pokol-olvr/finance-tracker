"""A PDF olvasása: a szövegréteg közvetlenül, a szkennelt lapok a modellen át."""

from collections.abc import Callable
from itertools import pairwise

import pypdfium2 as pdfium

from app.extract import MAX_SIDE, ReceiptReader, to_jpeg

CONTENT_TYPE = "application/pdf"
READER_NAME = "pdfium"
# Egy szkennelt lapon legfeljebb pár szó van a szövegrétegben, pl. a szkenner neve.
MIN_TEXT_CHARS = 50
# A hibás betűkészletű PDF szövegrétege csupa írásjel, abból a modell olvasata jobb.
MIN_READABLE_SHARE = 0.5
# Lapjaként kb. másfél perc, ezért egy szkennelt PDF nem foglalhatja le órákra a workert.
MAX_SCANNED_PAGES = 5


# Egy soron belül a dobozok közötti hézag a magassághoz mérve: ennél nagyobb hézag új cellát
# (pl. másik oszlopot) jelent, a cellán belüli szóközöket a pdfium adja. A betűnként tárolt
# szövegben (pl. a Stripe-számlák) a dobozok betűk, köztük nincs szóköz.
CELL_GAP = 1.0
# Szöveg nélküli összerakásnál (tesztek) ennél nagyobb hézag szóköz.
WORD_GAP = 0.15
# Ennyi függőleges átfedés kell egy sorhoz; a vessző és a „g” lejjebb lóg, mégis abba a sorba tartozik.
ROW_OVERLAP = 0.3
# A sorképzés változása új olvasatot ad, ezért a bronzban a könyvtár verziója mellett ez is szerepel.
LAYOUT_VERSION = "3"

Box = tuple[float, float, float, float, str]
TextOf = Callable[[float, float, float, float], str]


def same_row(first: Box, box: Box) -> bool:
    overlap = min(first[3], box[3]) - max(first[2], box[2])
    height = max(min(first[3] - first[2], box[3] - box[2]), 0.1)
    return overlap > ROW_OVERLAP * height


def height_of(previous: Box, box: Box) -> float:
    return max(previous[3] - previous[2], box[3] - box[2])


def cells_of(row: list[Box]) -> list[list[Box]]:
    cells = [[row[0]]]
    for previous, box in pairwise(row):
        if box[0] - previous[1] > CELL_GAP * height_of(previous, box):
            cells.append([box])
        else:
            cells[-1].append(box)
    return cells


def joined(cell: list[Box]) -> str:
    text = cell[0][4]
    for previous, box in pairwise(cell):
        gap = box[0] - previous[1]
        text += (" " if gap > WORD_GAP * height_of(previous, box) else "") + box[4]
    return text


def cell_text(cell: list[Box], text_of: TextOf | None) -> str:
    if text_of is None:
        return joined(cell)
    left, right = min(box[0] for box in cell), max(box[1] for box in cell)
    bottom, top = min(box[2] for box in cell), max(box[3] for box in cell)
    return " ".join(text_of(left, bottom, right, top).split()) or joined(cell)


def sorted_rows(boxes: list[Box], text_of: TextOf | None = None) -> list[str]:
    """Szövegdobozokból (bal, jobb, alsó, felső, szöveg) látható sorok: a fájl belső sorrendje
    oszloponként is haladhat, ezért a sorokat és a cellákat a helyzetük adja."""
    rows: list[list[Box]] = []
    for box in sorted(boxes, key=lambda box: -box[3]):
        if rows and same_row(rows[-1][0], box):
            rows[-1].append(box)
        else:
            rows.append([box])
    return [
        " ".join(cell_text(cell, text_of) for cell in cells_of(sorted(row))) for row in rows
    ]


def page_lines(page: pdfium.PdfPage) -> list[str]:
    text_page = page.get_textpage()
    boxes = []
    for index in range(text_page.count_rects()):
        left, bottom, right, top = text_page.get_rect(index)
        text = text_page.get_text_bounded(left, bottom, right, top).strip()
        if text:
            boxes.append((left, right, bottom, top, " ".join(text.split())))
    return sorted_rows(boxes, text_page.get_text_bounded)


def text_layer(content: bytes) -> str:
    with pdfium.PdfDocument(content) as document:
        return "\n".join(line for page in document for line in page_lines(page))


def is_readable(text: str) -> bool:
    visible = [char for char in text if not char.isspace()]
    return (
        len(visible) >= MIN_TEXT_CHARS
        and sum(char.isalnum() for char in visible) >= MIN_READABLE_SHARE * len(visible)
    )


def render_pages(content: bytes, max_side: int = MAX_SIDE) -> list[bytes]:
    """A lapok a modell bemenetéhez illő méretben; a kis oldalméret így nem ront a felbontáson."""
    with pdfium.PdfDocument(content) as document:
        images = []
        for index in range(min(len(document), MAX_SCANNED_PAGES)):
            page = document[index]
            scale = max_side / max(page.get_size())
            images.append(to_jpeg(page.render(scale=scale).to_pil()))
        return images


class TextLayerReading:
    """A szövegréteghez nem kell modell, ezért a bronzban a könyvtár neve és verziója szerepel."""

    name = READER_NAME

    def __init__(self, payload: dict):
        self.payload = payload

    def version(self) -> str:
        return f"{pdfium.PYPDFIUM_INFO} sorok{LAYOUT_VERSION}"

    def read(self, content: bytes, report: Callable[[str], None]) -> dict:
        report("read_text")
        return self.payload


class ScannedPdf:
    """Szövegréteg nélkül a lapok képként mennek a modellhez, egy dokumentumként tárolva."""

    def __init__(self, model: ReceiptReader):
        self.model = model
        self.name = model.name

    def version(self) -> str:
        return self.model.version()

    def read(self, content: bytes, report: Callable[[str], None]) -> dict:
        try:
            pages = render_pages(content, self.model.max_side)
        except pdfium.PdfiumError as error:
            return {"error": f"A PDF nem olvasható: {error}"}
        results = [self.model.read_image(page, report) for page in pages]
        # Lapok összege; a token/s a lapok átlaga, mert a lapok külön modellfutások.
        speeds = [result["tokens_per_second"] for result in results if result.get("tokens_per_second")]
        totals = {
            key: round(sum(result.get(key) or 0 for result in results), 1)
            for key in ("seconds", "load_seconds", "image_seconds", "text_seconds")
        }
        return {
            "ocr_text": "\n".join(result["ocr_text"] for result in results),
            "done_reason": results[-1].get("done_reason") if results else None,
            **totals,
            "tokens": sum(result.get("tokens") or 0 for result in results),
            "tokens_per_second": round(sum(speeds) / len(speeds), 1) if speeds else None,
            "max_side": self.model.max_side,
            # A határhoz a legrosszabb lap számít.
            **{
                key: max((result.get(key) or 0 for result in results), default=0) or None
                for key in ("prompt_tokens", "num_ctx", "attempts")
            },
        }


def reader_for(content: bytes, model: ReceiptReader) -> TextLayerReading | ScannedPdf:
    """A jelszavas vagy sérült PDF is eredményt ad, így nem marad örökre a sorban."""
    try:
        text = text_layer(content)
    except pdfium.PdfiumError as error:
        return TextLayerReading({"error": f"A PDF nem olvasható: {error}"})
    if is_readable(text):
        return TextLayerReading({"ocr_text": text, "done_reason": "stop", "seconds": 0})
    return ScannedPdf(model)
