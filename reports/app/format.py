"""Magyar számformátum: szóközös ezres tagolás, a beépített elemek nem tudják."""

import pandas as pd

# Vega-kifejezés a diagramok tengelyéhez.
AXIS_NUMBER = "replace(format(datum.value, ','), /,/g, ' ')"
PAYER_LABELS = {"shared": "Közös kártya"}
KIND_LABELS = {"item": "tétel", "deposit": "betétdíj", "discount": "kedvezmény", "voucher": "utalvány"}


def number(value: float | None, decimals: int = 0) -> str:
    if value is None or pd.isna(value):
        return "–"
    text = f"{value:,.{decimals}f}".replace(",", " ")
    return text.replace(".", ",")


def money(value: float | None) -> str:
    text = number(value)
    return text if text == "–" else f"{text} Ft"


def percent(value: float | None) -> str:
    text = number(value, 1)
    return text if text == "–" else f"{text}%"


def quantity(amount: float | None, unit: str | None) -> str:
    if amount is None or pd.isna(amount):
        return "–"
    text = f"{amount:g}".replace(".", ",")
    return f"{text} {unit}" if unit else text


def payer_label(payer: str) -> str:
    return PAYER_LABELS.get(payer, payer)
