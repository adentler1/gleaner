from gleaner import db


def test_migrate_creates_all_tables(tmp_path):
    conn = db.connect(tmp_path / "test.sqlite3")
    applied = db.migrate(conn)
    assert applied == [1]
    assert db.schema_version(conn) == 1

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    expected = {
        "schema_version", "runs", "items", "item_versions", "scores",
        "feedback", "deadlines", "proposals", "missed_items",
        "source_queue", "alerts",
    }
    assert expected <= tables


def test_migrate_is_idempotent(tmp_path):
    conn = db.connect(tmp_path / "test.sqlite3")
    db.migrate(conn)
    second_run = db.migrate(conn)
    assert second_run == []
    assert db.schema_version(conn) == 1
