"""Item identity and change rules, fixed in milestone 1 (SPEC.md: Data model).

- Item identity: the source's own id where it has one, else the normalized URL.
- Content hash: computed over declared fields only, so cosmetic text
  ("posted 3 days ago") never creates a spurious version.
- Cluster key: normalized title + employer-or-deadline, used to suppress
  repeat alerts for the same posting duplicated across sources. It never
  merges records — each source's item row still exists independently.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAMS = {"gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src"}


def normalize_url(url: str) -> str:
    """Lowercases scheme and host, strips tracking params and the fragment.
    Redirect resolution happens at fetch time (requests follows redirects);
    this function only normalizes the string representation."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()

    kept_params = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
        and not any(k.lower().startswith(p) for p in _TRACKING_PARAM_PREFIXES)
    ]
    query = urlencode(sorted(kept_params))

    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, query, ""))


def compute_item_id(*, source_id: str, source_item_id: str | None, canonical_url: str) -> str:
    """The source's own id where it has one, otherwise the normalized URL.
    Namespaced by source_id so two sources' internal ids never collide."""
    if source_item_id:
        return f"{source_id}:{source_item_id}"
    return f"{source_id}:url:{canonical_url}"


def compute_content_hash(declared_fields: dict[str, str | None]) -> str:
    """Hash over exactly the fields the source config declares (required_fields
    plus any other extracted fields), sorted for stability. View counters or
    similar undeclared noise fields must never be passed in here."""
    canonical = json.dumps(declared_fields, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w\s]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def compute_cluster_key(*, title: str | None, employer_or_deadline: str | None) -> str | None:
    """Normalized title + employer-or-deadline. Returns None when there is no
    title to key on, since an empty cluster key would wrongly cluster every
    title-less item together."""
    title_norm = _normalize_text(title)
    if not title_norm:
        return None
    return f"{title_norm}|{_normalize_text(employer_or_deadline)}"
