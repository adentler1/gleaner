"""One-way Telegram alerts through the monitor's own bot (SPEC.md).
Feedback buttons are a milestone 1b addition; this module only sends.
Every send attempt is logged to the alerts outbox table, with retries,
so the daily digest (later) can report anything still undelivered.
"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone

import requests

TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0


def send_message(bot_token: str, chat_id: str, text: str, *, timeout: int = 10) -> tuple[bool, str | None]:
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=timeout)
    except Exception as exc:
        return False, str(exc)

    if response.status_code == 200 and response.json().get("ok"):
        return True, None
    return False, f"HTTP {response.status_code}: {response.text[:200]}"


def send_alert(
    conn: sqlite3.Connection,
    *,
    bot_token: str,
    chat_id: str,
    message: str,
    item_id: str | None = None,
    channel: str = "telegram",
) -> bool:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        ok, last_error = send_message(bot_token, chat_id, message)
        if ok:
            conn.execute(
                "INSERT INTO alerts (item_id, channel, message, sent_at, delivered, retry_count) "
                "VALUES (?, ?, ?, ?, 1, ?)",
                (item_id, channel, message, datetime.now(timezone.utc).isoformat(), attempt - 1),
            )
            return True
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    conn.execute(
        "INSERT INTO alerts (item_id, channel, message, sent_at, delivered, retry_count) "
        "VALUES (?, ?, ?, ?, 0, ?)",
        (item_id, channel, message, datetime.now(timezone.utc).isoformat(), MAX_RETRIES),
    )
    return False
