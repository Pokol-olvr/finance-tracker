"""Kiadások: dokumentumok, lefúrás a tételekig, onnan az Ellenőrzés képernyőre."""

import os

import pandas as pd
import streamlit as st

from app import data
from app import format as fmt
from app.views import common


def document_table(frame: pd.DataFrame) -> list[int]:
    table = pd.DataFrame(
        {
            "Dátum": frame["occurred_on"].astype(str),
            "Bolt": frame["store_name"].fillna("Névtelen dokumentum"),
            "Ki fizetett": frame["payer"].map(fmt.payer_label),
            "Tételek": frame["item_count"],
            "Végösszeg": frame["total"].map(fmt.money),
        }
    )
    event = st.dataframe(
        table, hide_index=True, on_select="rerun", selection_mode="single-row", key="documents",
        column_config={"Végösszeg": st.column_config.TextColumn(alignment="right")},
    )
    return event.selection.rows


def item_table(frame: pd.DataFrame) -> None:
    table = pd.DataFrame(
        {
            "Tétel": frame["name"],
            "Mennyiség": [
                fmt.quantity(amount, unit)
                for amount, unit in zip(frame["quantity"], frame["unit"], strict=True)
            ],
            "Típus": frame["kind"].map(fmt.KIND_LABELS),
            "Kategória": frame["category"].fillna("–"),
            "Érték": frame["value"].map(fmt.money),
        }
    )
    st.dataframe(
        table, hide_index=True,
        column_config={"Érték": st.column_config.TextColumn(alignment="right")},
    )


def details(row: pd.Series) -> None:
    st.subheader(row["store_name"] or "Névtelen dokumentum")
    st.caption(f"{row['occurred_on']} · {fmt.money(row['total'])}")
    item_table(data.document_items(row["group_id"]))
    st.link_button(
        "Eredeti dokumentum megnyitása", f"{os.environ['WEBAPP_URL']}/review/{row['group_id']}"
    )


def render() -> None:
    st.title("Kiadások")
    payer = common.payer_filter("spending_payer")
    frame = data.documents(payer)
    if frame.empty:
        st.info("Még nincs beszámított dokumentum.")
        return
    st.caption("Válassz ki egy sort a tételekhez.")
    selected = document_table(frame)
    if selected:
        details(frame.iloc[selected[0]])
