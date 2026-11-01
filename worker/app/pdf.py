"""A PDF olvasása: a szövegréteg közvetlenül, a szkennelt lapok a modellen át."""

from collections.abc import Callable

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


def sorted_rows(boxes: list[tuple[float, float, float, str]]) -> list[str]:
    """Szövegdobozokból látható sorok: a fájl belső sorrendje oszloponként is haladhat."""
    rows: list[list[tuple[float, float, float, str]]] = []
    for box in sorted(boxes, key=lambda box: -box[2]):
        middle = (box[1] + box[2]) / 2
        if rows and rows[-1][0][1] <= middle <= rows[-1][0][2]:
            rows[-1].append(box)
        else:
            rows.append([box])
    return [" ".join(box[3] for box in sorted(row)) for row in rows]


def page_lines(page: pdfium.PdfPage) -> list[str]:
    text_page = page.get_textpage()
    boxes = []
    for index in range(text_page.count_rects()):
        left, bottom, right, top = text_page.get_rect(index)
        text = text_page.get_text_bounded(left, bottom, right, top).strip()
        if text:
            boxes.append((left, bottom, top, " ".join(text.split())))
    return sorted_rows(boxes)


def text_layer(content: bytes) -> str:
    with pdfium.PdfDocument(content) as document:
        return "\n".join(line for page in document for line in page_lines(page))


def is_readable(text: str) -> bool:
    visible = [char for char in text if not char.isspace()]
    return (
        len(visible) >= MIN_TEXT_CHARS
        and sum(char.isalnum() for char in visible) >= MIN_READABLE_SHARE * len(visible)
    )


def render_pages(content: bytes) -> list[bytes]:
    """A lapok a modell bemenetéhez illő méretben; a kis oldalméret így nem ront a felbontáson."""
    with pdfium.PdfDocument(content) as document:
        images = []
        for index in range(min(len(document), MAX_SCANNED_PAGES)):
            page = document[index]
            scale = MAX_SIDE / max(page.get_size())
            images.append(to_jpeg(page.render(scale=scale).to_pil()))
        return images


class TextLayerReading:
    """A szövegréteghez nem kell modell, ezért a bronzban a könyvtár neve és verziója szerepel."""

    name = READER_NAME

    def __init__(self, payload: dict):
        self.payload = payload

    def version(self) -> str:
        return str(pdfium.PYPDFIUM_INFO)

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
            pages = render_pages(content)
        except pdfium.PdfiumError as error:
            return {"error": f"A PDF nem olvasható: {error}"}
        results = [self.model.read_image(page, report) for page in pages]
        return {
            "ocr_text": "\n".join(result["ocr_text"] for result in results),
            "done_reason": results[-1].get("done_reason") if results else None,
            "seconds": round(sum(result.get("seconds", 0) for result in results), 1),
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
