"""Valódi Postgres, a tárolt szövegek feldolgozása; a tranzakció a végén visszagörgetődik."""

from uuid import uuid4

import app.parsing
import pytest
from app import bronze
from app.parsing import parse_pending
from app.receipt_parser import PARSER_VERSION
from conftest import (
    FIRST_PAGE,
    SAMPLE_TEXT,
    SECOND_PAGE,
    invented_receipt,
    make_group,
    make_item,
)

STORE_TEXT = (
    "ADOSZAM: 12345678-2-41\nNYUGTA\nC00 KENYÉR 500G 599\nÖSSZESEN: 599 FT\n"
    "BANKKARTYA: 599 FT\nNYUGTASZAM:\n2026.12.14. 0042/00017\n"
)


def stored(conn, item, payload) -> str:
    document_id = bronze.insert_document(conn, item, f"photo/teszt/{item['sha256']}.png")
    bronze.insert_extraction(conn, document_id, "teszt", "1", "2", payload)
    return bronze.group_of(conn, document_id)


def parses(conn, group_id):
    return conn.execute(
        "select parser_version, status, payload, checks from bronze.receipt_parse "
        "where group_id = %s order by created_at",
        (group_id,),
    ).fetchall()


def test_stored_text_is_parsed_once(conn):
    group_id = stored(conn, make_item(invented_receipt()), {"ocr_text": SAMPLE_TEXT})

    parse_pending(conn, group_id)
    parse_pending(conn, group_id)

    rows = parses(conn, group_id)
    assert len(rows) == 1
    assert rows[0][1] == "ok"
    assert rows[0][2]["total"] == 1048


def test_old_style_reading_is_parsed_too(conn):
    payload = {"raw_text": "{}", "parsed": {"store": "rossz"}, "ocr_text": SAMPLE_TEXT}
    group_id = stored(conn, make_item(invented_receipt()), payload)

    parse_pending(conn, group_id)

    assert parses(conn, group_id)[0][2]["total"] == 1048


def test_new_parser_version_reads_stored_text_again(conn, monkeypatch):
    group_id = stored(conn, make_item(invented_receipt()), {"ocr_text": SAMPLE_TEXT})
    parse_pending(conn, group_id)

    monkeypatch.setattr(app.parsing, "PARSER_VERSION", "uj-valtozat")
    parse_pending(conn, group_id)

    assert [row[0] for row in parses(conn, group_id)] == [PARSER_VERSION, "uj-valtozat"]


def test_group_is_parsed_as_one_receipt_with_overlap_removed(conn):
    items = make_group([invented_receipt(), invented_receipt()])
    group_id = stored(conn, items[0], {"ocr_text": FIRST_PAGE})
    stored(conn, items[1], {"ocr_text": SECOND_PAGE})

    parse_pending(conn, group_id)

    rows = parses(conn, group_id)
    assert len(rows) == 1
    assert rows[0][1] == "ok"
    assert [item["value"] for item in rows[0][2]["items"]] == [599, 449, 899]


def test_group_waits_until_all_pages_are_read(conn):
    items = make_group([invented_receipt(), invented_receipt()])
    group_id = stored(conn, items[0], {"ocr_text": FIRST_PAGE})

    parse_pending(conn, group_id)

    assert parses(conn, group_id) == []


def test_unreadable_page_makes_the_group_unparsed(conn):
    items = make_group([invented_receipt(), invented_receipt()])
    group_id = stored(conn, items[0], {"ocr_text": FIRST_PAGE})
    stored(conn, items[1], {"error": "A kép nem olvasható"})

    parse_pending(conn, group_id)

    assert parses(conn, group_id)[0][1] == "unparsed"


def test_rephotographed_receipt_needs_review(conn):
    undated = {"purchase_date": None}
    first = stored(conn, make_item(invented_receipt()) | undated, {"ocr_text": STORE_TEXT})
    second = stored(conn, make_item(invented_receipt()) | undated, {"ocr_text": STORE_TEXT})

    parse_pending(conn, first)
    parse_pending(conn, second)

    assert parses(conn, first)[0][1] == "ok"
    assert parses(conn, second)[0][1] == "review"
    assert parses(conn, second)[0][3]["duplicate"]["ok"] is False


def test_entered_date_is_compared_with_the_read_date(conn):
    item = make_item(invented_receipt()) | {"purchase_date": "2026-12-13"}
    group_id = stored(conn, item, {"ocr_text": STORE_TEXT})

    parse_pending(conn, group_id)

    assert parses(conn, group_id)[0][1] == "review"
    assert parses(conn, group_id)[0][3]["date"]["ok"] is False


def test_parser_failure_does_not_stop_the_worker(conn, monkeypatch):
    def broken(_texts):
        raise ValueError("váratlan formátum")

    monkeypatch.setattr(app.parsing, "parse_pages", broken)
    group_id = stored(conn, make_item(invented_receipt()), {"ocr_text": SAMPLE_TEXT})

    parse_pending(conn, group_id)

    assert parses(conn, group_id)[0][1] == "unparsed"


def test_unknown_group_is_ignored(conn):
    assert parse_pending(conn, uuid4()) == 0


def test_app_writer_cannot_change_a_parse(conn):
    group_id = stored(conn, make_item(invented_receipt()), {"ocr_text": SAMPLE_TEXT})
    parse_pending(conn, group_id)

    with pytest.raises(Exception, match="permission denied"):
        conn.execute("update bronze.receipt_parse set status = 'ok'")
