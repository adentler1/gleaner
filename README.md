# Gleaner

A single-user information monitor: watches configured web sources, applies
identity and change rules, tracks each source's health, and alerts on
Telegram. Everything after fetching is shared across sources; each source
gets its own small adapter (`api`, `rss`, or `html` so far).

Real watches, sources, and credentials are never in this repository — see
`config/example.yaml` and `.env.example` for the shape of a real
configuration, which lives entirely outside this repo.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Running the tests

```bash
.venv/bin/pytest
```

## Running the monitor

```bash
export GLEANER_ENV_FILE=/path/to/private/.env   # or export the GLEANER_* vars directly
.venv/bin/python -m gleaner migrate   # apply pending database migrations
.venv/bin/python -m gleaner run       # fetch every configured source once
.venv/bin/python -m gleaner health    # print current health state per source
```

In production this runs from a systemd timer, once per scheduling cycle; see
`scripts/backup_db.sh` and `scripts/restore_test.sh` for the backup side.

## Layout

```
gleaner/            engine: config loading, db/migrations, adapters, pipeline, health, alerts
tests/               pytest suite; every fixture under tests/fixtures/ is invented, not scraped
config/example.yaml  documentation example with neutral placeholder sources
scripts/             operational scripts (backup, restore test)
```
