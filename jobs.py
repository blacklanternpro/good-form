"""Background jobs: insert a row, run a daemon thread, expose status for the working page."""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable

import db

Runner = Callable[[int], None]


def log(job_id: int, line: str, *, status: str | None = None) -> None:
    db.append_job_log(job_id, line, message=status or line)


def start_job(kind: str, runner: Runner) -> int:
    db.init_db()
    job_id = db.create_job(kind)

    def _run() -> None:
        try:
            runner(job_id)
            job = db.get_job(job_id)
            if job and job["status"] == "running":
                db.finish_job(job_id, "done", job.get("message") or f"{kind} finished")
        except Exception as exc:
            tb = traceback.format_exc(limit=4)
            log(job_id, tb)
            db.finish_job(job_id, "error", f"{kind} failed: {exc}")

    thread = threading.Thread(target=_run, name=f"goodform-{kind}-{job_id}", daemon=True)
    thread.start()
    return job_id
