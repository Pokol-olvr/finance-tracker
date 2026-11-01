"""Minden helyben marad: a két beállítás nélkül a Streamlit külső szolgáltatást hívna."""

import tomllib
from pathlib import Path

CONFIG = Path(__file__).parents[1] / ".streamlit" / "config.toml"


def settings() -> dict:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))


def test_usage_statistics_are_off():
    assert settings()["browser"]["gatherUsageStats"] is False


def test_server_address_stops_the_external_lookup():
    assert settings()["browser"]["serverAddress"]


def test_error_details_stay_out_of_the_browser():
    assert settings()["client"]["showErrorDetails"] == "none"
