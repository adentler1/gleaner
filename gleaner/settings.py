"""Runtime settings, read from environment variables. The .env file lives in
the private data directory, outside the repo (SPEC.md: Repository and
privacy — "Credentials live in an environment file outside the repository").
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


@dataclass
class Settings:
    config_dir: Path
    db_path: Path
    snapshot_dir: Path
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    heartbeat_url: str | None


def load_settings(env_file: Path | None = None) -> Settings:
    if env_file is not None:
        load_env_file(env_file)

    db_path = Path(os.environ["GLEANER_DB_PATH"])
    default_snapshot_dir = db_path.parent.parent / "snapshots"
    return Settings(
        config_dir=Path(os.environ["GLEANER_CONFIG_DIR"]),
        db_path=db_path,
        snapshot_dir=Path(os.environ.get("GLEANER_SNAPSHOT_DIR", default_snapshot_dir)),
        telegram_bot_token=os.environ.get("GLEANER_TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.environ.get("GLEANER_TELEGRAM_CHAT_ID"),
        heartbeat_url=os.environ.get("GLEANER_HEARTBEAT_URL"),
    )
