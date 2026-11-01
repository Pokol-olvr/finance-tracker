"""A gold olvasása. A riportfelület mást nem ér el, és a kapcsolata is csak olvasható."""

import os
from decimal import Decimal

import pandas as pd
import psycopg
import streamlit as st

# A dbt óránként fut, ennél gyakrabban nem változnak a számok.
CACHE_SECONDS = 60


def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with (
        psycopg.connect(os.environ["DATABASE_URL"], options="-c default_transaction_read_only=on") as conn,
        conn.cursor() as cursor,
    ):
        cursor.execute(sql, params)
        columns = [column.name for column in cursor.description]
        rows = cursor.fetchall()
    frame = pd.DataFrame(rows, columns=columns)
    for column in columns:
        if frame[column].map(lambda value: isinstance(value, Decimal)).any():
            frame[column] = frame[column].astype(float)
    return frame


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    return run_query(sql, params)


def payers() -> list[str]:
    return query("select distinct payer from gold.monthly_cash_flow order by payer")["payer"].tolist()


def monthly(payer: str | None) -> pd.DataFrame:
    """Havi bevétel és kiadás, fizető fél nélkül a teljes háztartásé."""
    return query(
        "select month, sum(income) as income, sum(expense) as expense "
        "from gold.monthly_cash_flow where (%s::text is null or payer = %s) "
        "group by month order by month",
        (payer, payer),
    )


def categories(month: object, payer: str | None) -> pd.DataFrame:
    return query(
        "select category, sum(expense) as expense from gold.category_month "
        "where month = %s and (%s::text is null or payer = %s) "
        "group by category order by 2 desc",
        (month, payer, payer),
    )


def pending_documents() -> int:
    frame = query(
        "select coalesce(sum(document_count), 0) as waiting "
        "from gold.document_states where state = 'pending'"
    )
    return int(frame["waiting"].iloc[0])


def expected_deposit() -> float:
    return float(query("select balance from gold.expected_deposit")["balance"].iloc[0])


def documents(payer: str | None) -> pd.DataFrame:
    return query(
        "select group_id::text as group_id, occurred_on, store_name, payer, item_count, total "
        "from gold.expense_documents where (%s::text is null or payer = %s) "
        "order by occurred_on desc, store_name",
        (payer, payer),
    )


def document_items(group_id: str) -> pd.DataFrame:
    return query(
        "select name, kind, category, quantity, unit, value from gold.expense_items "
        "where group_id = %s order by line_no",
        (group_id,),
    )
