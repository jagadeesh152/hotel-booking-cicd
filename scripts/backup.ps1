# Creates a timestamped PostgreSQL backup in ./backups
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$name = "hotel_$ts.dump"
docker compose exec -T db sh -c ('pg_dump -U $POSTGRES_USER -Fc $POSTGRES_DB -f /backups/' + $name)
if ($LASTEXITCODE -ne 0) { throw "backup failed" }
Write-Host "Backup created: backups/$name"
