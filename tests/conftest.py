from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GOODFORM_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("GOODFORM_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("GOODFORM_SEED", str(tmp_path / "seeds"))
    monkeypatch.setenv("GOODFORM_DELAY", "0")
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    (tmp_path / "seeds").mkdir()
    (tmp_path / "cache").mkdir()
    import db

    db.init_db()
    return tmp_path


class FakeResp:
    def __init__(
        self,
        text: str = "",
        content: bytes | None = None,
        url: str = "https://example.test/",
        headers: dict | None = None,
        status_code: int = 200,
    ) -> None:
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")
        self.url = url
        self.headers = headers or {"Content-Type": "text/html"}
        self.status_code = status_code
