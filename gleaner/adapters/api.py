"""API adapter: official JSON endpoints (SPEC.md).

source.items_path is a dotted path to the list of items within the response
body (omit it when the response body is itself a list). extract.fields maps
a field name to a dotted path within each item.
"""
from __future__ import annotations

import json

from gleaner.adapters import http
from gleaner.adapters.base import FetchResult, RawItem
from gleaner.config import Source
from gleaner.pipeline.jsonpath import get_path


def parse(content: str | bytes, source: Source) -> list[RawItem]:
    body = json.loads(content)

    items = get_path(body, source.items_path) if source.items_path else body
    if not isinstance(items, list):
        raise ValueError(
            f"source {source.id!r}: items_path {source.items_path!r} did not resolve to a list"
        )

    field_map = source.extract.fields if source.extract else {}
    raw_items: list[RawItem] = []
    for item in items:
        fields = {name: get_path(item, path) for name, path in field_map.items()}
        source_item_id = get_path(item, "id") if isinstance(item, dict) and "id" in item else None
        raw_items.append(RawItem(source_item_id=str(source_item_id) if source_item_id is not None else None, fields=fields))
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
