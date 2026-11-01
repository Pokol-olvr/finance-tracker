"""Az oldalak közös elemei."""

import streamlit as st

from app import data
from app import format as fmt

ALL_PAYERS = "Mindenki"


def payer_filter(key: str) -> str | None:
    """A fizető fél szűrője; `None`, ha a teljes háztartás kell."""
    options = [ALL_PAYERS, *data.payers()]
    chosen = st.segmented_control(
        "Ki fizetett?", options, default=ALL_PAYERS, key=key,
        format_func=lambda value: value if value == ALL_PAYERS else fmt.payer_label(value),
    )
    return None if chosen in (None, ALL_PAYERS) else chosen
