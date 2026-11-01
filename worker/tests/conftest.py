import hashlib
import os
from io import BytesIO
from uuid import uuid4

import psycopg
import pytest
from app.storage import BUCKET, Storage
from PIL import Image

SAMPLE_TEXT = "NYUGTA\nC00 KENYÉR 500G 599\nC00 TEJ 1L 449\nÖSSZESEN: 1 048 FT\n"
FIRST_PAGE = "NYUGTA\nC00 KENYÉR 500G 599\nC00 TEJ 1L 449\n"
SECOND_PAGE = "C00 TEJ 1L 449\nB00 VAJ 200G 899\nÖSSZESEN: 1 947 FT\n"

test_database_url = os.environ.get("TEST_DATABASE_URL")
test_garage_endpoint = os.environ.get("TEST_GARAGE_ENDPOINT")


def invented_receipt() -> bytes:
    """Minden hívás más hash-t ad, mert a bronzban a hash egyedi."""
    image = Image.frombytes("RGB", (16, 16), os.urandom(16 * 16 * 3))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def invented_pdf(rows: list[tuple[int, int, str]]) -> bytes:
    """Szöveges, egylapos PDF: (x, y, szöveg) sorok, a megadott sorrendben a fájlban."""
    text = "".join(
        f"BT /F1 10 Tf {x} {y} Td ({value.replace('(', '[').replace(')', ']')}) Tj ET\n"
        for x, y, value in rows
    ).encode("cp1252", "replace")
    page = (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        page,
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(text), text),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    body = b"%PDF-1.7\n"
    offsets = []
    for number, content in enumerate(objects, 1):
        offsets.append(len(body))
        body += b"%d 0 obj\n%s\nendobj\n" % (number, content)
    table = len(body)
    body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    body += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    body += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, table)
    return body


def scanned_pdf(pages: int = 1) -> bytes:
    """Csak képből álló PDF, szövegréteg nélkül."""
    images = [Image.new("RGB", (120, 160), "white") for _ in range(pages)]
    buffer = BytesIO()
    images[0].save(buffer, format="PDF", save_all=True, append_images=images[1:])
    return buffer.getvalue()


def make_item(content: bytes) -> dict:
    return {
        "id": str(uuid4()),
        "sha256": hashlib.sha256(content).hexdigest(),
        "content_type": "image/png",
        "uploaded_by": "person_a",
        "uploaded_at": "2026-12-01T10:00:00+00:00",
        "purchased_by": "person_b",
        "purchase_date": "2026-11-30",
        "payer": "shared",
        "tags": ["élelmiszer", "háztartás"],
        "group_id": None,
        "page_no": 1,
        "page_count": 1,
    }


def make_group(contents: list[bytes]) -> list[dict]:
    group_id = str(uuid4())
    return [
        make_item(content)
        | {"group_id": group_id, "page_no": page_no, "page_count": len(contents)}
        for page_no, content in enumerate(contents, 1)
    ]


def no_report(_step: str) -> None:
    pass


class FakeInbox:
    def __init__(self, files: dict[str, bytes]):
        self.files = files
        self.closed: list[str] = []
        self.outcomes: list[dict] = []

    def download(self, item_id: str) -> bytes:
        return self.files[item_id]

    def close(self, item_id: str, outcome: dict) -> None:
        self.closed.append(item_id)
        self.outcomes.append(outcome)


class FakeReader:
    name = "teszt-modell"

    def __init__(self, payload: dict | None = None, error: Exception | None = None):
        self.payload = payload or {"ocr_text": SAMPLE_TEXT, "seconds": 80.0}
        self.error = error
        self.calls = 0
        self.images: list[bytes] = []

    def version(self) -> str:
        return "teszt-valtozat"

    def read(self, content: bytes, report) -> dict:
        self.calls += 1
        report("read_text")
        if self.error:
            raise self.error
        return self.payload

    def read_image(self, image: bytes, report) -> dict:
        self.images.append(image)
        return self.read(image, report)


@pytest.fixture
def conn():
    if not test_database_url:
        pytest.skip("nincs TEST_DATABASE_URL")
    with psycopg.connect(test_database_url) as connection:
        yield connection
        connection.rollback()


@pytest.fixture
def storage():
    """Valódi Garage; a teszt alatt írt objektumok a végén törlődnek."""
    if not test_garage_endpoint:
        pytest.skip("nincs TEST_GARAGE_ENDPOINT")
    garage = Storage(
        test_garage_endpoint, os.environ["GARAGE_ACCESS_KEY"], os.environ["GARAGE_SECRET_KEY"]
    )
    written: list[str] = []
    original_put = garage.put

    def put(key: str, content: bytes, content_type: str) -> None:
        written.append(key)
        original_put(key, content, content_type)

    garage.put = put
    garage.written = written
    yield garage
    for key in written:
        garage.client.delete_object(Bucket=BUCKET, Key=key)
