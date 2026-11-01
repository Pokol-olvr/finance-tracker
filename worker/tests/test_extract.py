import json
from io import BytesIO

import httpx
import pytest
from app.extract import (
    MAX_SIDE,
    PROMPT,
    TEXT_PROMPT,
    ModelMissing,
    ReceiptReader,
    parse_output,
    prepare_image,
)
from app.inbox import Inbox
from conftest import no_report
from PIL import Image


def image_bytes(image, image_format="JPEG", **options) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format=image_format, **options)
    return buffer.getvalue()


def reader_with(handler) -> ReceiptReader:
    reader = ReceiptReader("http://ollama:11434", "glm-ocr", 10)
    reader.client = httpx.Client(
        base_url="http://ollama:11434", transport=httpx.MockTransport(handler)
    )
    return reader


def test_prepare_image_shrinks_long_side():
    prepared = Image.open(BytesIO(prepare_image(image_bytes(Image.new("RGB", (4000, 3000))))))

    assert prepared.format == "JPEG"
    assert prepared.size == (MAX_SIDE, 1050)


def test_prepare_image_keeps_small_image_size():
    prepared = Image.open(BytesIO(prepare_image(image_bytes(Image.new("RGB", (620, 500))))))

    assert prepared.size == (620, 500)


def test_prepare_image_applies_exif_rotation():
    exif = Image.Exif()
    exif[0x0112] = 6
    rotated = image_bytes(Image.new("RGB", (400, 200)), exif=exif)

    prepared = Image.open(BytesIO(prepare_image(rotated)))

    assert prepared.size == (200, 400)


def test_prepare_image_reads_heic():
    pytest.importorskip("pillow_heif")
    heic = image_bytes(Image.new("RGB", (64, 32), "white"), "HEIF")

    assert Image.open(BytesIO(prepare_image(heic))).size == (64, 32)


def test_prepare_image_flattens_transparent_png():
    png = image_bytes(Image.new("RGBA", (32, 32), (255, 255, 255, 0)), "PNG")

    assert Image.open(BytesIO(prepare_image(png))).mode == "RGB"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('```json\n{"store": "TESZT"}\n```', {"store": "TESZT"}),
        ('{"store": "TESZT"}', {"store": "TESZT"}),
        ('{"store": "TESZT"', None),
        ("[1, 2]", None),
        ("nincs itt JSON", None),
        ("", None),
    ],
)
def test_parse_output(text, expected):
    assert parse_output(text) == expected


def test_read_sends_settings_and_keeps_both_readings():
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        structured = "format" in sent[-1]
        return httpx.Response(
            200,
            json={
                "message": {"content": '{"store": "TESZT"}' if structured else "TESZT\n7 626 Ft"},
                "done_reason": "stop",
                "total_duration": 17_000_000_000,
            },
        )

    steps = []
    result = reader_with(handler).read(image_bytes(Image.new("RGB", (32, 32))), steps.append)

    assert steps == ["read_json", "read_text"]
    assert [request["messages"][0]["content"] for request in sent] == [PROMPT, TEXT_PROMPT]
    assert sent[0]["options"] == {"temperature": 0, "num_thread": 10, "num_predict": 2000}
    assert sent[0]["format"]["required"] == ["store", "date", "items", "total", "payment_method"]
    assert "format" not in sent[1]
    assert sent[0]["keep_alive"] == "0"
    assert sent[0]["stream"] is False
    assert result == {
        "raw_text": '{"store": "TESZT"}',
        "parsed": {"store": "TESZT"},
        "ocr_text": "TESZT\n7 626 Ft",
        "done_reason": "stop",
        "seconds": 34.0,
    }


def test_broken_output_is_kept_without_parsed_value():
    def handler(_request):
        return httpx.Response(200, json={"message": {"content": "nem json"}})

    result = reader_with(handler).read(image_bytes(Image.new("RGB", (32, 32))), no_report)

    assert result["raw_text"] == "nem json"
    assert result["parsed"] is None


def test_unreadable_image_does_not_reach_the_model():
    def handler(_request):
        raise AssertionError("a modell nem kaphatja meg")

    result = reader_with(handler).read(b"\xff\xd8\xff nem igazi kep", no_report)

    assert "error" in result


def test_model_error_is_raised_so_item_stays_open():
    def handler(_request):
        return httpx.Response(500, json={"error": "hiba"})

    with pytest.raises(httpx.HTTPStatusError):
        reader_with(handler).read(image_bytes(Image.new("RGB", (32, 32))), no_report)


def test_version_returns_digest():
    def handler(_request):
        return httpx.Response(200, json={"models": [{"name": "glm-ocr:latest", "digest": "abc"}]})

    assert reader_with(handler).version() == "abc"


def test_missing_model_is_reported():
    def handler(_request):
        return httpx.Response(200, json={"models": []})

    with pytest.raises(ModelMissing):
        reader_with(handler).version()


def test_inbox_client_sends_token():
    seen = {}

    def handler(request):
        seen["authorization"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"items": [{"id": "1"}]})

    inbox = Inbox("http://webapp:8000", "titok", httpx.MockTransport(handler))

    assert inbox.list_new() == [{"id": "1"}]
    assert seen == {
        "authorization": "Bearer titok",
        "url": "http://webapp:8000/inbox/items?status=new",
    }
