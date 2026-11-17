"""Az oldalak a Streamlit saját tesztelőjével futnak, kitalált adatokkal."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

MAIN = str(Path(__file__).parents[1] / "app" / "main.py")


def run() -> AppTest:
    app = AppTest.from_file(MAIN, default_timeout=20).run()
    assert not app.exception
    return app


def test_overview_shows_this_month(gold):
    app = run()

    assert app.title[0].value == "Áttekintés"
    values = {metric.label: metric.value for metric in app.metric}
    assert values["Bevétel"] == "500 000 Ft"
    assert values["Kiadás"] == "250 000 Ft"
    assert values["Egyenleg"] == "250 000 Ft"
    assert values["Megtakarítási ráta"] == "50,0%"
    assert values["Várható betétdíj"] == "1 250 Ft"


def test_overview_warns_about_waiting_documents(gold):
    gold["pending"] = 2

    assert "2 dokumentum vár döntésre" in run().warning[0].value


def test_overview_is_quiet_without_waiting_documents(gold):
    assert not run().warning


def test_month_without_spending_says_so(gold):
    gold["categories"] = gold["categories"].iloc[0:0]

    assert "még nincs kiadás" in run().info[0].value


def spending_page():
    from app.views import spending

    spending.render()


def document_details():
    from app import data
    from app.views import spending

    spending.details(data.documents(None).iloc[0])


def test_spending_lists_documents(gold):
    app = AppTest.from_function(spending_page, default_timeout=20).run()

    assert not app.exception
    assert app.title[0].value == "Kiadások"
    assert len(app.dataframe) == 1
    assert not app.subheader


def test_empty_spending_page_explains_itself(gold):
    gold["documents"] = gold["documents"].iloc[0:0]

    app = AppTest.from_function(spending_page, default_timeout=20).run()

    assert not app.exception
    assert "Még nincs" in app.info[0].value


def test_details_show_items_and_the_way_to_the_original(gold):
    app = AppTest.from_function(document_details, default_timeout=20).run()

    assert not app.exception
    assert app.subheader[0].value == "Kitalált Élelmiszer Kft."
    table = app.dataframe[0].value
    assert table["Típus"].tolist() == ["tétel", "betétdíj"]
    assert table["Érték"].tolist() == ["599 Ft", "50 Ft"]
    assert table["Mennyiség"].tolist() == ["1 DB", "–"]


def prices_page():
    from app.views import prices

    prices.render()


def test_prices_show_the_change_since_the_first_month(gold):
    app = AppTest.from_function(prices_page, default_timeout=20).run()

    assert not app.exception
    assert app.title[0].value == "Árak"
    values = {metric.label: metric.value for metric in app.metric}
    assert values["Legutóbbi egységár"] == "1 150 Ft/kg"
    assert values["Legolcsóbb"] == "1 000 Ft/kg"
    assert values["Változás az első hónap óta"] == "15,0%"
    assert len(app.dataframe[0].value) == 3


def test_prices_explain_how_products_appear(gold):
    gold["products"] = gold["products"].iloc[0:0]

    app = AppTest.from_function(prices_page, default_timeout=20).run()

    assert not app.exception
    assert "termékszabály" in app.info[0].value


def test_item_table_shows_product_and_unit_price(gold):
    app = AppTest.from_function(document_details, default_timeout=20).run()

    table = app.dataframe[0].value
    assert table["Termék"].tolist() == ["kenyér", "–"]
    assert table["Egységár"].tolist() == ["1 198 Ft/kg", "–"]

