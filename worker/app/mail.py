"""E-mailes számlafogadás (FIN-307, ADR 0017).

A worker IMAP-on lehúzza a postafiók új leveleit. Ami a feladó-ellenőrzésen átmegy, annak a nyers
levele a Garage-ba, a PDF- és képmellékletei (vagy melléklet nélkül a törzse) dokumentumként a
bronzba kerülnek, és onnan ugyanazon az úton jutnak az Ellenőrzésre, mint a feltöltött fájlok.
A levél utána a „Feldolgozva” mappába kerül, az ellenőrizetlen feladóé a „Karantén”-ba; törlés nincs.
A kapcsolatot mindig a worker nyitja.
"""

import base64
import hashlib
import imaplib
import logging
import re
import socket
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from html.parser import HTMLParser
from typing import Self
from uuid import UUID

import psycopg

from app import bronze, pdf, text
from app.extract import ModelMissing
from app.parsing import parse_pending
from app.reviews import TRANSIENT

log = logging.getLogger("worker")

INBOX = "INBOX"
PROCESSED = "Feldolgozva"
QUARANTINE = "Karantén"
UPLOADER = "email"
# A Pi a 20 MB-nál nagyobb ellenőrzési oldalt nem fogadja; ennél nagyobb levél nem számla.
MAX_MESSAGE_BYTES = 30 * 1024 * 1024
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_DOCUMENTS = 5
# A kisebb kép jellemzően logó vagy aláírás; a modell percekig olvasná feleslegesen.
MIN_IMAGE_BYTES = 30_000
# Ennél rövidebb törzs (pl. „Szia, küldöm”) nem számla, nem kell belőle dokumentum.
MIN_BODY_CHARS = 40
FAILED = ("fail", "permerror", "softfail")
# Az IMAP-hiba a következő körben újrapróbálható, a worker nem áll le miatta.
MAIL_ERRORS = (imaplib.IMAP4.error, OSError, ssl.SSLError, socket.timeout)


# --- A feladó ellenőrzése -------------------------------------------------------------------


@dataclass(frozen=True)
class Auth:
    """A fogadó szerver (a postafiók) `Authentication-Results` fejlécének eredményei."""

    authserv_id: str | None
    spf: str | None = None
    spf_domain: str | None = None
    dmarc: str | None = None
    dkim: tuple[tuple[str, str | None], ...] = ()

    def as_json(self) -> dict:
        return {
            "authserv_id": self.authserv_id,
            "spf": self.spf,
            "spf_domain": self.spf_domain,
            "dmarc": self.dmarc,
            "dkim": [
                {"result": result, "domain": domain} for result, domain in self.dkim
            ],
        }


COMMENT = re.compile(r"\([^()]*\)")


def strip_comments(value: str) -> str:
    while COMMENT.search(value):
        value = COMMENT.sub(" ", value)
    return value


def domain_of(value: str | None) -> str | None:
    if not value:
        return None
    return value.rsplit("@", 1)[-1].strip().strip(">").lower() or None


def parse_results(header: str) -> Auth:
    parts = [
        part.strip() for part in strip_comments(" ".join(header.split())).split(";")
    ]
    authserv_id = parts[0].split()[0].lower() if parts and parts[0] else None
    spf = spf_domain = dmarc = None
    dkim: list[tuple[str, str | None]] = []
    for part in parts[1:]:
        tokens = part.split()
        if not tokens or "=" not in tokens[0]:
            continue
        method, result = tokens[0].lower().split("=", 1)
        properties = dict(
            token.lower().split("=", 1) for token in tokens[1:] if "=" in token
        )
        if method == "spf":
            spf = result
            spf_domain = domain_of(
                properties.get("smtp.mailfrom") or properties.get("smtp.helo")
            )
        elif method == "dkim":
            dkim.append((result, domain_of(properties.get("header.d"))))
        elif method == "dmarc":
            dmarc = result
    return Auth(authserv_id, spf, spf_domain, dmarc, tuple(dkim))


def read_auth(message: EmailMessage, authserv_id: str | None) -> Auth:
    """A fejlécet a saját postafiókunk szervere írja a levél tetejére; a lejjebb lévőt a feladó is
    hamisíthatja. Megadott `authserv_id`-nél csak az azzal kezdődő fejléc számít."""
    headers = [str(value) for value in message.get_all("Authentication-Results", [])]
    results = [parse_results(header) for header in headers]
    if authserv_id:
        results = [
            result for result in results if result.authserv_id == authserv_id.lower()
        ]
    return results[0] if results else Auth(None)


