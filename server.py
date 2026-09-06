"""FastAPI app: directory UI, jobs, zip downloads, Hall of Fame."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import db
import jobs as joblib
from config import GRID_LIMIT, ROOT, cache_dir, seed_dir
from harvester import run_mine
from scraper import run_scrape
from sources import run_discover, run_hop

templates = Jinja2Templates(directory=str(ROOT / "templates"))


class DownloadBody(BaseModel):
    ids: list[int] = Field(default_factory=list)


class EnabledBody(BaseModel):
    enabled: bool


def create_app() -> FastAPI:
    db.init_db()
    app = FastAPI(title="good-form")
    static_dir = ROOT / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        db.init_db()
        directory = db.sources_grouped_by_tag()
        images = db.list_images(limit=GRID_LIMIT)
        fame = db.hall_of_fame(50)
        seeds = [p.name for p in seed_dir().iterdir()] if seed_dir().is_dir() else []
        raster = [n for n in seeds if n.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "directory": directory,
                "images": images,
                "fame": fame,
                "seed_count": len(raster),
                "source_count": len(db.list_sources()),
            },
        )

    @app.get("/working/{job_id}", response_class=HTMLResponse)
    def working(request: Request, job_id: int) -> HTMLResponse:
        job = db.get_job(job_id)
        if job is None:
            raise HTTPException(404, "Unknown job")
        return templates.TemplateResponse(request, "working.html", {"job": job})

    def _kick(kind: str, runner) -> RedirectResponse:
        job_id = joblib.start_job(kind, runner)
        return RedirectResponse(url=f"/working/{job_id}", status_code=303)

    @app.post("/jobs/discover")
    def post_discover() -> RedirectResponse:
        return _kick("discover", run_discover)

    @app.post("/jobs/mine")
    def post_mine() -> RedirectResponse:
        return _kick("mine", run_mine)

    @app.post("/jobs/scrape")
    def post_scrape() -> RedirectResponse:
        return _kick("scrape", run_scrape)

    @app.post("/jobs/hop")
    def post_hop() -> RedirectResponse:
        return _kick("hop", run_hop)

    @app.post("/api/sources/{source_id}/enabled")
    def api_enabled(source_id: int, body: EnabledBody) -> dict:
        if db.get_source(source_id) is None:
            raise HTTPException(404, "Unknown source")
        db.set_enabled(source_id, body.enabled)
        return {"ok": True, "enabled": body.enabled}

    @app.post("/api/download")
    def api_download(body: DownloadBody) -> StreamingResponse:
        if not body.ids:
            raise HTTPException(400, "ids required")
        return _zip_images(body.ids)

    @app.get("/api/images/{image_id}/file")
    def api_image_file(image_id: int, save: int = 0):
        image = db.get_image(image_id)
        if image is None:
            raise HTTPException(404, "Unknown image")
        path = _safe_cache_path(image.get("cache_path"))
        if path is None:
            raise HTTPException(404, "File missing")
        if save:
            db.record_downloads([image_id])
        return FileResponse(
            path,
            filename=path.name,
            media_type="application/octet-stream",
        )

    @app.get("/media/{image_id}")
    def media(image_id: int):
        image = db.get_image(image_id)
        if image is None:
            raise HTTPException(404, "Unknown image")
        path = _safe_cache_path(image.get("cache_path"))
        if path is None:
            raise HTTPException(404, "File missing")
        return FileResponse(path)

    return app


def _safe_cache_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    path = Path(raw).resolve()
    root = cache_dir().resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path


def _zip_images(ids: list[int]) -> StreamingResponse:
    buffer = io.BytesIO()
    written_ids: list[int] = []
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        used_names: set[str] = set()
        for image_id in ids:
            image = db.get_image(image_id)
            if image is None:
                continue
            path = _safe_cache_path(image.get("cache_path"))
            if path is None:
                continue
            arcname = f"{image['domain']}/{path.name}"
            if arcname in used_names:
                arcname = f"{image['domain']}/{image_id}_{path.name}"
            used_names.add(arcname)
            archive.write(path, arcname=arcname)
            written_ids.append(image_id)
    if not written_ids:
        raise HTTPException(404, "No cached files for those ids")
    db.record_downloads(written_ids)
    buffer.seek(0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"goodform-{stamp}.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


app = create_app()
