"""HTML adapter: static pages, CSS selectors from config (SPEC.md).

extract.item selects each item's container element; extract.fields maps a
field name to a CSS selector, optionally suffixed "@attr" to read an
attribute instead of text content (e.g. "a@href" for a link's target).
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from gleaner.adapters import http
from gleaner.adapters.base import FetchResult, RawItem
from gleaner.config import Source


def _extract_field(item_tag, selector_spec: str) -> str | None:
    if "@" in selector_spec:
        selector, attr = selector_spec.rsplit("@", 1)
    else:
        selector, attr = selector_spec, None

    target = item_tag if not selector.strip() else item_tag.select_one(selector)
    if target is None:
        return None
    if attr:
        value = target.get(attr)
        return value.strip() if isinstance(value, str) else value
    text = target.get_text(strip=True)
    return text or None


def parse(content: str, source: Source) -> list[RawItem]:
    if source.extract is None or not source.extract.item:
        raise ValueError(f"source {source.id!r}: html adapter requires extract.item")

    soup = BeautifulSoup(content, "lxml")
    raw_items: list[RawItem] = []
    for item_tag in soup.select(source.extract.item):
        fields = {
            name: _extract_field(item_tag, selector)
            for name, selector in source.extract.fields.items()
        }
        raw_items.append(RawItem(source_item_id=None, fields=fields))
    return raw_items


def fetch(source: Source) -> FetchResult:
    try:
        response = http.get(source.url)
    except Exception as exc:
        return FetchResult(http_code=None, error=str(exc))

    if response.status_code >= 400:
        return FetchResult(http_code=response.status_code, error=f"HTTP {response.status_code}")

    try:
        raw_items = parse(response.text, source)
    except Exception as exc:
        return FetchResult(http_code=response.status_code, error=f"parse error: {exc}", snapshot_text=response.text)

    return FetchResult(raw_items=raw_items, http_code=response.status_code, snapshot_text=response.text)
