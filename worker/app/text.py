"""A szöveges dokumentum (pl. a számlát tartalmazó levél törzse): nincs mit kiolvasni, a szöveg kész."""

from collections.abc import Callable

CONTENT_TYPE = "text/plain"
READER_NAME = "text"
READER_VERSION = "1"


class TextReader:
    name = READER_NAME

    def version(self) -> str:
        return READER_VERSION

    def read(self, content: bytes, report: Callable[[str], None]) -> dict:
        report("read_text")
        return {"ocr_text": content.decode("utf-8")}
