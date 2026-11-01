"""Áttekintés: ez a hónap az előzőhöz és az átlaghoz képest."""

from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from app import data, metrics
from app import format as fmt
from app.views import common


def delta(current: float | None, previous: float | None) -> str | None:
    if current is None or previous is None:
        return None
    return fmt.money(current - previous)


def key_numbers(rows: list[dict]) -> None:
    this_month, last_month = rows[0], rows[1]
    income, expense = this_month["income"], this_month["expense"]
    balance = None if income is None else income - expense
    before = None if last_month["income"] is None else last_month["income"] - last_month["expense"]
    columns = st.columns(5)
    columns[0].metric("Bevétel", fmt.money(income), delta(income, last_month["income"]), border=True)
    columns[1].metric(
        "Kiadás", fmt.money(expense), delta(expense, last_month["expense"]),
        delta_color="inverse", border=True,
    )
    columns[2].metric("Egyenleg", fmt.money(balance), delta(balance, before), border=True)
    columns[3].metric("Megtakarítási ráta", fmt.percent(metrics.savings_rate(income, expense)), border=True)
    columns[4].metric(
        "Várható betétdíj", fmt.money(data.expected_deposit()), border=True,
        help="DRS-betétdíj, amely visszaváltáskor jön vissza; nem kiadás.",
    )


def comparison_table(rows: list[dict]) -> None:
    table = pd.DataFrame(
        [
            {
                "Időszak": row["period"],
                "Bevétel": fmt.money(row["income"]),
                "Kiadás": fmt.money(row["expense"]),
                "Egyenleg": fmt.money(
                    None if row["income"] is None else row["income"] - row["expense"]
                ),
                "Megtakarítási ráta": fmt.percent(metrics.savings_rate(row["income"], row["expense"])),
            }
            for row in rows
        ]
    )
    right = st.column_config.TextColumn(alignment="right")
    st.dataframe(
        table, hide_index=True,
        column_config={name: right for name in table.columns if name != "Időszak"},
    )


def category_chart(frame: pd.DataFrame) -> None:
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadiusEnd=4, color="#1f6f54")
        .encode(
            x=alt.X("expense:Q", title=None, axis=alt.Axis(labelExpr=fmt.AXIS_NUMBER)),
            y=alt.Y("category:N", title=None, sort="-x"),
            tooltip=[
                alt.Tooltip("category:N", title="Kategória"),
                alt.Tooltip("expense:Q", title="Kiadás", format=",.0f"),
            ],
        )
        .properties(height=max(120, 40 * len(frame)))
    )
    st.altair_chart(chart, width="stretch")


def render() -> None:
    st.title("Áttekintés")
    payer = common.payer_filter("overview_payer")
    month = metrics.first_of_month(date.today())
    st.caption(f"Ez a hónap: {month:%Y-%m}")

    waiting = data.pending_documents()
    if waiting:
        st.warning(f"{waiting} dokumentum vár döntésre, ezek még nem számítanak a kiadásba.")

    rows = metrics.comparison(data.monthly(payer), month)
    key_numbers(rows)

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Összehasonlítás")
        comparison_table(rows)
    with right:
        st.subheader("Kiadás kategóriánként")
        spending = data.categories(month, payer)
        if spending.empty:
            st.info("Ebben a hónapban még nincs kiadás.")
        else:
            category_chart(spending)
