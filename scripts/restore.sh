#!/usr/bin/env bash
# Usage: ./scripts/restore.sh hotel_20260101_120000.dump
set -euo pipefail
file="${1:?usage: restore.sh <file-in-backups>}"
[ -f "backups/$file" ] || { echo "backups/$file not found"; exit 1; }
docker compose stop app
docker compose exec -T db sh -c "pg_restore --clean --if-exists --no-owner -U \$POSTGRES_USER -d \$POSTGRES_DB /backups/$file"
docker compose start app
echo "Restore complete from $file"