def aligned(domain: str | None, from_domain: str) -> bool:
    """Egyezés a feladó domainjével, aldomain is (a DMARC laza illesztése, közelítve)."""
    return bool(domain) and (
        domain == from_domain
        or from_domain.endswith("." + domain)
        or domain.endswith("." + from_domain)
    )


def is_trusted(auth: Auth, from_domain: str | None) -> bool:
    """DMARC-egyezés, vagy DMARC nélkül a feladó domainjére illeszkedő DKIM- vagy SPF-eredmény."""
    if from_domain is None:
        return False
    if auth.dmarc == "pass":
        return True
    if auth.dmarc in FAILED:
        return False
    if any(
        result == "pass" and aligned(domain, from_domain)
        for result, domain in auth.dkim
    ):
        return True
    return auth.spf == "pass" and aligned(auth.spf_domain, from_domain)


def from_address(message: EmailMessage) -> str | None:
    """Pontosan egy feladó; ha több vagy egy sincs, a levél gyanús."""
    try:
        addresses = message["From"].addresses if message["From"] else ()
    except (AttributeError, IndexError, ValueError):
        return None
    if (
        len(addresses) != 1
        or not addresses[0].addr_spec
        or "@" not in addresses[0].addr_spec
    ):
        return None
    return addresses[0].addr_spec.lower()


def to_addresses(message: EmailMessage) -> list[str]:
    found = []
    for name in ("To", "Cc"):
        for header in message.get_all(name, []):
            try:
                found.extend(address.addr_spec.lower() for address in header.addresses)
            except (AttributeError, ValueError):
                continue
    return [address for address in found if address]


# --- A levél tartalma ------------------------------------------------------------------------


def detect_type(content: bytes) -> str | None:
    """A melléklet típusa a tartalma alapján; a levélben megadott típus hamis is lehet."""
    if content.startswith(b"%PDF-"):
        return pdf.CONTENT_TYPE
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content[4:8] == b"ftyp" and content[8:12] in (
        b"heic",
        b"heix",
        b"mif1",
        b"msf1",
    ):
        return "image/heic"
    return None


def documents_of(message: EmailMessage) -> list[tuple[bytes, str]]:
    """A PDF- és képmellékletek, a továbbított levelekben is; a beágyazott kép (logó) kimarad."""
    found: list[tuple[bytes, str]] = []
    seen: set[str] = set()
    for part in message.walk():
        if part.is_multipart():
            continue
        try:
            content = part.get_payload(decode=True)
        except (ValueError, TypeError):
            continue
        if not content or len(content) > MAX_DOCUMENT_BYTES:
            continue
        content_type = detect_type(content)
        if content_type is None:
            continue
        if content_type != pdf.CONTENT_TYPE and (
            part.get_content_disposition() != "attachment"
            or len(content) < MIN_IMAGE_BYTES
        ):
            continue
        digest = hashlib.sha256(content).hexdigest()
        if digest not in seen:
            seen.add(digest)
            found.append((content, content_type))
    return found[:MAX_DOCUMENTS]


