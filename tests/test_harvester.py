from tests.conftest import FakeResp

import db
from harvester import run_mine


HOME = """
<html><body>
  <a href="/posts">Latest</a>
  <footer>
    <a href="https://friend.neocities.org/">Friend Zine</a>
  </footer>
  <a href="https://webring.example/join">webring</a>
</body></html>
"""

LINKS = """
<html><body>
  <ul>
    <li><a href="https://peer.neocities.org/about">Peer archive</a></li>
    <li><a href="https://www.pinterest.com/x">Pinterest</a></li>
    <li><a href="https://self.example/about">self</a></li>
  </ul>
</body></html>
"""


def test_mine_writes_link_edges_and_dedupes_blacklist(isolated):
    sid = db.insert_source("self.example", "Self", "https://self.example/")
    db.set_tags(sid, ["zine"])

    def fetch_fn(url, log=None):
        if url.rstrip("/").endswith("/links"):
            return FakeResp(LINKS, url="https://self.example/links")
        if "self.example" in url:
            return FakeResp(HOME, url="https://self.example/")
        return None

    job_id = db.create_job("mine")
    run_mine(job_id, fetch_fn=fetch_fn, cap=40)

    assert db.get_source_by_domain("friend.neocities.org") is not None
    assert db.get_source_by_domain("peer.neocities.org") is not None
    assert db.get_source_by_domain("pinterest.com") is None
    assert db.get_source_by_domain("webring.example") is not None
    edges = db.list_edges()
    assert edges
    assert all(e["via_type"] == "link" for e in edges)
    assert all(e["from_source_id"] == sid for e in edges)

    # second mine must not duplicate sources
    before = len(db.list_sources())
    run_mine(db.create_job("mine"), fetch_fn=fetch_fn, cap=40)
    assert len(db.list_sources()) == before
