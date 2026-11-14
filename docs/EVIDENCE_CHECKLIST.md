# Evidence checklist (screenshots / links for the submission form)

| # | Evidence | How to capture |
|---|---|---|
| 1 | Repo URL, branch `main`, final commit ID | `git rev-parse HEAD` |
| 2 | Green CI run (all 4 jobs) – URL + screenshot | GitHub → Actions → run |
| 3 | Image tag + digest | Run *Summary* page, or GitHub → Packages |
| 4 | Test output incl. concurrency tests | `pytest -v` screenshot |
| 5 | `race_demo.py` output (1× 201, 9× 409) | `python scripts/race_demo.py https://localhost` |
| 6 | Stack running | `docker compose ps` (all healthy) |
| 7 | HTTPS + health/ready | `curl.exe -k https://localhost/ready` and browser `/docs` |
| 8 | Structured logs | `docker compose logs app --tail 20` |
| 9 | Failure → detection → recovery | stop db, `/ready` 503, start db, `/ready` 200 |
| 10 | Backup file created | `.\scripts\backup.ps1` + `dir backups` |
| 11 | Restore shows data returned | delete rows, restore, query reservation |
| 12 | Rollback v2 → v1 | `/health` version before/after |
| 13 | Trivy scan section of the build job | Actions → build → scan step |

Demo video (3–5 min): pipeline run → `docker compose ps` → `/ready` + logs → race demo →
stop DB/recover → backup → delete → restore → rollback.
