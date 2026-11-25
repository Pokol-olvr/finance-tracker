"""E-mailes számlafogadás (FIN-307) kitalált levelekkel; a bronzos tesztek visszagörgetnek."""

import hashlib
import os
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

import pytest
from app import bronze, mail, reviews
from app.mail import (
    PROCESSED,
    QUARANTINE,
    Auth,
    MailIntake,
    MailSettings,
    body_text,
    documents_of,
    handle,
    html_to_text,
    imap_utf7,
    is_trusted,
    parse_results,
    read_auth,
    subject_tags,
)
from app.main import store_content
from app.storage import BUCKET
from conftest import FakeInbox, FakeReader, invented_pdf, invented_receipt, no_report

GOOD_AUTH = (
    "mx.mailbox.org; dkim=pass (2048-bit key) header.d=bolt.example header.i=@bolt.example; "
    "spf=pass (mailbox.org: domain of szamla@bolt.example designates 192.0.2.1 as permitted sender) "
    "smtp.mailfrom=szamla@bolt.example; dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=bolt.example"
)
RECEIVED = datetime(2026, 12, 3, 9, 30, tzinfo=UTC)
SETTINGS = MailSettings(
    "imap.example", "u", "p", buyers={"en@example.test": "person_a"}
)
INVOICE_ROWS = [
    (50, 800, "SZÁMLA"),
    (50, 780, "Eladó: Példa Bolt Kft."),
    (50, 760, "Adószám: 12345678-2-42"),
    (50, 740, "Számla sorszáma: PB-2026-001"),
    (50, 720, "Kelt: 2026.12.02"),
    (50, 700, "Kenyér 1 db 599 Ft"),
    (50, 680, "Fizetendő összeg: 599 Ft"),
]


def big_image() -> bytes:
    """Tömöríthetetlen PNG, a logóküszöbnél nagyobb."""
    from io import BytesIO

    from PIL import Image

    image = Image.frombytes("RGB", (120, 120), os.urandom(120 * 120 * 3))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_email(
    *,
    sender: str = "Példa Bolt <szamla@bolt.example>",
    auth: list[str] | None = None,
    subject: str = "Számla PB-2026-001 #élelmiszer #Háztartás",
    body: str = "Köszönjük a vásárlást, a számlát csatoltuk.",
    html: str | None = None,
    attachments: list[tuple[bytes, str, str, str, str]] = (),
) -> bytes:
    message = EmailMessage()
    for header in [GOOD_AUTH] if auth is None else auth:
        message["Authentication-Results"] = header
    message["From"] = sender
    message["To"] = "szamla@example.test"
    message["Subject"] = subject
    message["Date"] = format_datetime(RECEIVED)
    message["Message-ID"] = make_msgid(domain="bolt.example")
    message.set_content(body)
    if html is not None:
        message.add_alternative(html, subtype="html")
    for content, maintype, subtype, filename, disposition in attachments:
        message.add_attachment(
            content,
            maintype=maintype,
            subtype=subtype,
            filename=filename,
            disposition=disposition,
        )
    return message.as_bytes()


def pdf_attachment(rows=INVOICE_ROWS) -> tuple[bytes, str, str, str, str]:
    return (invented_pdf(rows), "application", "pdf", "szamla.pdf", "attachment")


def parsed(raw: bytes):
    from email import message_from_bytes, policy

    return message_from_bytes(raw, policy=policy.default)


# --- A feladó ellenőrzése ----------------------------------------------------------------------


def test_results_header_is_parsed_without_comments():
    auth = parse_results(GOOD_AUTH)

    assert auth == Auth(
        "mx.mailbox.org", "pass", "bolt.example", "pass", (("pass", "bolt.example"),)
    )


@pytest.mark.parametrize(
    ("header", "trusted"),
    [
        ("mx; dmarc=pass header.from=bolt.example", True),
        (
            "mx; dkim=pass header.d=bolt.example; dmarc=fail header.from=bolt.example",
            False,
        ),
        ("mx; dkim=pass header.d=mail.bolt.example; dmarc=none", True),
        ("mx; dkim=pass header.d=levelkuldo.example; dmarc=none", False),
        ("mx; spf=pass smtp.mailfrom=bounce@bolt.example", True),
        ("mx; spf=pass smtp.mailfrom=bounce@levelkuldo.example", False),
        (
            "mx; dkim=fail header.d=bolt.example; spf=softfail smtp.mailfrom=x@bolt.example",
            False,
        ),
        ("mx; none", False),
    ],
)
def test_sender_is_trusted_only_with_aligned_results(header, trusted):
    assert is_trusted(parse_results(header), "bolt.example") is trusted


