from pathlib import Path

from PIL import Image

import db


def _write_png(path: Path, size: tuple[int, int] = (500, 500)) -> None:
    Image.new("RGB", size, "green").save(path, format="PNG")


def test_zip_increments_saved_and_source_counts(isolated: Path):
    source_id = db.insert_source("zine.example", "Zine", "https://zine.example/")
    db.set_tags(source_id, ["zine"])
    cache = isolated / "cache" / "zine.example"
    cache.mkdir(parents=True)
    one = cache / "a.png"
    two = cache / "b.png"
    _write_png(one)
    _write_png(two)
    id_a = db.insert_image(source_id, "https://zine.example/a.png", str(one), 500, 500, "https://zine.example/post")
    id_b = db.insert_image(source_id, "https://zine.example/b.png", str(two), 500, 500, "https://zine.example/post")
    assert db.hall_of_fame() == []

    updated = db.record_downloads([id_a, id_b])
    assert updated == 2
    source = db.get_source(source_id)
    assert source["downloads_count"] == 2
    assert db.get_image(id_a)["saved_count"] == 1
    fame = db.hall_of_fame()
    assert fame[0]["domain"] == "zine.example"
    assert fame[0]["downloads_count"] == 2


def test_hall_of_fame_ignores_scraped_only_domains(isolated: Path):
    sid = db.insert_source("dud.example", "Dud", "https://dud.example/")
    cache = isolated / "cache" / "dud.example"
    cache.mkdir(parents=True)
    path = cache / "x.png"
    _write_png(path)
    db.insert_image(sid, "https://dud.example/x.png", str(path), 500, 500, "https://dud.example/")
    assert db.hall_of_fame() == []
    other = db.insert_source("kept.example", "Kept", "https://kept.example/")
    kcache = isolated / "cache" / "kept.example"
    kcache.mkdir(parents=True)
    kpath = kcache / "k.png"
    _write_png(kpath)
    kid = db.insert_image(other, "https://kept.example/k.png", str(kpath), 500, 500, "https://kept.example/")
    db.record_downloads([kid])
    fame = db.hall_of_fame()
    assert [row["domain"] for row in fame] == ["kept.example"]
