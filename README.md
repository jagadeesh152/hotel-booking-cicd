# Hotel Booking API – Cloud Deployment & CI/CD

![CI](https://github.com/YOUR_USERNAME/hotel-booking-cicd/actions/workflows/ci.yml/badge.svg)

A small **room availability and reservation service** (FastAPI + PostgreSQL) built to demonstrate
production-style **build, release, deployment, observability and recovery** practices.
The application is intentionally small; the engineering around it is the point.

**Highlights**

- Double-booking is impossible: a PostgreSQL **exclusion constraint** rejects overlapping confirmed
  stays, so correctness holds under concurrent requests (proved by tests and `scripts/race_demo.py`).
- Multi-stage, **non-root** Docker image; read-only filesystem, all capabilities dropped.
- Docker Compose stack: Nginx (HTTPS) → API → PostgreSQL, with **health checks**, persistent volume,
  and a database network that has no outside access.
- GitHub Actions: lint, format check, dependency audit, tests against real PostgreSQL, image build,
  Trivy scan, versioned push to GHCR (tag + digest), and a clean-environment deploy smoke test.
- Structured **JSON logs**, separate **liveness** (`/health`) and **readiness** (`/ready`) endpoints.
- Scripted **backup / restore** and a documented **rollback** to a previous image tag.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the diagram and [`docs/RUNBOOK.md`](docs/RUNBOOK.md)
for operations.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness – process is up (no DB call) |
| GET | `/ready` | Readiness – DB reachable (503 if not) |
| GET | `/rooms/availability?room_type=&check_in=&check_out=` | Free rooms for a date range |
| POST | `/reservations` | Create reservation, returns unique reference `HB-XXXXXXXXXX` |
| GET | `/reservations/{reference}` | Look up a reservation |
| GET | `/docs` | Interactive Swagger UI |

Room types: `standard` (5 rooms), `deluxe` (3), `suite` (2) – seeded automatically and repeatably.
Rules: `check_out` after `check_in`, no past dates, max 30 nights, valid email. Stays are half-open
`[check_in, check_out)`, so same-day turnover (out on the 12th, in on the 12th) is allowed.
`POST /reservations` accepts an optional `room_number` to book one specific room.

## Port map

| Port | Service | Exposed to host? |
|---|---|---|
| 80 | Nginx – redirects to HTTPS, `/nginx-health` | Yes |
| 443 | Nginx – TLS termination, proxies to API | Yes |
| 8000 | FastAPI | **No** (internal network only) |
| 5432 | PostgreSQL | **No** (internal network only) |

## Environment variables

| Variable | Used by | Description |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | db, app | Database credentials (set in `.env`, never committed) |
| `APP_IMAGE`, `APP_TAG` | compose | Image to run (default builds locally as `hotel-booking-api:local`) |
| `LOG_LEVEL` | app | `INFO` (default), `DEBUG`, … |
| `DATABASE_URL` | app | Built by Compose; set manually only for local development |
| `MAX_STAY_NIGHTS` | app | Optional, default `30` |

## Quick start – clean machine (Windows PowerShell)

Requires Docker Desktop and Git.

```powershell
git clone https://github.com/YOUR_USERNAME/hotel-booking-cicd.git
cd hotel-booking-cicd

copy .env.example .env          # then edit .env and set a strong POSTGRES_PASSWORD
.\scripts\gen-certs.ps1         # self-signed certificate for https://localhost
docker compose up -d --build --wait

curl.exe -k https://localhost/health
curl.exe -k https://localhost/ready
```

Linux/macOS: `cp .env.example .env && ./scripts/gen-certs.sh && docker compose up -d --build --wait`
(and `chmod 777 backups` so the database container can write backups).

Open **https://localhost/docs** (accept the self-signed certificate warning) to try the API.

```powershell
curl.exe -k "https://localhost/rooms/availability?room_type=suite&check_in=2030-06-10&check_out=2030-06-12"
curl.exe -k -X POST https://localhost/reservations -H "Content-Type: application/json" -d "@docs/sample-booking.json"
```

## Run the tests

Tests use a real PostgreSQL. Start only the database, then run pytest:

```powershell
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# a throw-away database for tests
docker run -d --name hotel-test-db -e POSTGRES_USER=hotel -e POSTGRES_PASSWORD=hotel -e POSTGRES_DB=hotel -p 5432:5432 postgres:16-alpine
$env:DATABASE_URL = "postgresql+psycopg2://hotel:hotel@localhost:5432/hotel"

pytest -v
ruff check . ; ruff format --check .

docker rm -f hotel-test-db
```

The key acceptance tests are `test_two_concurrent_requests_for_same_room_only_one_confirms` and
`test_many_concurrent_requests_never_overbook`. For a live demo against the deployed stack:

```powershell
python scripts/race_demo.py https://localhost
```

## CI/CD pipeline (`.github/workflows/ci.yml`)

| Job | What it does |
|---|---|
| `lint` | `ruff check`, `ruff format --check`, `pip-audit` dependency scan |
| `test` | pytest against a PostgreSQL service container |
| `build` | Builds the image, scans it with Trivy, and (on push to `main` / tags) pushes to GHCR |
| `compose-smoke` | Builds the whole stack from scratch on a clean runner and checks health + a booking over HTTPS |

Image tags: `sha-<short-commit>`, `latest` (main), and `1.2.3` for git tag `v1.2.3`.
The **digest** is printed in each run's *Summary* page. Only the built-in `GITHUB_TOKEN` is used;
no secrets are stored in the repo.

Release a version:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

## Deploy a published image

```powershell
# in .env:
#   APP_IMAGE=ghcr.io/YOUR_USERNAME/hotel-booking-cicd
#   APP_TAG=v1.0.0
docker compose pull app
docker compose up -d
```

(If the GHCR package is private: `docker login ghcr.io` with a personal access token that has `read:packages`.)

## Rollback procedure

Every release is an immutable image tag, so rollback is "run the previous tag".

```powershell
# 1. Note what is running
curl.exe -k https://localhost/health            # shows "version"
# 2. Point to the previous known-good tag in .env (e.g. APP_TAG=v1.0.0)
# 3. Recreate only the app container
docker compose up -d app
# 4. Verify
curl.exe -k https://localhost/ready
```

Local rehearsal without a registry:

```powershell
$env:APP_TAG="v1"; docker compose build app
# ...make a change...
$env:APP_TAG="v2"; docker compose build app; docker compose up -d app    # deploy v2
$env:APP_TAG="v1"; docker compose up -d app                              # roll back to v1
curl.exe -k https://localhost/health                                     # version: v1
```

Database data is untouched by app rollbacks. If data itself is damaged, use backup/restore below.

## Backup & restore

```powershell
.\scripts\backup.ps1                                  # creates backups\hotel_YYYYMMDD_HHMMSS.dump
.\scripts\restore.ps1 hotel_20260101_120000.dump      # stops app, restores, starts app
```

Linux/macOS: `./scripts/backup.sh` and `./scripts/restore.sh <file>`.
Backups use `pg_dump -Fc` (custom format) and are never committed (`backups/` is git-ignored).

## Failure & recovery drill

```powershell
docker compose stop db
curl.exe -k https://localhost/health     # still 200 – process is alive
curl.exe -k https://localhost/ready      # 503 – database is down (detected)
docker compose logs app --tail 20        # JSON log: "readiness check failed"
docker compose start db
curl.exe -k https://localhost/ready      # 200 – recovered, no app restart needed

docker kill hotel-booking-app-1          # crash the API
docker compose ps                        # restart policy brings it back; healthcheck turns healthy
```

## Security notes

- Secrets only via `.env` (git-ignored); `.env.example` has placeholders. CI uses a throw-away password.
- App container: non-root user, read-only root filesystem, `cap_drop: ALL`, `no-new-privileges`.
- Database and API are on internal networks; only Nginx publishes ports. The DB network is `internal: true`.
- TLS 1.2/1.3 only, HSTS and basic security headers at Nginx. Local demo uses a self-signed
  certificate; for a public host replace `nginx/certs/server.*` with Let's Encrypt certificates.
- Dependabot keeps pip, Docker and Actions dependencies current; CI runs `pip-audit` and Trivy.

## Known limitations / assumptions

- Local self-signed TLS; no paid cloud hosting (not required by the brief).
- Metrics (Prometheus) are not implemented – a stretch goal; logs + health/readiness cover observability.
- No authentication or payments – out of scope for this assessment.
- Trivy runs in report-only mode so a base-image CVE does not block a release; set `exit-code: "1"` to enforce.
