from io import BytesIO

from PIL import Image

from scraper import image_passes_bytes, largest_srcset, url_is_rejected


def _png(width: int, height: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), "blue").save(buf, format="PNG")
    return buf.getvalue()


def test_rejects_svg_data_and_ad_urls():
    assert url_is_rejected("data:image/png;base64,xxxx")
    assert url_is_rejected("https://cdn.example/icon.svg")
    assert url_is_rejected("https://doubleclick.net/track.gif")
    assert url_is_rejected("https://example.com/pixel/foo.png")
    assert not url_is_rejected("https://zine.example/photos/scan.jpg")


def test_minimum_short_edge():
    ok, w, h = image_passes_bytes(_png(100, 100))
    assert not ok
    assert (w, h) == (100, 100)
    ok, w, h = image_passes_bytes(_png(500, 500))
    assert ok
    assert (w, h) == (500, 500)


def test_rejects_extreme_aspect_ratios():
    assert not image_passes_bytes(_png(1200, 100))[0]
    assert not image_passes_bytes(_png(100, 1200))[0]
    assert image_passes_bytes(_png(900, 400))[0]


def test_rejects_svg_payload():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800"></svg>'
    assert not image_passes_bytes(svg, "icon.svg")[0]


def test_largest_srcset_picks_widest():
    chosen = largest_srcset("a.jpg 400w, b.jpg 800w, c.jpg 200w")
    assert chosen == "b.jpg"
