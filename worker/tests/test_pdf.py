"""A tesztfájlok itt készülnek, kitalált adattal: PDF nem kerülhet a repóba."""

from io import BytesIO
from pathlib import Path

from app.document_parser import parse_document
from app.extract import MAX_SIDE
from app.pdf import (
    MAX_SCANNED_PAGES,
    ScannedPdf,
    TextLayerReading,
    is_readable,
    reader_for,
    render_pages,
    text_layer,
)
from conftest import FakeReader, invented_pdf, no_report, scanned_pdf
from PIL import Image

INVOICES = Path(__file__).parent / "invoices"
LONG_LINE = "Ez a kitalált, kicsit hosszabb sor adja meg a szövegréteg elegendő hosszát."


def test_lines_follow_the_page_not_the_file_order():
    # A fájlban oszloponként vannak a cellák, ahogy sok számlázóprogram írja.
    content = invented_pdf(
        [
            (50, 700, "Elso termek"),
            (50, 680, "Masodik termek"),
            (300, 700, "1 000"),
            (300, 680, "2 000"),
        ]
    )

    assert text_layer(content).splitlines() == ["Elso termek 1 000", "Masodik termek 2 000"]


def test_lines_run_from_the_top_of_the_page():
    content = invented_pdf([(50, 100, "also sor"), (50, 800, "felso sor")])

    assert text_layer(content).splitlines() == ["felso sor", "also sor"]


def test_text_pdf_needs_no_model():
    content = invented_pdf([(50, 700, LONG_LINE)])
    model = FakeReader()

    active = reader_for(content, model)
    result = active.read(content, no_report)

    assert isinstance(active, TextLayerReading)
    assert result["ocr_text"].startswith("Ez a kitalált, kicsit")
    assert result["done_reason"] == "stop"
    assert model.calls == 0


def test_text_pdf_records_the_library_as_reader():
    active = reader_for(invented_pdf([(50, 700, LONG_LINE)]), FakeReader())

    assert active.name == "pdfium"
    assert active.version()


def test_invoice_in_a_pdf_reaches_the_invoice_parser():
    lines = (INVOICES / "one_line_row.txt").read_text(encoding="utf-8").splitlines()
    content = invented_pdf([(50, 820 - 14 * row, line) for row, line in enumerate(lines)])

    result = parse_document([text_layer(content)])

    assert result["document_type"] == "invoice"
    assert result["total"] == 13700
    assert [item["value"] for item in result["items"]] == [12700, 1000]


def test_scanned_pdf_goes_to_the_model_page_by_page():
    content = scanned_pdf(2)
    model = FakeReader({"ocr_text": "KIOLVASOTT", "seconds": 80.0, "done_reason": "stop"})

    active = reader_for(content, model)
    result = active.read(content, no_report)

    assert isinstance(active, ScannedPdf)
    assert (active.name, active.version()) == (model.name, model.version())
    assert result == {"ocr_text": "KIOLVASOTT\nKIOLVASOTT", "done_reason": "stop", "seconds": 160.0}


def test_scanned_pdf_reads_only_the_first_pages():
    content = scanned_pdf(MAX_SCANNED_PAGES + 2)
    model = FakeReader()

    reader_for(content, model).read(content, no_report)

    assert len(model.images) == MAX_SCANNED_PAGES


def test_pages_are_rendered_for_the_model():
    with Image.open(BytesIO(render_pages(scanned_pdf())[0])) as page:
        assert page.format == "JPEG"
        assert max(page.size) == MAX_SIDE


def test_broken_pdf_reports_an_error_and_needs_no_model():
    model = FakeReader()

    result = reader_for(b"%PDF-1.7 serult", model).read(b"", no_report)

    assert result["error"].startswith("A PDF nem olvasható")
    assert model.calls == 0


def test_short_or_garbled_text_layer_is_not_used():
    assert not is_readable("Scanner 3000")
    assert not is_readable("?" * 60 + "a" * 5)
    assert is_readable(LONG_LINE)
