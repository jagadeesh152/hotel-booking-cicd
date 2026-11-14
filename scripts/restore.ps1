# Usage: .\scripts\restore.ps1 hotel_20260101_120000.dump
param([Parameter(Mandatory = $true)][string]$File)
if (-not (Test-Path "backups/$File")) { throw "backups/$File not found" }
docker compose stop app
docker compose exec -T db sh -c ('pg_restore --clean --if-exists --no-owner -U $POSTGRES_USER -d $POSTGRES_DB /backups/' + $File)
docker compose start app
Write-Host "Restore complete from $File"
