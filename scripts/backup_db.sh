#!/usr/bin/env bash
# Nightly backup: sqlite3 .backup (safe against a concurrent writer) to a
# local temp file, then rsync to the NUC (SPEC.md: Operations — Backups).
# Required environment: GLEANER_DB_PATH, GLEANER_BACKUP_HOST, GLEANER_BACKUP_DIR.
# Retention: keeps the most recent GLEANER_BACKUP_KEEP (default 14) copies.
set -euo pipefail

: "${GLEANER_DB_PATH:?set GLEANER_DB_PATH}"
: "${GLEANER_BACKUP_HOST:?set GLEANER_BACKUP_HOST (the NUC's address)}"
: "${GLEANER_BACKUP_DIR:?set GLEANER_BACKUP_DIR (destination directory on the NUC)}"
KEEP="${GLEANER_BACKUP_KEEP:-14}"

tmp_backup="$(mktemp)"
trap 'rm -f "$tmp_backup"' EXIT

sqlite3 "$GLEANER_DB_PATH" ".backup '$tmp_backup'"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
dest="gleaner_${timestamp}.sqlite3"

rsync -a "$tmp_backup" "${GLEANER_BACKUP_HOST}:${GLEANER_BACKUP_DIR%/}/${dest}"

ssh "$GLEANER_BACKUP_HOST" \
  "cd '${GLEANER_BACKUP_DIR}' && ls -1t gleaner_*.sqlite3 | tail -n +$((KEEP + 1)) | xargs -r rm --"

echo "backed up to ${GLEANER_BACKUP_HOST}:${GLEANER_BACKUP_DIR%/}/${dest}"
