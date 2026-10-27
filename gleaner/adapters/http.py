"""Shared HTTP client: identifying User-Agent and a per-host rate limit
(SPEC.md: Health checks — "Requests carry an identifying User-Agent and a
per-host rate limit"). One process runs one source fetch at a time (systemd
timers, not concurrent workers), so a simple last-request-time dict is
enough; no locking needed.
"""
from __future__ import annotations

import time
from urllib.parse import urlsplit

import requests

USER_AGENT = "GleanerBot/0.1 (+personal information monitor; contact: operator)"
MIN_SECONDS_BETWEEN_REQUESTS_PER_HOST = 2.0
DEFAULT_TIMEOUT_SECONDS = 20

_last_request_at: dict[str, float] = {}


def _rate_limit(host: str) -> None:
    last = _last_request_at.get(host)
    if last is not None:
        elapsed = time.monotonic() - last
        remaining = MIN_SECONDS_BETWEEN_REQUESTS_PER_HOST - elapsed
        if remaining > 0:
            time.sleep(remaining)
    _last_request_at[host] = time.monotonic()


def get(url: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> requests.Response:
    host = urlsplit(url).netloc
    _rate_limit(host)
    return requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
        allow_redirects=True,
    )
