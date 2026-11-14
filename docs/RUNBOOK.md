# Operations runbook

All commands run from the repository root. `docker compose` uses `.env` for configuration.

## Deploy
1. `copy .env.example .env` and set a strong `POSTGRES_PASSWORD` (first time only).
2. `.\scripts\gen-certs.ps1` (first time only; replace with real certs in production).
3. `docker compose pull app` (published image) **or** `docker compose build app` (local build).
4. `docker compose up -d --wait`
5. Verify: `curl.exe -k https://localhost/ready` → `{"status":"ready",...}`

## Restart
| Goal | Command |
|---|---|
| Restart API only | `docker compose restart app` |
| Restart everything | `docker compose restart` |
| Full recreate (data kept) | `docker compose down` then `docker compose up -d --wait` |
| **Destroy data too** (careful) | `docker compose down -v` |

## Status and logs
```
docker compose ps                         # health column: healthy / unhealthy
docker compose logs -f app                # JSON logs, follow
docker compose logs --since 10m app       # recent
docker compose logs db | Select-String ERROR
```
Each request logs `request_id`, `method`, `path`, `status`, `duration_ms`. Every response carries an
`x-request-id` header – search the logs for it to trace one request.

## Backup / restore
```
.\scripts\backup.ps1
.\scripts\restore.ps1 <file-in-backups>
```
Verify after restore: `curl.exe -k https://localhost/reservations/<known-reference>`.
Recommended schedule: daily backup, keep 7 days; copy `backups/` off the host.

## Rollback
Set `APP_TAG` in `.env` to the previous good tag → `docker compose up -d app` → check
`/health` shows that version and `/ready` is 200. (See README for a local rehearsal.)

## Incident response

| Symptom | Likely cause | Check | Fix |
|---|---|---|---|
| `https://localhost` unreachable | Nginx down / cert missing | `docker compose ps`, `docker compose logs nginx` | Generate certs; `docker compose up -d nginx` |
| 502 Bad Gateway | API container down/unhealthy | `docker compose ps`, `logs app` | `docker compose restart app`; rollback if a bad release |
| `/health` 200 but `/ready` 503 | Database down or unreachable | `docker compose ps db`, `logs db`, `logs app` ("readiness check failed") | `docker compose start db`; app recovers automatically |
| App restarting in a loop, log "database unavailable after retries" | DB not healthy / wrong password in `.env` | `logs db`; compare `.env` password with the volume's original | Fix credentials; if password was changed after first start, either revert it or recreate the volume (restore from backup) |
| 409 on every booking | Room genuinely full for those dates | Query `/rooms/availability` | Expected behaviour |
| Data lost / corrupted | Human error, bad migration | Latest file in `backups/` | `restore.ps1`, then verify |
| Disk filling up | Logs or backups | `docker system df`, size of `backups/` | Logs already rotate (10 MB × 3); prune old backups |

**Escalation steps:** 1) confirm with `docker compose ps` and `/ready`; 2) read `logs app` and `logs db`;
3) restart the failed component; 4) if a release caused it, roll back; 5) if data is damaged, restore;
6) record what happened and the fix.

## Failure drills performed (record evidence in README/screenshots)
1. Stop DB → `/ready` 503 → start DB → `/ready` 200.
2. Kill app container → restart policy brings it back healthy.
3. Delete reservations → restore from backup → reservations return.
4. Deploy tag `v2` → roll back to `v1` → `/health` shows `v1`.
