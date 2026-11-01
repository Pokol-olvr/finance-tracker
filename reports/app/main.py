"""A riportfelület belépési pontja. Csak megjelenít, adatbevitel a webappban történik."""

import os

import streamlit as st

from app.views import overview, spending

# A kártyák és a táblázatok így férnek el; a szépítés többi része a témában van.
STYLE = """
<style>
  [data-testid="stMainBlockContainer"] { padding-top: 3.5rem; max-width: 1200px; }
  h1 { font-size: 2rem !important; padding-top: 0 !important; }
</style>
"""

st.set_page_config(page_title="Riportok", layout="wide")
st.markdown(STYLE, unsafe_allow_html=True)
page = st.navigation(
    [
        st.Page(overview.render, title="Áttekintés", url_path="attekintes", default=True),
        st.Page(spending.render, title="Kiadások", url_path="kiadasok"),
    ],
    position="top",
)
webapp = os.environ["WEBAPP_URL"]
st.caption(
    f"[Feltöltés]({webapp}/) · [Ellenőrzés]({webapp}/review) · "
    f"[Szabályok]({webapp}/rules) · [Betétdíj]({webapp}/deposit) · [Állapot]({webapp}/status)"
)
page.run()
