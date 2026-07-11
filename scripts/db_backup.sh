#!/usr/bin/env bash
# PostgreSQL backup with rotation (DBA runbook).
#
# Usage:
#   DATABASE_URL=postgresql://user:pass@host:5432/db ./scripts/db_backup.sh [backup_dir] [keep]
#
# - Writes a compressed custom-format dump (pg_dump -Fc) named by UTC timestamp.
# - Keeps the newest $KEEP dumps (default 7), deletes older ones.
# - Restore drill (run it — an untested backup is not a backup):
#     pg_restore --clean --if-exists -d "$DATABASE_URL" backups/pb_<timestamp>.dump
set -euo pipefail

BACKUP_DIR="${1:-backups}"
KEEP="${2:-7}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: set DATABASE_URL (postgresql://...)" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/pb_${STAMP}.dump"

pg_dump --format=custom --no-owner --file="$OUT" "$DATABASE_URL"
echo "backup written: $OUT ($(du -h "$OUT" | cut -f1))"

# rotate: keep newest $KEEP
ls -1t "$BACKUP_DIR"/pb_*.dump 2>/dev/null | tail -n "+$((KEEP + 1))" | while read -r old; do
  rm -f "$old"
  echo "rotated out: $old"
done
