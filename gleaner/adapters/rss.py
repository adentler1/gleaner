"""RSS/Atom adapter, including Google News search feeds (SPEC.md).

Default field mapping comes from feedparser's normalized entry attributes
(title, link, id/guid, published, summary). extract.fields can override or
add fields, where each selector is a feedparser entry attribute name.
"""
from __future__ import annotations

import feedparser

from gleaner.adapters import http
from gleaner.adapters.base import FetchResult, RawItem
from gleaner.config import Source

DEFAULT_FIELD_MAP = {
    "title": "title",
    "url": "link",
    "published": "published",
}


def parse(content: str | bytes, source: Source) -> list[RawItem]:
    field_map = dict(DEFAULT_FIELD_MAP)
    if source.extract is not None:
        field_map.update(source.extract.fields)

    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"feed did not parse: {parsed.bozo_exception}")

    raw_items: list[RawItem] = []
    for entry in parsed.entries:
        fields = {name: entry.get(attr) for name, attr in field_map.items()}
        source_item_id = entry.get("id") or entry.get("guid")
        raw_items.append(RawItem(source_item_id=source_item_id, fields=fields))
    return raw_items


def fetch(source: Source) -> FetchResult:
    try:
        response = http.get(source.url)
    except Exception as exc:
        return FetchResult(http_code=None, error=str(exc))

    if response.status_code >= 400:
        return FetchResult(http_code=response.status_code, error=f"HTTP {response.status_code}")

    try:
        raw_items = parse(response.content, source)
    except Exception as exc:
        return FetchResult(http_code=response.status_code, error=f"parse error: {exc}", snapshot_text=response.text)

    return FetchResult(raw_items=raw_items, http_code=response.status_code, snapshot_text=response.text)
