from pathlib import Path

from PIL import Image

import db
from sources import SerpApiError, run_discover, run_hop


def _png(path: Path) -> None:
    Image.new("RGB", (20, 20), "red").save(path, format="PNG")


def test_discover_falls_back_after_serpapi_error(isolated: Path, monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    seed = isolated / "seeds" / "vaporwave_zine.png"
    _png(seed)

    def boom(_data: bytes):
        raise SerpApiError("Your account has run out of searches.", 429)

    def web(_query: str):
        return [
            {"title": "Neon Diary", "url": "https://neon-diary.neocities.org/", "snippet": "zine"},
            {"title": "Amazon", "url": "https://www.amazon.com/foo", "snippet": ""},
        ]

    job_id = db.create_job("discover")
    run_discover(job_id, lens_search=boom, web_search=web, seeds=[seed])
    job = db.get_job(job_id)
    assert "429" in (job["log"] or "")
    assert db.get_source_by_domain("neon-diary.neocities.org") is not None
    assert db.get_source_by_domain("amazon.com") is None
    assert db.get_source_by_domain("www.amazon.com") is None


def test_discover_empty_seeds_does_not_crash(isolated: Path):
    job_id = db.create_job("discover")
    run_discover(job_id, seeds=[])
    job = db.get_job(job_id)
    assert "No images" in (job["message"] or "")


def test_hop_prefers_dud_unsaved_not_yet_hopped_and_respects_cap(isolated: Path, monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    dud = db.insert_source("dud.example", "Dud", "https://dud.example/")
    star = db.insert_source("star.example", "Star", "https://star.example/")
    db.set_tags(dud, ["zine"])
    db.set_tags(star, ["zine"])
    cache = isolated / "cache"
    ids = []
    for index in range(4):
        path = cache / "dud.example" / f"{index}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (500 + index, 500), "blue").save(path)
        ids.append(
            db.insert_image(
                dud,
                f"https://dud.example/{index}.png",
                str(path),
                500 + index,
                500,
                "https://dud.example/post",
            )
        )
    star_path = cache / "star.example" / "s.png"
    star_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 800), "blue").save(star_path)
    star_img = db.insert_image(
        star,
        "https://star.example/s.png",
        str(star_path),
        800,
        800,
        "https://star.example/post",
    )
    db.record_downloads([star_img])
    with db.connect() as conn:
        conn.execute("UPDATE images SET saved_count = 1 WHERE id = ?", (ids[0],))
    db.mark_hopped(ids[1])

    job_id = db.create_job("hop")
    run_hop(
        job_id,
        lens_search=lambda _data: [{"title": "Peer", "url": "https://peer.neocities.org/", "snippet": ""}],
        cap=1,
    )

    assert db.get_image(ids[0])["hopped_at"] is None
    assert db.get_image(ids[1])["hopped_at"] is not None
    hopped_new = [i for i in ids[2:] if db.get_image(i)["hopped_at"] is not None]
    assert len(hopped_new) == 1
    assert db.get_image(star_img)["hopped_at"] is None
    assert db.get_source_by_domain("peer.neocities.org") is not None
    edges = db.list_edges()
    assert any(e["via_type"] == "image_lens" for e in edges)
    assert db.get_source_by_domain("peer.neocities.org")["downloads_count"] == 0


def test_text_hop_when_no_serpapi_key(isolated: Path):
    dud = db.insert_source("bridge.example", "Bridge zine", "https://bridge.example/vaporwave")
    db.set_tags(dud, ["vaporwave"])
    path = isolated / "cache" / "bridge.example" / "x.png"
    path.parent.mkdir(parents=True)
    Image.new("RGB", (500, 600), "blue").save(path)
    image_id = db.insert_image(
        dud,
        "https://bridge.example/x.png",
        str(path),
        500,
        600,
        "https://bridge.example/vaporwave/post",
    )
    job_id = db.create_job("hop")
    run_hop(
        job_id,
        web_search=lambda q: [{"title": "Found", "url": "https://found.neocities.org/", "snippet": ""}],
        cap=1,
    )
    assert db.get_image(image_id)["hopped_at"] is not None
    assert db.get_source_by_domain("found.neocities.org") is not None
    assert any(e["via_type"] == "text_search" for e in db.list_edges())
