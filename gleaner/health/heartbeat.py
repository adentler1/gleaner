"""External dead-man ping, sent after every completed run cycle (SPEC.md:
Health checks). Deliberately provider-agnostic: a plain HTTP GET is the
contract every heartbeat-style service (healthchecks.io, Better Stack,
UptimeRobot heartbeat, ...) accepts on its ping URL, so picking a provider
is a configuration decision, not a code change.
"""
from __future__ import annotations

import requests


def ping(url: str, *, timeout: int = 10) -> bool:
    try:
        response = requests.get(url, timeout=timeout)
    except Exception:
        return False
    return response.status_code < 400
