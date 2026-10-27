"""Source health state (SPEC.md: Health checks).

A source counts as quiet only when its item selector matched and every
record validated; zero matches on a source with history is a failure.
States: healthy, warning, stale, failed, blocked.

Thresholds below (consecutive-failure count, volume-drop ratio, schema
failure share) are defaults, not numbers SPEC.md fixes — tune them from
real behaviour once sources have run for a while.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone

from gleaner.config import Source

CONSECUTIVE_FAILURES_BEFORE_ALERT = 1
VOLUME_DROP_WARNING_RATIO = 0.5
SCHEMA_FAILURE_WARNING_SHARE = 0.1
SCHEMA_FAILURE_FAILED_SHARE = 0.5

RECENT_RUNS_WINDOW = 10
VOLUME_HISTORY_RUNS = 5


@dataclass
class HealthState:
    state: str  # healthy | warning | stale | failed | blocked
    reasons: list[str] = field(default_factory=list)


def record_run(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    status: str,
    http_code: int | None,
    records_found: int | None,
    records_with_missing_required: int | None,
    error: str | None,
    snapshot_path: str | None,
    started_at: str,
    finished_at: str,
) -> int:
    conn.execute(
        """INSERT INTO runs (
            source_id, started_at, finished_at, status, http_code,
            records_found, records_with_missing_required, error, snapshot_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            source_id, started_at, finished_at, status, http_code,
            records_found, records_with_missing_required, error, snapshot_path,
        ),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def evaluate(conn: sqlite3.Connection, source: Source) -> HealthState:
    runs = conn.execute(
        "SELECT * FROM runs WHERE source_id = ? ORDER BY started_at DESC LIMIT ?",
        (source.id, RECENT_RUNS_WINDOW),
    ).fetchall()

    if not runs:
        return HealthState("healthy", ["no runs yet"])

    latest = runs[0]

    # Transport: consecutive failures.
    consecutive_failed = 0
    for run in runs:
        if run["status"] == "failed":
            consecutive_failed += 1
        else:
            break
    if consecutive_failed >= CONSECUTIVE_FAILURES_BEFORE_ALERT:
        return HealthState("failed", [f"{consecutive_failed} consecutive failed run(s): {latest['error']}"])

    if latest["status"] == "blocked":
        return HealthState("blocked", ["disallowed by robots.txt"])

    reasons: list[str] = []
    state = "healthy"

    # Parse: zero matches.
    if latest["records_found"] == 0:
        if source.health.alert_on_zero_results:
            return HealthState("failed", ["zero items matched"])
        reasons.append("zero items matched (alert_on_zero_results is off for this source)")
        state = "warning"

    # Schema: share of records missing a required field.
    if latest["records_found"]:
        missing_share = (latest["records_with_missing_required"] or 0) / latest["records_found"]
        if missing_share >= SCHEMA_FAILURE_FAILED_SHARE:
            return HealthState(
                "failed", [f"{missing_share:.0%} of records missing a required field"]
            )
        if missing_share >= SCHEMA_FAILURE_WARNING_SHARE:
            reasons.append(f"{missing_share:.0%} of records missing a required field")
            state = "warning"

    # Volume: compare against recent successful history.
    successful_history = [
        r for r in runs[1:] if r["status"] == "ok" and r["records_found"] is not None
    ][:VOLUME_HISTORY_RUNS]
    if successful_history and latest["records_found"] is not None:
        avg = sum(r["records_found"] for r in successful_history) / len(successful_history)
        if avg > 0 and latest["records_found"] < VOLUME_DROP_WARNING_RATIO * avg:
            reasons.append(f"record count {latest['records_found']} is far below recent average {avg:.1f}")
            state = "warning"

    # Freshness: no new item for longer than stale_after_days.
    last_item = conn.execute(
        "SELECT MAX(first_seen_at) AS m FROM items WHERE source_id = ?", (source.id,)
    ).fetchone()
    if last_item and last_item["m"]:
        last_seen = datetime.fromisoformat(last_item["m"])
        age_days = (datetime.now(timezone.utc) - last_seen).days
        if age_days > source.health.stale_after_days:
            return HealthState("stale", [f"no new items for {age_days} days"])

    return HealthState(state, reasons)
