"""A levél törzséből jött e-nyugta (FIN-307); a szövegek kitaláltak, a valódiak szerkezetét követik."""

from app.document_parser import parse_document
from app.email_receipt import parse_email_receipt
from app.receipt_checks import run_checks, status_of

SUBSCRIPTION = """Kibocsátó: Példa Előfizetés
Számla
2026. november 11.
Sorszám:
1-10000000001
Megrendelésazonosító:
ABCDEF1234
Fiók:
valaki@example.test
Tárhely
Tárhely 50 GB (Havi)
Megújul: 2026. december 12.
399 Ft
Áfával, mértéke: 27%85 Ft
Számlázás és fizetés
Példa Vevő
Részösszeg
314 Ft
Áfa mértéke: 27%
85 Ft
------------------------------
Mastercard •••• 0000 (Apple Pay)
399 Ft
Ha kérdése van a számlával kapcsolatban, vegye fel a kapcsolatot a támogatással.
"""

ORDER = """Kibocsátó: Példa Bútor
Kedves Vásárló
Örömmel értesítjük, hogy a 4100000000 azonosítószámú megrendelés átvételre kész.
Állítható
asztal PÉLDA 70x140 fekete
Termék: 3600000
Mennyiség
1 db
Egységár
109900 Ft
37500 Ft
Összesen 37500 Ft
Összesen 37500 Ft
ÁFA 7972 Ft
Üdvözlettel,
Példa Bútor
"""


def test_subscription_receipt_total_comes_from_the_card_payment():
    parsed = parse_email_receipt(SUBSCRIPTION)

    assert parsed["store_name"] == "Példa Előfizetés"
    assert parsed["total"] == 399
    assert [(item["name"], item["value"]) for item in parsed["items"]] == [("Tárhely 50 GB (Havi)", 399)]
    assert parsed["purchased_on"] == "2026-11-11"
    assert parsed["receipt_number"] == "1-10000000001"
    assert parsed["inferred"] is True


def test_order_total_comes_from_the_label_and_the_name_skips_quantity_and_price():
    parsed = parse_email_receipt(ORDER)

    assert parsed["total"] == 37500
    assert parsed["items"][0]["name"] == "asztal PÉLDA 70x140 fekete"
    assert parsed["purchased_on"] is None


def test_unknown_issuer_leaves_the_store_empty():
    parsed = parse_email_receipt(ORDER.replace("Kibocsátó: Példa Bútor", "Kibocsátó: ismeretlen"))

    assert parsed["store_name"] is None


def test_only_email_bodies_and_only_with_a_total():
    assert parse_email_receipt(ORDER.split("\n", 1)[1]) is None
    assert parse_email_receipt("Kibocsátó: Valaki\nKöszönjük a megrendelést!\nHamarosan szállítjuk.") is None


def test_inferred_receipt_always_goes_to_review():
    parsed = parse_document([SUBSCRIPTION])
    checks = run_checks(parsed, None, False)

    assert parsed["document_type"] == "receipt"
    assert checks["inferred"] == {"ok": False}
    assert status_of(parsed, checks) == "review"


def test_regular_receipt_is_not_inferred():
    receipt = "Kibocsátó: Bolt\nNYUGTA\nC00 KENYÉR 500G 599\nÖSSZESEN: 599 FT\n"

    assert "inferred" not in parse_document([receipt])


def test_unparsed_email_body_gets_the_issuer_as_store_name():
    plain = "Kibocsátó: Példa Szolgáltató\nKöszönjük a regisztrációt!\nÜdvözlettel"
    unknown = "Kibocsátó: ismeretlen\nKöszönjük a regisztrációt!\nÜdvözlettel"

    assert parse_document([plain])["store_name"] == "Példa Szolgáltató"
    assert parse_document([unknown])["store_name"] is None
