"""Shared types for adapters.

An adapter's fetch() does the network call; parse() is pure and operates on
already-fetched content, so fixture tests can call parse() directly on a
saved sample without touching the network (SPEC.md: Fixture test health check).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawItem:
    source_item_id: str | None
    fields: dict[str, str | None]  # raw extracted strings, keyed by the names in source.extract.fields


@dataclass
class FetchResult:
    raw_items: list[RawItem] = field(default_factory=list)
    http_code: int | None = None
    error: str | None = None
    snapshot_text: str | None = None
