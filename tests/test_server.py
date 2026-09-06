from pathlib import Path

from PIL import Image
from fastapi.testclient import TestClient

import db


def _png_bytes(size=(500, 500)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, "purple").save(buf, format="PNG")
    return buf.getvalue()


def test_index_and_download_zip(isolated: Path):
    from server import create_app

    sid = db.insert_source("kept.example", "Kept", "https://kept.example/")
    db.set_tags(sid, ["zine"])
    cache = isolated / "cache" / "kept.example"
    cache.mkdir(parents=True)
    path = cache / "shot.png"
    path.write_bytes(_png_bytes())
    image_id = db.insert_image(
        sid,
        "https://kept.example/shot.png",
        str(path),
        500,
        500,
        "https://kept.example/post",
    )

    client = TestClient(create_app())
    page = client.get("/")
    assert page.status_code == 200
    assert b"good-form" in page.content
    assert b"kept.example" in page.content
    assert b"Hall of Fame" in page.content

    empty = client.post("/api/download", json={"ids": []})
    assert empty.status_code == 400

    zipped = client.post("/api/download", json={"ids": [image_id]})
    assert zipped.status_code == 200
    assert zipped.headers["content-type"].startswith("application/zip")
    assert db.get_source(sid)["downloads_count"] == 1
    assert db.get_image(image_id)["saved_count"] == 1

    fame = client.get("/")
    assert b"[1] kept.example" in fame.content
    assert b"1 saved" in fame.content

    enabled = client.post(f"/api/sources/{sid}/enabled", json={"enabled": False})
    assert enabled.status_code == 200
    assert db.get_source(sid)["enabled"] == 0

    one = client.get(f"/api/images/{image_id}/file?save=1")
    assert one.status_code == 200
    assert db.get_source(sid)["downloads_count"] == 2


def test_working_page_for_job(isolated: Path):
    from server import create_app

    job_id = db.create_job("discover")
    client = TestClient(create_app())
    page = client.get(f"/working/{job_id}")
    assert page.status_code == 200
    assert b"discover" in page.content
