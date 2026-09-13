import os

import pytest


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch, tmp_path):
    """Tests never call Gemini, OSRM, or Tiger Data."""
    monkeypatch.setenv("USE_OSRM", "false")
    monkeypatch.setenv("USE_GEMINI", "false")
    monkeypatch.setenv("USE_TIGER", "false")
    monkeypatch.setenv("TICK_MS", "10")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TIGER_DB_URL", raising=False)
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "rumbo-auth.sqlite3"))
