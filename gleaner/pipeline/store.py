"""Applies identity and change rules to a fetched RawItem and stores the
result (SPEC.md: Data model, Identity and change rules). This is the one
place item rows and item_versions rows get written.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from gleaner.adapters.base import RawItem
from gleaner.config import Source
from gleaner.pipeline.dates import parse_date
from gleaner.pipeline.identity import (
    compute_cluster_key,
    compute_content_hash,
    compute_item_id,
    normalize_url,
)


@dataclass
class StoreResult:
    item_id: str
    is_new: bool
    realert: bool
    unparsed_fields: list[str]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def store_raw_item(
    conn: sqlite3.Connection,
    *,
    source: Source,
    watch_id: str,
    run_id: int,
    raw_item: RawItem,
) -> StoreResult:
    """fields must include a 'url' entry — every adapter in this project
    extracts one, by convention, since canonical_url is required for identity
    when a source has no id of its own."""
    raw_url = raw_item.fields.get("url")
    if not raw_url:
        raise ValueError(f"source {source.id!r}: item has no 'url' field: {raw_item.fields}")

    canonical_url = normalize_url(raw_url)
    item_id = compute_item_id(
        source_id=source.id, source_item_id=raw_item.source_item_id, canonical_url=canonical_url
    )
    content_hash = compute_content_hash(raw_item.fields)
    unparsed_fields = [f for f in source.required_fields if not raw_item.fields.get(f)]

    title = raw_item.fields.get("title")
    deadline_raw = raw_item.fields.get("deadline")
    deadline = parse_date(deadline_raw, source.date_locale)
    cluster_key = compute_cluster_key(title=title, employer_or_deadline=deadline_raw or title)

    now = _now()
    existing = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()

    if existing is None:
        conn.execute(
            """INSERT INTO items (
                id, source_id, watch_id, canonical_url, title, deadline, deadline_raw,
                first_seen_at, last_checked_at, last_changed_at, content_hash,
                extraction_version, cluster_key, raw_fields, unparsed_fields, first_seen_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
            (
                item_id, source.id, watch_id, canonical_url, title,
                deadline.isoformat() if deadline else None, deadline_raw,
                now, now, now, content_hash, cluster_key,
                json.dumps(raw_item.fields, ensure_ascii=False),
                json.dumps(unparsed_fields), run_id,
            ),
        )
        return StoreResult(item_id=item_id, is_new=True, realert=True, unparsed_fields=unparsed_fields)

    if existing["content_hash"] == content_hash:
        conn.execute("UPDATE items SET last_checked_at = ? WHERE id = ?", (now, item_id))
        return StoreResult(item_id=item_id, is_new=False, realert=False, unparsed_fields=unparsed_fields)

    old_fields = json.loads(existing["raw_fields"])
    changed_fields = sorted(
        k for k in raw_item.fields
        if raw_item.fields.get(k) != old_fields.get(k)
    )
    realert = bool({"title", "deadline"} & set(changed_fields))

    conn.execute(
        """UPDATE items SET
            title = ?, deadline = ?, deadline_raw = ?, last_checked_at = ?, last_changed_at = ?,
            content_hash = ?, cluster_key = ?, raw_fields = ?, unparsed_fields = ?
        WHERE id = ?""",
        (
            title, deadline.isoformat() if deadline else None, deadline_raw, now, now,
            content_hash, cluster_key, json.dumps(raw_item.fields, ensure_ascii=False),
            json.dumps(unparsed_fields), item_id,
        ),
    )
    conn.execute(
        """INSERT INTO item_versions (item_id, run_id, changed_fields, old_values, new_values, realert, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            item_id, run_id, json.dumps(changed_fields),
            json.dumps({k: old_fields.get(k) for k in changed_fields}),
            json.dumps({k: raw_item.fields.get(k) for k in changed_fields}),
            realert, now,
        ),
    )
    return StoreResult(item_id=item_id, is_new=False, realert=realert, unparsed_fields=unparsed_fields)
