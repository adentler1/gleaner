"""robots.txt check, honoured automatically (SPEC.md: Health checks).
A disallowed source gets the health state 'blocked'; the runner checks this
before fetching, so the adapter itself never needs to know about robots.txt.
"""
from __future__ import annotations

from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from gleaner.adapters.http import USER_AGENT


def is_allowed(url: str) -> bool:
    """Returns False only on an explicit robots.txt disallow. A robots.txt
    that is missing or unreachable is treated as allowed — a transport
    problem on robots.txt itself is not grounds to block a source, and will
    surface as its own transport failure on the real fetch if the host is
    actually down."""
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:
        return True
    return parser.can_fetch(USER_AGENT, url)