def test_missing_sender_is_never_trusted():
    assert is_trusted(parse_results("mx; dmarc=pass"), None) is False


def test_only_the_top_results_header_counts():
    """A lejjebb lévő fejlécet a feladó is beleírhatja a levélbe."""
    forged = make_email(
        auth=["mx.mailbox.org; dmarc=fail", "mx.mailbox.org; dmarc=pass"]
    )

    assert read_auth(parsed(forged), None).dmarc == "fail"


def test_configured_server_id_ignores_foreign_headers():
    forged = make_email(auth=["hamis.example; dmarc=pass header.from=bolt.example"])

    assert read_auth(parsed(forged), "mx.mailbox.org") == Auth(None)
    assert read_auth(parsed(make_email()), "mx.mailbox.org").dmarc == "pass"


# --- A levél tartalma ----------------------------------------------------------------------------


def test_pdf_and_large_image_attachments_are_documents_but_inline_logo_is_not():
    logo = invented_receipt()
    photo = big_image()
    raw = make_email(
        attachments=[
            pdf_attachment(),
            (logo, "image", "png", "logo.png", "inline"),
            (photo, "image", "png", "blokk.png", "attachment"),
        ]
    )

    found = documents_of(parsed(raw))

    assert [content_type for _, content_type in found] == [
        "application/pdf",
        "image/png",
    ]
    assert found[1][0] == photo


def test_type_comes_from_content_not_from_the_name():
    fake = (b"nem pdf, csak szoveg", "application", "pdf", "szamla.pdf", "attachment")

    assert documents_of(parsed(make_email(attachments=[fake]))) == []


def test_forwarded_message_attachment_is_found():
    inner = parsed(make_email(attachments=[pdf_attachment()]))
    outer = EmailMessage()
    outer["From"] = "En <en@example.test>"
    outer["Subject"] = "Fwd: Számla"
    outer.set_content("Továbbítom.")
    outer.add_attachment(inner)

    assert [kind for _, kind in documents_of(parsed(outer.as_bytes()))] == [
        "application/pdf"
    ]


def test_same_attachment_twice_is_one_document():
    raw = make_email(attachments=[pdf_attachment(), pdf_attachment()])

    assert len(documents_of(parsed(raw))) == 1


def test_html_table_becomes_readable_lines():
    html = (
        "<html><head><style>p{}</style></head><body><p>Számla&nbsp;összesítő</p>"
        "<table><tr><td>Kenyér</td><td>599 Ft</td></tr><tr><td>Fizetendő</td><td>599 Ft</td></tr>"
        "</table><script>alert(1)</script></body></html>"
    )

    assert html_to_text(html) == "Számla összesítő\nKenyér 599 Ft\nFizetendő 599 Ft"


def test_plain_body_is_preferred_and_html_is_the_fallback():
    assert body_text(parsed(make_email(body="Sima szöveg"))) == "Sima szöveg"
    html_only = EmailMessage()
    html_only["From"] = "a@b.example"
    html_only.set_content("<p>Csak HTML</p>", subtype="html")
    assert body_text(parsed(html_only.as_bytes())) == "Csak HTML"


def test_tags_come_from_the_subject():
    assert subject_tags("Számla #élelmiszer #Háztartás #élelmiszer") == [
        "háztartás",
        "élelmiszer",
    ]
    assert subject_tags(None) == []


@pytest.mark.parametrize(
    ("name", "encoded"),
    [("Feldolgozva", "Feldolgozva"), ("Karantén", "Karant&AOk-n"), ("a&b", "a&-b")],
)
def test_folder_names_use_imap_utf7(name, encoded):
    assert imap_utf7(name) == encoded


# --- Bronz és Garage --------------------------------------------------------------------------


def store_with(conn, storage, reader=None):
    active = reader or FakeReader()
    return lambda item, content: store_content(
        item, content, conn, storage, active, no_report
    )[0]


def email_rows(conn, raw):
    return conn.execute(
        "select object_key, from_address, subject, auth ->> 'dmarc', document_ids "
        "from bronze.email_message where sha256 = %s",
        (hashlib.sha256(raw).hexdigest(),),
    ).fetchall()


