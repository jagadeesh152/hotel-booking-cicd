#!/usr/bin/env bash
set -euo pipefail
name="hotel_$(date +%Y%m%d_%H%M%S).dump"
docker compose exec -T db sh -c "pg_dump -U \$POSTGRES_USER -Fc \$POSTGRES_DB -f /backups/$name"
echo "Backup created: backups/$name"
