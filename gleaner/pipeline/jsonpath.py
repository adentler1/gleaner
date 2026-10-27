"""Minimal dotted-path resolver for JSON config values, e.g. "data.items" or
"authors[0].name". Deliberately not a full JSONPath implementation — the
api adapter only ever needs to walk down known keys and list indices.
"""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def _tokenize(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for key, index in _TOKEN_RE.findall(path):
        if key:
            tokens.append(key)
        else:
            tokens.append(int(index))
    return tokens


def get_path(obj, path: str):
    """Returns None if any step along the path is missing, rather than
    raising — a missing field is a data-quality issue for the schema health
    check to flag, not a crash."""
    current = obj
    for token in _tokenize(path):
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                return None
            current = current[token]
        else:
            if not isinstance(current, dict) or token not in current:
                return None
            current = current[token]
    return current