class HtmlText(HTMLParser):
    """HTML-ből olvasható szöveg: a blokkok és a táblázatsorok új sort, a cellák tabulátort kapnak."""

    BREAKS = frozenset(
        {"br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "table", "section"}
    )
    SKIP = frozenset({"script", "style", "head", "title"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.BREAKS:
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append("\t")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag in self.BREAKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skipping:
            self.parts.append(data)

    def text(self) -> str:
        lines = [
            " ".join(line.replace("\xa0", " ").split())
            for line in "".join(self.parts).split("\n")
        ]
        return "\n".join(line for line in lines if line)


def html_to_text(html: str) -> str:
    parser = HtmlText()
    parser.feed(html)
    parser.close()
    return parser.text()


def body_text(message: EmailMessage) -> str:
    body = message.get_body(preferencelist=("plain", "html"))
    if body is None:
        return ""
    try:
        content = body.get_content()
    except (LookupError, ValueError):
        return ""
    if body.get_content_subtype() == "html":
        return html_to_text(content)
    lines = [line.rstrip() for line in content.replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


TAG = re.compile(r"#(\w+)")


def subject_tags(subject: str | None) -> list[str]:
    """A tárgyban `#élelmiszer #háztartás` formában megadott címkék."""
    return sorted({tag.lower() for tag in TAG.findall(subject or "")})


def sent_at(message: EmailMessage) -> datetime | None:
    try:
        value = message["Date"].datetime if message["Date"] else None
    except (AttributeError, ValueError, TypeError):
        return None
    if value is not None and value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value


@dataclass(frozen=True)
class MailSettings:
    host: str
    user: str
    password: str
    authserv_id: str | None = None
    poll_seconds: int = 300
    # A saját címekről továbbított levélnél a vásárló a továbbító; a bolt közvetlen levelénél üres.
    buyers: dict[str, str] = field(default_factory=dict)


# --- Feldolgozás ------------------------------------------------------------------------------

Store = Callable[[dict, bytes], UUID]


def handle(
    conn: psycopg.Connection,
    storage,
    store: Store,
    raw: bytes,
    received_at: datetime,
    settings: MailSettings,
) -> str:
    """Egy levél; a visszaadott mappába kerül. Bármelyik lépés után újrafuttatható."""
    message = message_from_bytes(raw, policy=policy.default)
    sender = from_address(message)
    auth = read_auth(message, settings.authserv_id)
    if not is_trusted(auth, domain_of(sender)):
        log.warning(
            "Ellenőrizetlen feladó, karantén: %s (dmarc=%s, spf=%s, dkim=%s)",
            sender,
            auth.dmarc,
            auth.spf,
            [result for result, _ in auth.dkim],
        )
        return QUARANTINE

    digest = hashlib.sha256(raw).hexdigest()
    if bronze.email_seen(conn, digest):
        return PROCESSED

    key = f"email/{received_at:%Y/%m}/{digest}.eml"
    storage.put(key, raw, "message/rfc822")
    subject = str(message["Subject"] or "") or None
    documents = documents_of(message)
    if not documents:
        body = body_text(message)
        if len(body) >= MIN_BODY_CHARS:
            documents = [(body.encode("utf-8"), text.CONTENT_TYPE)]

    document_ids = []
    for content, content_type in documents:
        item = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "content_type": content_type,
            "source_type": "email",
            "uploaded_by": UPLOADER,
            "uploaded_at": received_at.isoformat(),
            "purchased_by": settings.buyers.get(sender),
            "purchase_date": None,
            # A közös fizető, mint a feltöltés alapértéke; a silver nem enged üres fizetőt.
            "payer": "shared",
            "tags": subject_tags(subject),
            "group_id": None,
            "page_no": 1,
            "page_count": 1,
        }
        document_id = store(item, content)
        parse_pending(conn, bronze.group_of(conn, document_id))
        document_ids.append(document_id)

    bronze.insert_email(
        conn,
        {
            "sha256": digest,
            "object_key": key,
            "message_id": str(message["Message-ID"] or "").strip() or None,
            "from_address": sender,
            "to_addresses": to_addresses(message),
            "subject": subject,
            "sent_at": sent_at(message),
            "received_at": received_at,
            "auth": auth.as_json(),
            "document_ids": document_ids,
        },
    )
    if not document_ids:
        log.warning(
            "A levélben nincs számla (melléklet vagy elég hosszú törzs): %s", subject
        )
    return PROCESSED


# --- IMAP -------------------------------------------------------------------------------------


def imap_utf7(name: str) -> str:
    """A mappanév az IMAP módosított UTF-7 kódolásában (RFC 3501), pl. Karantén → Karant&AOk-n."""
    out: list[str] = []
    pending: list[str] = []

    def flush() -> None:
        if pending:
            encoded = base64.b64encode("".join(pending).encode("utf-16-be")).decode()
            out.append("&" + encoded.rstrip("=").replace("/", ",") + "-")
            pending.clear()

    for char in name:
        if 0x20 <= ord(char) <= 0x7E:
            flush()
            out.append("&-" if char == "&" else char)
        else:
            pending.append(char)
    flush()
    return "".join(out)


def quoted(name: str) -> str:
    return '"' + imap_utf7(name).replace("\\", "\\\\").replace('"', '\\"') + '"'


FETCH_META = re.compile(rb"RFC822\.SIZE (\d+)")


class ImapMailbox:
    """Csak olvasás és mappák közti mozgatás; a levél a fejléc-lekérdezéstől nem lesz olvasott."""

    def __init__(
        self, host: str, user: str, password: str, port: int = 993, timeout: int = 60
    ):
        self.host, self.user, self.password = host, user, password
        self.port, self.timeout = port, timeout
        self.conn: imaplib.IMAP4_SSL | None = None

    def __enter__(self) -> Self:
        self.conn = imaplib.IMAP4_SSL(
            self.host,
            self.port,
            ssl_context=ssl.create_default_context(),
            timeout=self.timeout,
        )
        self.conn.login(self.user, self.password)
        for folder in (PROCESSED, QUARANTINE):
            _, found = self.conn.list('""', quoted(folder))
            if not found or found == [None]:
                self.conn.create(quoted(folder))
        self.check(self.conn.select(INBOX))
        return self

    def __exit__(self, *_exc) -> None:
        if self.conn is not None:
            try:
                self.conn.logout()
            except MAIL_ERRORS:
                pass
            self.conn = None

    @staticmethod
    def check(response: tuple) -> list:
        status, data = response
        if status != "OK":
            raise imaplib.IMAP4.error(f"IMAP: {status} {data!r}")
        return data

    def uids(self) -> list[bytes]:
        data = self.check(self.conn.uid("SEARCH", None, "ALL"))
        return data[0].split() if data and data[0] else []

    def size(self, uid: bytes) -> int:
        data = self.check(self.conn.uid("FETCH", uid, "(RFC822.SIZE)"))
        match = FETCH_META.search(data[0] if isinstance(data[0], bytes) else data[0][0])
        return int(match.group(1)) if match else 0

    def fetch(self, uid: bytes) -> tuple[bytes, datetime]:
        data = self.check(self.conn.uid("FETCH", uid, "(INTERNALDATE BODY.PEEK[])"))
        meta, raw = next(item for item in data if isinstance(item, tuple))
        received = imaplib.Internaldate2tuple(meta)
        when = (
            datetime.fromtimestamp(time.mktime(received), UTC)
            if received
            else datetime.now(UTC)
        )
        return raw, when

    def move(self, uid: bytes, folder: str) -> None:
        if "MOVE" in self.conn.capabilities:
            self.check(self.conn.uid("MOVE", uid, quoted(folder)))
            return
        self.check(self.conn.uid("COPY", uid, quoted(folder)))
        self.check(self.conn.uid("STORE", uid, "+FLAGS", "(\\Deleted)"))
        self.check(self.conn.expunge())


class MailIntake:
    """A worker körébe illesztve: a megadott időközönként nézi a postafiókot."""

    def __init__(self, settings: MailSettings, mailbox_factory=None):
        self.settings = settings
        self.mailbox_factory = mailbox_factory or (
            lambda: ImapMailbox(settings.host, settings.user, settings.password)
        )
        self.next_run = 0.0

    def due(self) -> bool:
        return time.monotonic() >= self.next_run

    def run(
        self,
        conn: psycopg.Connection,
        storage,
        store: Store,
        report: Callable[[str], None],
    ) -> int:
        """A feldolgozott levelek száma; IMAP-hiba esetén a következő körben újra próbálja."""
        self.next_run = time.monotonic() + self.settings.poll_seconds
        done = 0
        try:
            with self.mailbox_factory() as mailbox:
                for uid in mailbox.uids():
                    report("download")
                    if mailbox.size(uid) > MAX_MESSAGE_BYTES:
                        log.warning("Túl nagy levél, karantén: UID %s", uid.decode())
                        mailbox.move(uid, QUARANTINE)
                        continue
                    raw, received_at = mailbox.fetch(uid)
                    try:
                        folder = handle(
                            conn, storage, store, raw, received_at, self.settings
                        )
                    except (*TRANSIENT, ModelMissing):
                        raise
                    except Exception:
                        # Egy hibás levél nem akaszthatja meg a többit; a karanténból kézzel nézhető.
                        log.exception(
                            "A levél nem dolgozható fel, karantén: UID %s", uid.decode()
                        )
                        folder = QUARANTINE
                    mailbox.move(uid, folder)
                    done += 1
        except MAIL_ERRORS as error:
            log.error("A postafiók most nem olvasható: %s", error)
        finally:
            report("idle")
        return done
