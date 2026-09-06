from io import BytesIO

from PIL import Image

import db
from scraper import harvest_source
from tests.conftest import FakeResp


FEED = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Zine</title>
    <item>
      <title>Post</title>
      <link>https://zine.example/post</link>
      <description><![CDATA[<img src="https://zine.example/tiny.png">]]></description>
      <enclosure url="https://zine.example/good.png" type="image/png"/>
    </item>
  </channel>
</rss>
"""


def _png(size) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, "navy").save(buf, format="PNG")
    return buf.getvalue()


def test_harvest_keeps_feed_enclosure_above_threshold(isolated):
    sid = db.insert_source("zine.example", "Zine", "https://zine.example/")
    db.set_feed_url(sid, "https://zine.example/feed")
    source = db.get_source(sid)

    tiny = _png((50, 50))
    good = _png((640, 800))

    def fetch_fn(url, log=None):
        if url.endswith("/feed"):
            return FakeResp(FEED, url=url, headers={"Content-Type": "application/rss+xml"})
        if url.endswith("tiny.png"):
            return FakeResp(content=tiny, url=url, headers={"Content-Type": "image/png"})
        if url.endswith("good.png"):
            return FakeResp(content=good, url=url, headers={"Content-Type": "image/png"})
        return None

    added = harvest_source(source, fetch_fn=fetch_fn)
    assert added == 1
    images = db.list_images()
    assert images[0]["width"] == 640
    assert images[0]["height"] == 800
    assert images[0]["saved_count"] == 0
    assert "zine.example" in images[0]["cache_path"]
