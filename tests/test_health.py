import pytest

from gleaner import db, health
from gleaner.config import Source


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.sqlite3")
    db.migrate(c)
    return c


@pytest.fixture
def source():
    return Source(id="src", adapter="html", url="https://example.invalid")


def _run(conn, source_id, *, status="ok", records_found=5, missing=0, error=None, at="2026-10-27T00:00:00+00:00"):
    health.record_run(
        conn, source_id=source_id, status=status, http_code=200 if status == "ok" else 404,
        records_found=records_found, records_with_missing_required=missing,
        error=error, snapshot_path=None, started_at=at, finished_at=at,
    )


def test_no_runs_is_healthy(conn, source):
    assert health.evaluate(conn, source).state == "healthy"


def test_single_transport_failure_is_failed_immediately(conn, source):
    _run(conn, "src", status="failed", records_found=None, error="HTTP 404")
    state = health.evaluate(conn, source)
    assert state.state == "failed"
    assert "404" in state.reasons[0]


def test_zero_matches_with_alert_on_zero_results_is_failed(conn, source):
    _run(conn, "src", records_found=5)
    _run(conn, "src", records_found=0, at="2026-10-28T00:00:00+00:00")
    assert health.evaluate(conn, source).state == "failed"


def test_healthy_run_is_healthy(conn, source):
    _run(conn, "src", records_found=5)
    assert health.evaluate(conn, source).state == "healthy"


def test_high_schema_failure_share_is_failed(conn, source):
    _run(conn, "src", records_found=10, missing=6)
    assert health.evaluate(conn, source).state == "failed"


def test_low_schema_failure_share_is_warning(conn, source):
    _run(conn, "src", records_found=10, missing=2)
    assert health.evaluate(conn, source).state == "warning"


def test_volume_drop_is_warning(conn, source):
    for _ in range(5):
        _run(conn, "src", records_found=20)
    _run(conn, "src", records_found=3, at="2026-11-01T00:00:00+00:00")
    assert health.evaluate(conn, source).state == "warning"


def test_stale_when_no_new_items_past_threshold(conn, source):
    conn.execute(
        """INSERT INTO items (id, source_id, watch_id, canonical_url, first_seen_at,
            last_checked_at, last_changed_at, content_hash, raw_fields, unparsed_fields)
        VALUES ('i1', 'src', 'w', 'https://x', '2026-01-01T00:00:00+00:00',
            '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', 'h', '{}', '[]')"""
    )
    _run(conn, "src", records_found=0)
    source = Source(id="src", adapter="html", url="https://example.invalid", health={"alert_on_zero_results": False})
    assert health.evaluate(conn, source).state == "stale"
