# Database (Speegile ATS)

The ATS database is **managed manually**: the Django models use `managed = False`,
so **SQL is the source of truth**, not Django migrations. `manage.py migrate` does
**not** create these tables.

| File | Purpose |
|------|---------|
| **`ats db schema.sql`** | The **complete current schema** for a fresh database (schema `ats`: 34 tables + all columns, PKs, FKs, checks, unique constraints, indexes, sequences/defaults). Generated from the live DB; equal to the base schema + every `migrations/*.sql` applied. |
| **`ats insert data 2.sql`** | The **official reference/master (lookup) data seed** — roles, requirement/candidate/application/position statuses, priorities, notice periods, req types, work modes, sources, screening modes, rejection reasons, and the JD email template. Lookup data only; **no** transactional/demo rows. Idempotent (`ON CONFLICT DO NOTHING`). |
| **`migrations/*.sql`** | **Numbered, ordered** incremental changes for **evolving an existing** database (see `migrations/README.md`). A fresh DB from `ats db schema.sql` already contains all of these — do **not** replay them. |

> The schema file is authoritative. Regenerate it whenever you add a numbered
> migration (see *Regenerating the schema* below) so the two never drift.

---

## From-scratch setup

A new developer can go from nothing to a running app with **no manual database
edits**. There is **one official seeding process** (steps 4 + 5 below): the
reference SQL provides the lookup/enum data, then `seed_demo` creates users and a
realistic demo dataset. `seed_demo` alone is **not** sufficient on an empty DB — it
looks up the reference rows the SQL seeds.

### 0. Prerequisites

- **PostgreSQL 14+** (the schema is generated with v18; 14+ works — it uses
  `GENERATED ... AS IDENTITY`, `JSONB`, and standard constraints). Install from
  <https://www.postgresql.org/download/>. On Windows the client tools live under
  e.g. `C:\Program Files\PostgreSQL\18\bin` — add that to `PATH` or call the exes
  by full path.
- **Python 3.11+** and **Node.js 18+** (for the frontend).

Run the commands from the **repo root** unless noted.

### 1. Create the database

```bash
createdb -U postgres ats_db
# or:  psql -U postgres -c "CREATE DATABASE ats_db;"
```

### 2. Apply the schema

```bash
psql -U postgres -d ats_db -v ON_ERROR_STOP=1 -f "database/ats db schema.sql"
```

Creates the `ats` schema and every table/constraint/index. Idempotent at the schema
level (`CREATE SCHEMA IF NOT EXISTS`); keeps the convention `SET search_path = ats, public;`.

### 3. Load reference/master (lookup) data

```bash
psql -U postgres -d ats_db -v ON_ERROR_STOP=1 -f "database/ats insert data 2.sql"
```

Seeds the static lookup/enum rows the application and the seeder depend on. Safe to
re-run.

### 4. Configure the backend environment

```bash
cd backend
cp .env.example .env            # Windows: copy .env.example .env
```
Edit `backend/.env` and set at least `SECRET_KEY` and `DB_PASSWORD`; the DB block
should match your Postgres:
```
DB_NAME=ats_db  DB_USER=postgres  DB_HOST=localhost  DB_PORT=5432  DB_SCHEMA=ats,public
```
Generate a secret key:
`python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`

### 5. Install backend dependencies

```bash
python -m venv .venv
. .venv/Scripts/activate         # Windows Git Bash;  .venv\Scripts\activate on cmd/PowerShell;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
```

### 6. Seed demo data (users + demo pipeline)

```bash
python manage.py seed_demo
```

Creates demo users and a realistic pipeline. Idempotent. All demo logins share the
password printed at the end (`Speegile@123`): `priya.sharma` (Admin), `rajeev.mehta`
(Recruiter), `ankit.desai` (Hiring Manager), etc.

> This is the **only** supported seeding process: reference SQL (step 3) +
> `seed_demo` (step 6). The `manage.py seed_users` command (one bare login per role)
> exists for minimal test setups but is not part of the standard flow.

### 7. Run the backend

```bash
python manage.py runserver          # serves the API at http://127.0.0.1:8000/api
```

### 8. Run the frontend

```bash
cd ../frontend
npm install
# frontend/.env already points at the local API:
#   VITE_API_BASE_URL=http://127.0.0.1:8000/api
npm run dev                         # Vite dev server (prints the URL, e.g. http://localhost:5173)
```

Log in with any demo account above.

### 9. Verify model ↔ schema sync (optional but recommended)

```bash
cd ../backend && python check_schema_drift.py
```

Compares every `managed = False` model against the live database and reports missing
tables/columns, type mismatches, missing FKs, and missing indexes. Expected output:
**NO DRIFT** (models match all 34 tables).

---

## Evolving an existing database

Add a new numbered file under `migrations/` and apply it — never edit an
already-applied migration.

```bash
python backend/manage.py migrate_sql 0020_your_change.sql
# or:  psql -U postgres -d ats_db -f database/migrations/0020_your_change.sql
```

Then **update `ats db schema.sql`** (regenerate, below), update the matching
`managed = False` model, and re-run `check_schema_drift.py`.

## Regenerating the schema file

`ats db schema.sql` is produced from the live database and normalized (drops psql
`\restrict` meta and the empty-search-path reset; installs
`SET search_path = ats, public;`):

```bash
pg_dump -h localhost -U postgres -d ats_db --schema-only -n ats \
        --no-owner --no-privileges -f dump.sql
# then apply the header/search_path normalization (see the file header).
```

Verify by loading the regenerated file into a throwaway DB and diffing object
counts/column signatures against `ats_db`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `psql: FATAL: password authentication failed` | Wrong `DB_PASSWORD`. Set it in `backend/.env` and use the same for `psql` (set `PGPASSWORD` or enter when prompted). |
| `psql: command not found` (Windows) | Add `C:\Program Files\PostgreSQL\<ver>\bin` to `PATH`, or call `psql`/`createdb`/`pg_dump` by full path. |
| `relation "ats.xxx" does not exist` when seeding | Schema step skipped/failed. Re-run step 2 with `-v ON_ERROR_STOP=1` and check for errors. |
| `seed_demo` raises `KeyError` (e.g. a status code) | Step 3 (reference data) was not loaded, or was loaded into a different DB. Run `ats insert data 2.sql` against the same `DB_NAME`. |
| `django.db.utils.OperationalError: could not connect` | Postgres not running, or wrong `DB_HOST`/`DB_PORT`. Start the service and confirm `psql -U postgres -d ats_db` connects. |
| Tables missing after `manage.py migrate` | Expected — ATS tables are `managed = False`. Use `ats db schema.sql` (step 2), not `migrate`. |
| `permission denied to create database` | Use a superuser (e.g. `postgres`) or grant `CREATEDB` to your role. |
| Frontend shows network/CORS errors | Backend not running or `VITE_API_BASE_URL` mismatched. Start `runserver` and confirm the URL in `frontend/.env`. |
| `check_schema_drift.py` reports drift after a change | The model and SQL disagree. Fix the model to match the schema (or add a migration + regenerate the schema). |