def document(conn, document_id):
    return conn.execute(
        "select object_key, source_type, uploaded_by, purchased_by, tags, uploaded_at "
        "from bronze.raw_document where id = %s",
        (document_id,),
    ).fetchone()


def stored(storage, key):
    return storage.client.get_object(Bucket=BUCKET, Key=key)["Body"].read()


def test_trusted_email_with_pdf_reaches_bronze_and_review(conn, storage):
    raw = make_email(attachments=[pdf_attachment()])

    assert (
        handle(conn, storage, store_with(conn, storage), raw, RECEIVED, SETTINGS)
        == PROCESSED
    )

    [(key, sender, subject, dmarc, document_ids)] = email_rows(conn, raw)
    digest = hashlib.sha256(raw).hexdigest()
    assert key == f"email/2026/12/{digest}.eml"
    assert stored(storage, key) == raw
    assert (sender, subject, dmarc) == (
        "szamla@bolt.example",
        "Számla PB-2026-001 #élelmiszer #Háztartás",
        "pass",
    )
    [document_id] = document_ids
    object_key, source_type, uploaded_by, purchased_by, tags, uploaded_at = document(
        conn, document_id
    )
    assert object_key.startswith("email/2026/12/") and object_key.endswith(".pdf")
    assert (source_type, uploaded_by, purchased_by) == ("email", "email", None)
    assert tags == ["háztartás", "élelmiszer"]
    assert uploaded_at == RECEIVED
    group_id = bronze.group_of(conn, document_id)
    assert bronze.latest_parse_id(conn, group_id) is not None


def test_forwarded_from_own_address_sets_the_buyer(conn, storage):
    own_auth = "mx.mailbox.org; dkim=pass header.d=example.test; dmarc=pass header.from=example.test"
    raw = make_email(
        sender="Én <En@Example.test>", auth=[own_auth], attachments=[pdf_attachment()]
    )

    handle(conn, storage, store_with(conn, storage), raw, RECEIVED, SETTINGS)

    [(_, _, _, _, [document_id])] = email_rows(conn, raw)
    assert document(conn, document_id)[3] == "person_a"


def test_buyers_are_read_from_the_environment():
    from app.config import parse_buyers

    assert parse_buyers("person_a:A@Example.hu, person_b:b@example.hu,hibás") == {
        "a@example.hu": "person_a",
        "b@example.hu": "person_b",
    }


def test_untrusted_email_stays_out_of_bronze_and_garage(conn, storage):
    raw = make_email(
        auth=[
            "mx.mailbox.org; dkim=fail header.d=bolt.example; dmarc=fail header.from=bolt.example"
        ],
        attachments=[pdf_attachment()],
    )

    assert (
        handle(conn, storage, store_with(conn, storage), raw, RECEIVED, SETTINGS)
        == QUARANTINE
    )
    assert email_rows(conn, raw) == []
    assert storage.written == []


def test_body_only_email_becomes_a_text_document(conn, storage):
    body = "Számla\nEladó: Példa Bolt Kft.\nKenyér 599 Ft\nFizetendő összeg: 599 Ft"
    raw = make_email(body=body)

    handle(conn, storage, store_with(conn, storage), raw, RECEIVED, SETTINGS)

    [(_, _, _, _, [document_id])] = email_rows(conn, raw)
    object_key = document(conn, document_id)[0]
    assert object_key.endswith(".txt")
    assert stored(storage, object_key).decode() == body
    [(model_name, payload)] = conn.execute(
        "select model_name, payload from bronze.extraction where document_id = %s",
        (document_id,),
    ).fetchall()
    assert (model_name, payload) == ("text", {"ocr_text": body})


def test_text_page_goes_to_review_with_charset(conn, storage):
    raw = make_email(body="Számla\nFizetendő összeg: 1 290 Ft\nKöszönjük a vásárlást!")
    handle(conn, storage, store_with(conn, storage), raw, RECEIVED, SETTINGS)
    [(_, _, _, _, [document_id])] = email_rows(conn, raw)
    group_id = bronze.group_of(conn, document_id)
    inbox = FakeInbox({})

    candidate = {
        "group_id": group_id,
        "parse_id": bronze.latest_parse_id(conn, group_id),
        "uploaded_at": RECEIVED,
    }
    reviews.push(conn, inbox, storage, candidate, has_files=False)

    assert inbox.page_types[(str(group_id), 1)] == "text/plain; charset=utf-8"
    assert inbox.reviews[str(group_id)]["content_types"] == [
        "text/plain; charset=utf-8"
    ]


