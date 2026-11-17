"""Árak: egy termék egységára havonta és boltonként, a személyes inflációhoz (ADR 0015)."""

import altair as alt
import pandas as pd
import streamlit as st

from app import data
from app import format as fmt

UNIT_LABELS = {"kg": "Ft/kg", "l": "Ft/l", "db": "Ft/db"}


def product_label(row: pd.Series) -> str:
    return f"{row['product']} ({row['category']} › {row['product_family']}, {UNIT_LABELS[row['base_unit']]})"


def monthly_average(frame: pd.DataFrame) -> pd.DataFrame:
    """Boltoktól függetlenül, mennyiséggel súlyozva: a nagy kiszerelés nem torzít."""
    weighted = frame.assign(spent=frame["unit_price"] * frame["quantity"])
    months = weighted.groupby("month", as_index=False)[["spent", "quantity"]].sum()
    return months.assign(unit_price=months["spent"] / months["quantity"])


def change_since_first(months: pd.DataFrame) -> float | None:
    if len(months) < 2:
        return None
    first, last = months["unit_price"].iloc[0], months["unit_price"].iloc[-1]
    return (last / first - 1) * 100 if first else None


def price_chart(frame: pd.DataFrame, unit: str) -> None:
    chart = (
        alt.Chart(frame)
        .mark_line(point=True)
        .encode(
            x=alt.X("month:T", title=None, axis=alt.Axis(format="%Y. %m.")),
            y=alt.Y("unit_price:Q", title=unit, axis=alt.Axis(labelExpr=fmt.AXIS_NUMBER)),
            color=alt.Color("store_name:N", title="Bolt"),
            tooltip=[
                alt.Tooltip("month:T", title="Hónap", format="%Y. %m."),
                alt.Tooltip("store_name:N", title="Bolt"),
                alt.Tooltip("unit_price:Q", title=unit, format=",.0f"),
            ],
        )
    )
    st.altair_chart(chart, width="stretch")


def price_table(frame: pd.DataFrame, unit: str) -> None:
    table = pd.DataFrame(
        {
            "Hónap": pd.to_datetime(frame["month"]).dt.strftime("%Y. %m."),
            "Bolt": frame["store_name"].fillna("–"),
            unit: frame["unit_price"].map(fmt.money),
            "Legolcsóbb": frame["min_unit_price"].map(fmt.money),
            "Legdrágább": frame["max_unit_price"].map(fmt.money),
            "Vásárlás": frame["purchase_count"],
        }
    )
    st.dataframe(
        table, hide_index=True,
        column_config={
            column: st.column_config.TextColumn(alignment="right")
            for column in (unit, "Legolcsóbb", "Legdrágább")
        },
    )


def render() -> None:
    st.title("Árak")
    products = data.products()
    if products.empty:
        st.info(
            "Még nincs termékre sorolt tétel. A Szabályok oldalon felvett termékszabály után "
            "a következő óránkénti frissítéssel jelenik meg."
        )
        return
    labels = products.apply(product_label, axis=1).tolist()
    chosen = st.selectbox("Termék", range(len(labels)), format_func=lambda index: labels[index])
    product = products.iloc[chosen]
    unit = UNIT_LABELS[product["base_unit"]]
    frame = data.product_prices(product["product"], product["base_unit"])
    months = monthly_average(frame)

    latest, cheapest, change = st.columns(3)
    latest.metric("Legutóbbi egységár", f"{fmt.money(months['unit_price'].iloc[-1])}/{product['base_unit']}")
    cheapest.metric("Legolcsóbb", f"{fmt.money(frame['min_unit_price'].min())}/{product['base_unit']}")
    change.metric("Változás az első hónap óta", fmt.percent(change_since_first(months)))
    price_chart(frame, unit)
    price_table(frame, unit)
