from unittest.mock import MagicMock, patch

import pytest

from gleaner import db
from gleaner.config import Config, Source, Watch
from gleaner.runner import run_source


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.sqlite3")
    db.migrate(c)
    return c


@pytest.fixture
def config():
    source = Source(
        id="jobs", adapter="html", url="https://example.invalid/jobs",
        extract={"item": "div.job", "fields": {"title": "h3", "url": "a@href", "deadline": ".deadline"}},
        required_fields=["title", "url"],
        health={"alert_on_zero_results": True},
    )
    watch = Watch(id="w", pattern="stream", description="d", sources=["jobs"])
    return Config(watches=[watch], sources=[source])


HTML_WITH_TWO_JOBS = """
<div class="job"><h3>Lecturer</h3><a href="/jobs/1">x</a><span class="deadline">2026-12-01</span></div>
<div class="job"><h3>Fellow</h3><a href="/jobs/2">x</a><span class="deadline">2026-12-02</span></div>
"""


def _mock_response(status_code=200, text=""):
    resp = MagicMock(status_code=status_code, text=text)
    resp.content = text.encode()
    return resp


@patch("gleaner.pipeline.robots.is_allowed", return_value=True)
def test_successful_run_stores_items_and_is_healthy(_robots, conn, config, tmp_path):
    with patch("gleaner.adapters.http.requests.get", return_value=_mock_response(text=HTML_WITH_TWO_JOBS)):
        summary = run_source(conn, config, config.source_by_id("jobs"), snapshot_dir=tmp_path)

    assert summary.status == "ok"
    assert summary.new_items == 2
    assert summary.health_after.state == "healthy"
    assert summary.alert_needed is False
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2


@patch("gleaner.pipeline.robots.is_allowed", return_value=True)
def test_404_triggers_alert_within_one_cycle(_robots, conn, config, tmp_path):
    with patch("gleaner.adapters.http.requests.get", return_value=_mock_response(status_code=404, text="not found")):
        summary = run_source(conn, config, config.source_by_id("jobs"), snapshot_dir=tmp_path)

    assert summary.status == "failed"
    assert summary.health_after.state == "failed"
    assert summary.alert_needed is True


@patch("gleaner.pipeline.robots.is_allowed", return_value=True)
def test_altered_page_with_zero_matches_triggers_alert(_robots, conn, config, tmp_path):
    # First cycle: healthy baseline with real matches.
    with patch("gleaner.adapters.http.requests.get", return_value=_mock_response(text=HTML_WITH_TWO_JOBS)):
        run_source(conn, config, config.source_by_id("jobs"), snapshot_dir=tmp_path)

    # Second cycle: selectors no longer match anything (page structure changed).
    with patch("gleaner.adapters.http.requests.get", return_value=_mock_response(text="<div>no jobs here</div>")):
        summary = run_source(conn, config, config.source_by_id("jobs"), snapshot_dir=tmp_path)

    assert summary.status == "ok"  # HTTP succeeded, zero matches is a parse/health concern
    assert summary.health_after.state == "failed"
    assert summary.alert_needed is True


@patch("gleaner.pipeline.robots.is_allowed", return_value=False)
def test_robots_disallowed_marks_blocked(_robots, conn, config, tmp_path):
    summary = run_source(conn, config, config.source_by_id("jobs"), snapshot_dir=tmp_path)
    assert summary.status == "blocked"
    assert summary.health_after.state == "blocked"
    assert summary.alert_needed is True
