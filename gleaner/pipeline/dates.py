"""Locale-aware date parsing (SPEC.md: "a date locale set per source").
The raw string is always kept by the caller alongside whatever this returns;
a date that fails to parse is not an error here — the caller stores None
and the item is flagged in the inbox, never dropped.
"""
from __future__ import annotations

from datetime import date

from dateutil import parser as dateutil_parser

# Locales where day comes before month in an ambiguous numeric date (dd/mm/yyyy).
_DAY_FIRST_LOCALES = {"de", "en-gb", "fr", "es", "it"}


def parse_date(raw: str | None, locale: str = "en") -> date | None:
    if not raw:
        return None
    try:
        dayfirst = locale.lower() in _DAY_FIRST_LOCALES
        return dateutil_parser.parse(raw, dayfirst=dayfirst, fuzzy=True).date()
    except (ValueError, OverflowError):
        return None
