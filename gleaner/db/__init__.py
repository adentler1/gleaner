"""SQLite connection and migration runner.

One database file per instance. Migrations are plain numbered .sql scripts
in gleaner/db/migrations/, tracked in a schema_version table, applied in
order, never edited after being committed (SPEC.md: Migrations).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_MIGRATION_NAME_RE = re.compile(r"^(\d+)_.*\.sql$")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)  # autocommit; callers use explicit transactions
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _available_migrations() -> list[tuple[int, Path]]:
    found = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        m = _MIGRATION_NAME_RE.match(path.name)
        if not m:
            raise ValueError(f"migration file {path.name!r} does not match NNNN_description.sql")
        found.append((int(m.group(1)), path))
    return sorted(found, key=lambda t: t[0])


def migrate(conn: sqlite3.Connection) -> list[int]:
    """Applies every migration newer than the current schema_version.
    Returns the list of version numbers that were applied."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]

    applied = []
    for version, path in _available_migrations():
        if version <= current:
            continue
        # executescript() (needed for multi-statement DDL files) commits any
        # open transaction before it runs, so BEGIN/COMMIT can't wrap it.
        # Split into individual statements instead and wrap those explicitly.
        statements = [s.strip() for s in path.read_text(encoding="utf-8").split(";") if s.strip()]
        conn.execute("BEGIN")
        try:
            for statement in statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(timezone.utc).isoformat()),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        applied.append(version)
    return applied


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) FROM schema_version"
    ).fetchone()
    return row[0]
