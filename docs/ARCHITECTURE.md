# Architecture

```mermaid
flowchart LR
    U[User / API client] -->|HTTPS 443| N[Nginx reverse proxy<br/>TLS termination]
    N -->|HTTP 8000<br/>frontend network| A[FastAPI app<br/>non-root, read-only]
    A -->|5432<br/>backend network, internal| D[(PostgreSQL 16<br/>volume: pgdata)]
    D -. pg_dump / pg_restore .-> B[/backups folder/]

    subgraph CI/CD - GitHub Actions
      direction LR
      G[Git push / PR] --> L[Lint + format + pip-audit]
      L --> T[Tests on PostgreSQL]
      T --> I[Build image + Trivy scan]
      I --> R[(GHCR: tag + digest)]
      T --> S[Compose smoke test]
    end
    R -. docker compose pull .-> A
```

## Components

| Component | Responsibility | Exposure |
|---|---|---|
| Nginx | TLS, HTTP→HTTPS redirect, security headers, reverse proxy | Ports 80, 443 |
| FastAPI | Availability + reservation API, `/health`, `/ready`, JSON logs | Internal 8000 |
| PostgreSQL | Rooms + reservations, exclusion constraint prevents overlaps | Internal only |
| GitHub Actions | Verify, build, scan, publish versioned image | – |

## Data model

```mermaid
erDiagram
    rooms ||--o{ reservations : "has"
    rooms {
      int id PK
      string room_number UK
      string room_type
      numeric price_night
    }
    reservations {
      int id PK
      string reference UK
      int room_id FK
      string guest_name
      string guest_email
      date check_in
      date check_out
      string status
      timestamptz created_at
    }
```

**Overlap rule** (in `app/schema.sql`):

```sql
EXCLUDE USING gist (room_id WITH =, daterange(check_in, check_out, '[)') WITH &&)
WHERE (status = 'confirmed')
```

Why in the database and not in application code: a "check then insert" in Python has a race window
between the two steps. The constraint is enforced atomically by PostgreSQL, so two concurrent
requests can never both commit. The app catches the violation and tries the next free room, or
returns `409 Conflict` when none is left.
