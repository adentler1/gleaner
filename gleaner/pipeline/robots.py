"""robots.txt check, honoured automatically (SPEC.md: Health checks).
A disallowed source gets the health state 'blocked'; the runner checks this
before fetching, so the adapter itself never needs to know about robots.txt.
"""
from __future__ import annotations

from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from gleaner.adapters import http
from gleaner.adapters.http import USER_AGENT


def is_allowed(url: str) -> bool:
    """Returns False only on an explicit robots.txt disallow. A robots.txt
    that is missing or unreachable is treated as allowed — a transport
    problem on robots.txt itself is not grounds to block a source, and will
    surface as its own transport failure on the real fetch if the host is
    actually down.

    Fetches robots.txt through our own identified HTTP client rather than
    RobotFileParser.read()'s default urllib opener: a WAF that 403s the
    generic "Python-urllib/3.x" User-Agent (common) makes robotparser treat
    the whole site as disallowed, even when robots.txt itself is permissive
    for an identified bot — a false "blocked" that's worse than useless."""
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    parser = RobotFileParser()
    try:
        response = http.get(robots_url)
    except Exception:
        return True
    if response.status_code >= 400:
        return True
    parser.parse(response.text.splitlines())
    return parser.can_fetch(USER_AGENT, url)
