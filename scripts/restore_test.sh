#!/usr/bin/env bash
# Restore test (SPEC.md M1a done-when: "a database restore works").
# Pulls the most recent backup from the NUC into a throwaway local path and
# runs a basic integrity + row-count check. Never touches the live database.
# Required environment: GLEANER_BACKUP_HOST, GLEANER_BACKUP_DIR.
set -euo pipefail

: "${GLEANER_BACKUP_HOST:?set GLEANER_BACKUP_HOST}"
: "${GLEANER_BACKUP_DIR:?set GLEANER_BACKUP_DIR}"

latest="$(ssh "$GLEANER_BACKUP_HOST" "cd '${GLEANER_BACKUP_DIR}' && ls -1t gleaner_*.sqlite3 | head -n1")"
if [ -z "$latest" ]; then
  echo "no backup found on ${GLEANER_BACKUP_HOST}:${GLEANER_BACKUP_DIR}" >&2
  exit 1
fi

restore_path="$(mktemp)"
trap 'rm -f "$restore_path"' EXIT

scp "${GLEANER_BACKUP_HOST}:${GLEANER_BACKUP_DIR%/}/${latest}" "$restore_path"

sqlite3 "$restore_path" "PRAGMA integrity_check;" | grep -q '^ok$' \
  || { echo "integrity_check failed on $latest" >&2; exit 1; }

item_count="$(sqlite3 "$restore_path" "SELECT COUNT(*) FROM items;")"
run_count="$(sqlite3 "$restore_path" "SELECT COUNT(*) FROM runs;")"

echo "restored $latest: integrity ok, $item_count items, $run_count runs"
