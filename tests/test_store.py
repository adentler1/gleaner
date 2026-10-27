import json

import pytest

from gleaner import db
from gleaner.adapters.base import RawItem
from gleaner.config import Source
from gleaner.pipeline.store import store_raw_item


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.sqlite3")
    db.migrate(c)
    return c


@pytest.fixture
def run_id(conn):
    conn.execute(
        "INSERT INTO runs (source_id, started_at, status) VALUES ('src', '2026-10-27T00:00:00', 'ok')"
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


@pytest.fixture
def source():
    return Source(
        id="src", adapter="html", url="https://example.invalid",
        required_fields=["title", "url"],
    )


def test_new_item_is_inserted_and_flagged_new(conn, run_id, source):
    raw = RawItem(source_item_id=None, fields={
        "title": "Lecturer", "url": "https://example.invalid/jobs/1", "deadline": "2026-12-01",
    })
    result = store_raw_item(conn, source=source, watch_id="w", run_id=run_id, raw_item=raw)

    assert result.is_new is True
    assert result.realert is True
    assert result.unparsed_fields == []

    row = conn.execute("SELECT * FROM items WHERE id = ?", (result.item_id,)).fetchone()
    assert row["title"] == "Lecturer"
    assert row["deadline"] == "2026-12-01"


def test_unchanged_refetch_only_updates_last_checked(conn, run_id, source):
    raw = RawItem(source_item_id=None, fields={
        "title": "Lecturer", "url": "https://example.invalid/jobs/1", "deadline": "2026-12-01",
    })
    first = store_raw_item(conn, source=source, watch_id="w", run_id=run_id, raw_item=raw)
    second = store_raw_item(conn, source=source, watch_id="w", run_id=run_id, raw_item=raw)

    assert second.is_new is False
    assert second.realert is False
    versions = conn.execute(
        "SELECT * FROM item_versions WHERE item_id = ?", (first.item_id,)
    ).fetchall()
    assert versions == []


def test_non_title_deadline_change_is_silent(conn, run_id, source):
    raw1 = RawItem(source_item_id=None, fields={
        "title": "Lecturer", "url": "https://example.invalid/jobs/1",
        "deadline": "2026-12-01", "summary": "old summary",
    })
    raw2 = dict(raw1.fields)
    raw2["summary"] = "new summary"

    store_raw_item(conn, source=source, watch_id="w", run_id=run_id, raw_item=raw1)
    result = store_raw_item(
        conn, source=source, watch_id="w", run_id=run_id,
        raw_item=RawItem(source_item_id=None, fields=raw2),
    )

    assert result.is_new is False
    assert result.realert is False  # summary changed, but not title/deadline
    versions = conn.execute(
        "SELECT * FROM item_versions WHERE item_id = ?", (result.item_id,)
    ).fetchall()
    assert len(versions) == 1
    assert json.loads(versions[0]["changed_fields"]) == ["summary"]


def test_deadline_change_triggers_realert(conn, run_id, source):
    raw1 = RawItem(source_item_id=None, fields={
        "title": "Lecturer", "url": "https://example.invalid/jobs/1", "deadline": "2026-12-01",
    })
    raw2 = RawItem(source_item_id=None, fields={
        "title": "Lecturer", "url": "https://example.invalid/jobs/1", "deadline": "2026-12-15",
    })

    store_raw_item(conn, source=source, watch_id="w", run_id=run_id, raw_item=raw1)
    result = store_raw_item(conn, source=source, watch_id="w", run_id=run_id, raw_item=raw2)

    assert result.realert is True


def test_missing_required_field_is_flagged_not_dropped(conn, run_id, source):
    raw = RawItem(source_item_id=None, fields={
        "title": None, "url": "https://example.invalid/jobs/1",
    })
    result = store_raw_item(conn, source=source, watch_id="w", run_id=run_id, raw_item=raw)

    assert result.unparsed_fields == ["title"]
    row = conn.execute("SELECT * FROM items WHERE id = ?", (result.item_id,)).fetchone()
    assert row is not None  # stored despite the missing required field
