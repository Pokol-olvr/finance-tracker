"""Számítások a riportokhoz, Streamlit nélkül, hogy tesztelhetők legyenek."""

from datetime import date

import pandas as pd


def first_of_month(day: date) -> date:
    return day.replace(day=1)


def shift_month(month: date, months: int) -> date:
    index = month.year * 12 + month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def savings_rate(income: float | None, expense: float | None) -> float | None:
    """A megtakarítási ráta százalékban; bevétel nélkül nem értelmezhető."""
    if not income:
        return None
    return round((income - (expense or 0)) / income * 100, 1)


def month_row(frame: pd.DataFrame, month: date) -> dict:
    rows = frame[frame["month"] == month]
    if rows.empty:
        return {"income": None, "expense": None}
    return {"income": rows["income"].iloc[0], "expense": rows["expense"].iloc[0]}


def closed_average(frame: pd.DataFrame, month: date, months: int = 3) -> dict:
    """Az előző lezárt hónapok átlaga, a folyó hónap nélkül."""
    window = frame[(frame["month"] >= shift_month(month, -months)) & (frame["month"] < month)]
    if window.empty:
        return {"income": None, "expense": None}
    return {"income": window["income"].mean(), "expense": window["expense"].mean()}


def comparison(frame: pd.DataFrame, month: date) -> list[dict]:
    return [
        {"period": "Ez a hónap", **month_row(frame, month)},
        {"period": "Előző hónap", **month_row(frame, shift_month(month, -1))},
        {"period": "Előző 3 lezárt hónap átlaga", **closed_average(frame, month)},
    ]
