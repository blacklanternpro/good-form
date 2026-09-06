from pathlib import Path

from fallback import build_queries, filter_hits, parse_ddg_html, search_web, tokenize_filename, unwrap_ddg_href


FIXTURE = Path(__file__).parent / "fixtures" / "ddg.html"


def test_tokenize_and_query_builder_subtracts_aggregators():
    tokens = tokenize_filename("vaporwave_zine_scan.jpg")
    assert "vaporwave" in tokens
    queries = build_queries(tokens, ["vaporwave", "Unsorted"])
    assert queries
    assert any("personal blog" in q for q in queries)
    assert any("site:tumblr.com" in q for q in queries)
    assert all("-pinterest" in q for q in queries)
    assert all("Unsorted" not in q for q in queries)


def test_parse_ddg_html_unwraps_uddg():
    html = FIXTURE.read_text(encoding="utf-8")
    hits = parse_ddg_html(html)
    urls = [h["url"] for h in hits]
    assert "https://neon-diary.neocities.org/" in urls
    assert "https://cool-scans.tumblr.com/post/1" in urls
    assert unwrap_ddg_href("https://duckduckgo.com/l/?uddg=https%3A%2F%2Fx.example%2F") == "https://x.example/"


def test_filter_hits_drops_blacklist():
    hits = [
        {"title": "Pin", "url": "https://www.pinterest.com/pin/1", "snippet": ""},
        {"title": "Zine", "url": "https://neon-diary.neocities.org/", "snippet": ""},
    ]
    kept = filter_hits(hits)
    assert [h["host"] for h in kept] == ["neon-diary.neocities.org"]


def test_brave_preferred_then_ddg(isolated, monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-test-key")
    called = {"brave": 0, "ddg": 0}

    def brave(_query: str):
        called["brave"] += 1
        return [{"title": "A", "url": "https://a.neocities.org/", "snippet": ""}]

    def ddg(_query: str):
        called["ddg"] += 1
        return [{"title": "B", "url": "https://b.neocities.org/", "snippet": ""}]

    hits = search_web("vaporwave personal blog", brave_fn=brave, ddg_fn=ddg)
    assert called["brave"] == 1
    assert called["ddg"] == 0
    assert hits[0]["url"].endswith("a.neocities.org/")


def test_ddg_used_when_brave_empty(isolated, monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-test-key")
    called = {"ddg": 0}

    def brave(_query: str):
        return []

    def ddg(_query: str):
        called["ddg"] += 1
        return [{"title": "B", "url": "https://b.neocities.org/", "snippet": ""}]

    hits = search_web("q", brave_fn=brave, ddg_fn=ddg)
    assert called["ddg"] == 1
    assert hits[0]["title"] == "B"
