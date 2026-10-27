"""Ties adapters, identity/change rules, health and alerting together.
Invoked once per scheduling cycle (one systemd timer, SPEC.md's single Pi
instance); processes every configured source and pings the external
heartbeat once at the end, so a dead timer or a dead Pi both show up there.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from gleaner import health
from gleaner.adapters import get_adapter
from gleaner.config import IMPLEMENTED_ADAPTERS, Config, Source
from gleaner.health import HealthState
from gleaner.pipeline import robots
from gleaner.pipeline.store import store_raw_item


@dataclass
class RunSummary:
    source_id: str
    run_id: int | None
    status: str
    health_before: HealthState
    health_after: HealthState
    new_items: int
    realerted_items: int
    alert_needed: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_snapshot(snapshot_dir: Path, source_id: str, text: str | None) -> str | None:
    if not text:
        return None
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"{source_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.snapshot"
    path.write_text(text, encoding="utf-8")
    return str(path)


def _watch_id_for_source(config: Config, source_id: str) -> str:
    for watch in config.watches:
        if source_id in watch.sources:
            return watch.id
    return "unassigned"


def run_source(conn: sqlite3.Connection, config: Config, source: Source, *, snapshot_dir: Path) -> RunSummary:
    health_before = health.evaluate(conn, source)
    watch_id = _watch_id_for_source(config, source.id)
    started_at = _now()

    if not robots.is_allowed(source.url):
        run_id = health.record_run(
            conn, source_id=source.id, status="blocked", http_code=None,
            records_found=None, records_with_missing_required=None,
            error="disallowed by robots.txt", snapshot_path=None,
            started_at=started_at, finished_at=_now(),
        )
        health_after = health.evaluate(conn, source)
        return RunSummary(source.id, run_id, "blocked", health_before, health_after, 0, 0, True)

    adapter = get_adapter(source.adapter)
    result = adapter.fetch(source)
    finished_at = _now()
    status = "failed" if result.error else "ok"
    records_found = len(result.raw_items) if status == "ok" else None
    missing_required = None
    if status == "ok":
        missing_required = sum(
            1 for item in result.raw_items
            if any(not item.fields.get(f) for f in source.required_fields)
        )
    snapshot_path = _save_snapshot(snapshot_dir, source.id, result.snapshot_text)

    run_id = health.record_run(
        conn, source_id=source.id, status=status, http_code=result.http_code,
        records_found=records_found, records_with_missing_required=missing_required,
        error=result.error, snapshot_path=snapshot_path,
        started_at=started_at, finished_at=finished_at,
    )

    new_items = 0
    realerted_items = 0
    if status == "ok":
        for raw_item in result.raw_items:
            store_result = store_raw_item(conn, source=source, watch_id=watch_id, run_id=run_id, raw_item=raw_item)
            if store_result.is_new:
                new_items += 1
            elif store_result.realert:
                realerted_items += 1

    health_after = health.evaluate(conn, source)
    alert_needed = (
        health_after.state in ("failed", "stale", "blocked")
        and health_after.state != health_before.state
    )
    return RunSummary(source.id, run_id, status, health_before, health_after, new_items, realerted_items, alert_needed)


def run_all(conn: sqlite3.Connection, config: Config, *, snapshot_dir: Path) -> list[RunSummary]:
    summaries = []
    for source in config.sources:
        if source.adapter not in IMPLEMENTED_ADAPTERS:
            continue
        summaries.append(run_source(conn, config, source, snapshot_dir=snapshot_dir))
    return summaries