def test_short_body_without_attachment_is_recorded_without_document(conn, storage):
    raw = make_email(body="Szia!")

    assert (
        handle(conn, storage, store_with(conn, storage), raw, RECEIVED, SETTINGS)
        == PROCESSED
    )
    [(_, _, _, _, document_ids)] = email_rows(conn, raw)
    assert document_ids == []


def test_same_email_twice_is_stored_once(conn, storage):
    raw = make_email(attachments=[pdf_attachment()])
    store = store_with(conn, storage)
    handle(conn, storage, store, raw, RECEIVED, SETTINGS)
    written = list(storage.written)

    assert handle(conn, storage, store, raw, RECEIVED, SETTINGS) == PROCESSED
    assert len(email_rows(conn, raw)) == 1
    assert storage.written == written


# --- A postafiók köre -----------------------------------------------------------------------------


class FakeMailbox:
    def __init__(
        self, messages: dict[bytes, bytes], sizes: dict[bytes, int] | None = None
    ):
        self.messages = messages
        self.sizes = sizes or {}
        self.moved: dict[bytes, str] = {}

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return None

    def uids(self):
        return list(self.messages)

    def size(self, uid):
        return self.sizes.get(uid, len(self.messages[uid]))

    def fetch(self, uid):
        return self.messages[uid], RECEIVED

    def move(self, uid, folder):
        self.moved[uid] = folder


def test_intake_moves_every_message_to_its_folder(conn, storage, monkeypatch):
    good = make_email(attachments=[pdf_attachment()])
    bad = make_email(auth=["mx.mailbox.org; dmarc=fail"])
    huge = make_email()
    broken = make_email(
        body="Ez a levél hibát okoz a feldolgozásban, mert a teszt így kéri."
    )
    mailbox = FakeMailbox(
        {b"1": good, b"2": bad, b"3": huge, b"4": broken},
        sizes={b"3": mail.MAX_MESSAGE_BYTES + 1},
    )
    original = mail.handle

    def failing(conn, storage, store, raw, received_at, settings):
        if raw == broken:
            raise KeyError("váratlan")
        return original(conn, storage, store, raw, received_at, settings)

    monkeypatch.setattr(mail, "handle", failing)
    intake = MailIntake(
        MailSettings("imap.example", "u", "p"), mailbox_factory=lambda: mailbox
    )

    done = intake.run(conn, storage, store_with(conn, storage), no_report)

    assert mailbox.moved == {
        b"1": PROCESSED,
        b"2": QUARANTINE,
        b"3": QUARANTINE,
        b"4": QUARANTINE,
    }
    assert done == 3
    assert not intake.due()


def test_unreachable_mailbox_does_not_stop_the_worker(conn, storage):
    def unreachable():
        raise OSError("nincs kapcsolat")

    intake = MailIntake(
        MailSettings("imap.example", "u", "p"), mailbox_factory=unreachable
    )

    assert intake.run(conn, storage, store_with(conn, storage), no_report) == 0


def test_forward_header_images_and_links_are_removed_from_the_body():
    from app.mail import clean_body

    forwarded = (
        "---------- Forwarded message ---------\n"
        "Feladó: Apple <no_reply@email.apple.com>\n"
        "Date: 2026. nov. 24., K, 21:16\n"
        "Subject: Az Ön számlája az Apple-től\n"
        "To: <en@example.test>\n"
        "\n"
        "\n"
        "[image: Apple]\n"
        "Számla\n"
        "\n"
        "Sorszám:\n"
        "1-15004610664 <(500)%20461-0664>\n"
        "YouTube Premium (Havi)\n"
        "\n"
        "3490 Ft\n"
    )

    assert clean_body(forwarded) == (
        "Számla\nSorszám:\n1-15004610664\nYouTube Premium (Havi)\n3490 Ft"
    )


def test_body_without_forward_keeps_its_lines():
    from app.mail import clean_body

    assert clean_body("Kedves Vásárló!\n\nFizetendő: 1 290 Ft\n") == (
        "Kedves Vásárló!\nFizetendő: 1 290 Ft"
    )
