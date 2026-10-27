"""Command-line entrypoint, invoked by the systemd timer/service on the Pi.

Reads all configuration from environment variables (see gleaner/settings.py):
  GLEANER_ENV_FILE       path to the private .env file (optional; if set,
                          values there are loaded before everything else)
  GLEANER_CONFIG_DIR     private config directory (watches/sources YAML)
  GLEANER_DB_PATH         sqlite3 database file
  GLEANER_SNAPSHOT_DIR    where raw fetch snapshots are written (optional)
  GLEANER_TELEGRAM_BOT_TOKEN, GLEANER_TELEGRAM_CHAT_ID   (optional; alerts
                          are skipped with a warning if unset)
  GLEANER_HEARTBEAT_URL   external dead-man ping URL (optional; skipped if unset)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from gleaner import db
from gleaner.alerts.telegram import send_alert
from gleaner.config import load_config
from gleaner.health import heartbeat
from gleaner.runner import run_all
from gleaner.settings import load_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gleaner")


def _settings():
    env_file = os.environ.get("GLEANER_ENV_FILE")
    return load_settings(Path(env_file) if env_file else None)


def cmd_migrate(_args: argparse.Namespace) -> int:
    settings = _settings()
    conn = db.connect(settings.db_path)
    applied = db.migrate(conn)
    if applied:
        logger.info("applied migrations: %s", applied)
    else:
        logger.info("database already at schema version %s", db.schema_version(conn))
    return 0


def cmd_run(_args: argparse.Namespace) -> int:
    settings = _settings()
    conn = db.connect(settings.db_path)
    db.migrate(conn)
    config = load_config(settings.config_dir)

    summaries = run_all(conn, config, snapshot_dir=settings.snapshot_dir)

    any_alert_undelivered = False
    for summary in summaries:
        logger.info(
            "%s: status=%s health=%s new=%d realerted=%d",
            summary.source_id, summary.status, summary.health_after.state,
            summary.new_items, summary.realerted_items,
        )
        if summary.alert_needed:
            message = (
                f"Gleaner: source '{summary.source_id}' is now {summary.health_after.state}.\n"
                f"{'; '.join(summary.health_after.reasons) or 'no further detail'}"
            )
            if settings.telegram_bot_token and settings.telegram_chat_id:
                delivered = send_alert(
                    conn, bot_token=settings.telegram_bot_token,
                    chat_id=settings.telegram_chat_id, message=message,
                )
                if not delivered:
                    any_alert_undelivered = True
                    logger.error("alert for %s could not be delivered", summary.source_id)
            else:
                logger.warning("health alert for %s not sent — Telegram is not configured", summary.source_id)

    if settings.heartbeat_url:
        if heartbeat.ping(settings.heartbeat_url):
            logger.info("heartbeat ping ok")
        else:
            logger.error("heartbeat ping failed")
    else:
        logger.warning("GLEANER_HEARTBEAT_URL not set — no heartbeat ping sent")

    return 1 if any_alert_undelivered else 0


def cmd_health(_args: argparse.Namespace) -> int:
    from gleaner import health as health_module

    settings = _settings()
    conn = db.connect(settings.db_path)
    config = load_config(settings.config_dir)
    for source in config.sources:
        state = health_module.evaluate(conn, source)
        print(f"{source.id}: {state.state} ({'; '.join(state.reasons) or 'no issues'})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gleaner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("migrate", help="apply pending database migrations").set_defaults(func=cmd_migrate)
    subparsers.add_parser("run", help="fetch every source once, store, alert, heartbeat").set_defaults(func=cmd_run)
    subparsers.add_parser("health", help="print current health state per source").set_defaults(func=cmd_health)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
