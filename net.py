"""Polite HTTP fetches. 403/404 are skipped; other failures are logged."""

from __future__ import annotations

from collections.abc import Callable

import requests

from config import REQUEST_TIMEOUT, USER_AGENT, request_delay

LogFn = Callable[[str], None]

SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT


def _sleep() -> None:
    delay = request_delay()
    if delay > 0:
        import time

        time.sleep(delay)


def fetch(
    url: str,
    log: LogFn | None = None,
    *,
    stream: bool = False,
    timeout: int | None = None,
) -> requests.Response | None:
    _sleep()
    try:
        response = SESSION.get(
            url,
            timeout=timeout or REQUEST_TIMEOUT,
            stream=stream,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        if log:
            log(f"request failed {url}: {exc}")
        return None
    if response.status_code in (403, 404):
        if log:
            log(f"{response.status_code} {url}")
        return None
    if response.status_code >= 400:
        if log:
            log(f"HTTP {response.status_code} {url}")
        return None
    return response
