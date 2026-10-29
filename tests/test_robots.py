from types import SimpleNamespace

from gleaner.pipeline import robots


def _fake_response(status_code: int, text: str = ""):
    return SimpleNamespace(status_code=status_code, text=text)


def test_is_allowed_true_when_robots_txt_permits(monkeypatch):
    monkeypatch.setattr(
        robots.http, "get",
        lambda url, **kw: _fake_response(200, "User-agent: *\nDisallow: /admin/\n"),
    )
    assert robots.is_allowed("https://example.invalid/jobs") is True


def test_is_allowed_false_on_explicit_disallow(monkeypatch):
    monkeypatch.setattr(
        robots.http, "get",
        lambda url, **kw: _fake_response(200, "User-agent: *\nDisallow: /jobs\n"),
    )
    assert robots.is_allowed("https://example.invalid/jobs") is False


def test_is_allowed_true_when_robots_txt_fetch_errors(monkeypatch):
    def raise_error(url, **kw):
        raise ConnectionError("boom")
    monkeypatch.setattr(robots.http, "get", raise_error)
    assert robots.is_allowed("https://example.invalid/jobs") is True


def test_is_allowed_true_on_http_error_status(monkeypatch):
    """A WAF that 403s our own identified fetch of robots.txt itself is a
    transport problem, not an explicit disallow — must not block the source."""
    monkeypatch.setattr(robots.http, "get", lambda url, **kw: _fake_response(403, ""))
    assert robots.is_allowed("https://example.invalid/jobs") is True
