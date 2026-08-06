# Deployment — Speegile ATS

Two ways to run the stack: **Docker Compose** (recommended — one command, same on
Windows/macOS/Linux) and **local/manual** (see `database/README.md` + `README.md`).

The stack has three services:

| Service    | Tech                     | Port (host) | Notes |
|------------|--------------------------|-------------|-------|
| `db`       | PostgreSQL 16            | 5432        | Loads schema + reference data on first start |
| `backend`  | Django + DRF (gunicorn)  | 8000        | REST API at `/api/…` |
| `frontend` | React/Vite built → nginx | 8080        | Serves the SPA; proxies `/api` → backend |

---

## 1. Run with Docker (local)

**Prerequisite:** Docker Desktop (Windows/macOS) or Docker Engine + Compose (Linux).

```bash
# from the repo root
cp .env.example .env          # then edit SECRET_KEY and DB_PASSWORD
docker compose up --build
```

On first start the `db` container creates the database and loads
`database/ats db schema.sql` (schema) + `database/ats insert data 2.sql`
(reference/lookup data). Then create the login users and demo data **once**:

```bash
docker compose exec backend python manage.py seed_demo
```

Open **http://localhost:8080** and log in.

Useful commands:

```bash
docker compose logs -f backend        # follow API logs
docker compose exec backend python manage.py <cmd>   # any manage.py command
docker compose down                   # stop (keeps the db volume)
docker compose down -v                # stop and DELETE the db volume (fresh start)
```

> The schema/reference SQL only runs when the `pgdata` volume is empty. To reload
> it from scratch, `docker compose down -v` then `up` again.

---

## 2. Configuration (environment variables)

Set these in `.env` (compose) or in your cloud platform's env settings.

| Variable | Purpose | Example |
|---|---|---|
| `SECRET_KEY` | Django secret — **must** be a long random string | *(generated)* |
| `DEBUG` | `False` in production (turns on HSTS, secure cookies, SSL redirect) | `False` |
| `ALLOWED_HOSTS` | Hosts/domains that may serve the API | `api.example.com` |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Database credentials | `ats_db` / `postgres` / … |
| `DB_HOST` / `DB_PORT` | Database location (`db` inside compose) | `db` / `5432` |
| `DB_SCHEMA` | Postgres search path | `ats,public` |
| `CORS_ALLOWED_ORIGINS` | Frontend origin(s) allowed to call the API | `https://app.example.com` |
| `JWT_ACCESS_HOURS` / `JWT_REFRESH_DAYS` | Token lifetimes | `8` / `7` |

Generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`.env` files are git-ignored — never commit real secrets. Only `*.example` files
are tracked.

---

## 3. Cross-platform

The stack is platform-neutral: Python, Node, and PostgreSQL all run on Windows,
macOS, and Linux, config is env-driven (no hardcoded paths), and `.gitattributes`
normalises line endings. With Docker the host OS doesn't matter at all — the
containers are Linux either way.

---

## 4. Hosting on the cloud

The images are standard, so any container host works. General steps:

1. **Managed Postgres** — use the provider's database (AWS RDS, Render/Railway
   Postgres, Azure Database, etc.) instead of the `db` container. Point
   `DB_HOST/DB_NAME/DB_USER/DB_PASSWORD` at it. Load the schema + reference data
   once: `psql "$DATABASE_URL" -f "database/ats db schema.sql"` then
   `psql "$DATABASE_URL" -f "database/ats insert data 2.sql"`, then run
   `python manage.py seed_demo` (or `seed_users` for just the accounts).
2. **Backend** — deploy `backend/Dockerfile`. Set all env vars, `DEBUG=False`, a
   real `SECRET_KEY`, and `ALLOWED_HOSTS` = your API domain. The container runs
   `collectstatic` + gunicorn on port 8000; WhiteNoise serves admin/DRF static.
3. **Frontend** — build `frontend/Dockerfile` with
   `--build-arg VITE_API_BASE_URL=https://<your-api-domain>/api` (or keep `/api`
   and put the API behind the same domain/reverse proxy). nginx serves the SPA.
4. **HTTPS** — terminate TLS at the platform's load balancer / reverse proxy.
   With `DEBUG=False` Django already sets HSTS, secure cookies, and SSL redirect.
5. **Persistence** — the database volume must be a managed/persistent disk.
   Uploaded résumés live in `backend/uploads` — mount a persistent volume or move
   to object storage (S3) for a multi-instance deployment.

**Beginner-friendly options:** Render or Railway can build from this repo
directly (one web service per Dockerfile + a managed Postgres add-on). For AWS,
push both images to ECR and run them on ECS/Fargate with an RDS Postgres.

### Pre-deploy checklist
- [ ] `SECRET_KEY` set to a fresh random value (not the example)
- [ ] `DEBUG=False`
- [ ] `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` set to real domains
- [ ] Managed Postgres provisioned; schema + reference data loaded; `seed_demo` run
- [ ] Persistent storage for the database (and for `uploads/` if used)
- [ ] HTTPS enabled at the proxy/load balancer
