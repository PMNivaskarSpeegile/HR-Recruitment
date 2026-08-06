# Recruitment ATS — Applicant Tracking System

A role-based recruitment ATS (Phase 1) built with **Django REST Framework + PostgreSQL** (React frontend planned). It tracks requirements, candidates, and the screening pipeline for a small recruitment team.

## Roles
| Role | Code | Does |
|------|------|------|
| Administrator | `ADM` | Manages users, master data, full access |
| Hiring Manager | `HM` | Creates requirements, assigns recruiters |
| Recruiter | `REC` | Uploads candidates, works the screening pipeline |

## Tech stack
- **Backend:** Django 6 · Django REST Framework · SimpleJWT
- **Database:** PostgreSQL (schema `ats`, tables `managed = False`)
- **Config:** environment-driven via `.env` (`python-dotenv`)
- **Frontend:** React + Tailwind + shadcn/ui *(planned)*

## Quick start
```bash
# 1. create & fill environment file
cd backend
copy .env.example .env        # then edit values

# 2. install deps
pip install -r requirements.txt

# 3. apply the database migrations (raw SQL, since tables are managed=False)
python manage.py migrate_sql 0001_phase1_pipeline.sql
python manage.py migrate_sql 0002_workflow_masters.sql
python manage.py migrate_sql 0003_email_template.sql

# 4a. seed one user per role  (all password: Speegile@123)
python manage.py seed_users

# 4b. (optional) seed realistic Indian demo data — clients, candidates,
#     requirements & a full pipeline for an end-to-end demo
python manage.py seed_demo

# 5. run
python manage.py runserver
```
Login: `POST /api/auth/login/` with `{"username","password"}` → returns a JWT used as `Authorization: Bearer <token>`.

## Documentation (`docs/`)
| File | Contents |
|------|----------|
| [ROADMAP.md](docs/ROADMAP.md) | Phased plan + build log (resume pointer) |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Layered design + system/module/API-flow diagrams |
| [DATABASE.md](docs/DATABASE.md) | Schema, tables, migrations, status codes |
| [API.md](docs/API.md) | Endpoint reference |
| [ER_DIAGRAM.md](docs/ER_DIAGRAM.md) | Entity-relationship diagram |
| [SEQUENCE_DIAGRAMS.md](docs/SEQUENCE_DIAGRAMS.md) | Workflow, sequence & state diagrams |
| [RBAC.md](docs/RBAC.md) | Roles & permission matrix |
| [DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) | Frontend design tokens & component library |
| [CHANGELOG.md](docs/CHANGELOG.md) | Version history |

## Status
Backend: Foundation + **UC1–UC5 complete & verified** + **hardening** (16 pytest tests, Swagger at `/api/docs/`, security). Frontend: **feature-complete — the full UC0–UC5 workflow** is in the UI (login, role dashboards, requirements, candidates + Excel upload, screening pipeline) plus the **JD email module** (admin-editable template → compose/preview → send → tracker). Remaining work is polish/hardening (richer seed data, code-split, frontend tests, deployment). See [ROADMAP.md](docs/ROADMAP.md).

**Backend dev/test:** `pip install -r requirements-dev.txt`, then `pytest` from `backend/`. API docs at `/api/docs/`.

## Frontend (`frontend/`)
React + TypeScript (Vite) + Tailwind + shadcn-style components.
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173  (API base from frontend/.env)
```
The backend must be running on `http://127.0.0.1:8000` (CORS already allows `localhost:5173`).
