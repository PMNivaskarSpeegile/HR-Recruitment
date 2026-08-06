# API Reference

Base URL: `/api/` · Auth: `Authorization: Bearer <jwt>` (except login).
List endpoints are paginated: `{count, next, previous, results}` (20/page, `?page_size=` up to 100).
Errors use a uniform envelope: `{ "success": false, "status_code": <n>, "error": {...} }` (frontend unwraps via `lib/apiError.ts`).

**Auth failures → `401`, not `403`.** The JWT auth class sets a `WWW-Authenticate: Bearer` header (`authenticate_header`), so a missing / malformed / expired / invalid token returns **401** (the frontend's axios interceptor treats only 401 as "session gone → re-login"). A *role/permission* denial on an authenticated user is still `403`.

**Interactive docs:** Swagger UI at `/api/docs/`, ReDoc at `/api/redoc/`, raw OpenAPI 3 at `/api/schema/`.

## Authentication
- `GET /api/auth/me/` — verify the current JWT; returns `{user_id, full_name, username, email, role:{id,code,name}}` (any role). `401` if missing/invalid. Called on startup so a restored session is only trusted once the backend confirms the token.

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/api/auth/login/` | none | `{username, password}` → `{message, token, user}`. Throttled (scope `login` → `429`). Bad creds → `401`; inactive account → `403`. Constant-time to avoid username enumeration. |

## Admin / Profile
| Method | Path | Role | Notes |
|--------|------|------|-------|
| GET | `/api/profile/` | **ADM only** | `{user_id, full_name, username, email, role}` (role as display name). Admin-only (`IsAdministrator`). |
| GET | `/api/dashboard/` | any auth | Role-aware summary — see [Dashboard](#dashboard). |

## Master data (UC0)
**Writes (create/update/delete) require ADM; reads require any authenticated user** (`IsAdminOrReadOnly`) — with two carve-outs below.
**Exception 1 — inline reference creation:** `/api/skills/` and `/api/locations/` allow **POST (create) by ADM *or* HM** (a Hiring Manager can add a missing skill/location from the New Requirement form without leaving it); **edit/delete remain ADM-only** (`CanManageReferenceData`, [authentication/permissions.py](backend/authentication/permissions.py)).
**Exception 2 — `/api/users/` is Admin-only for *everything* (incl. reads)** (`IsAdministrator`): the user directory is staff PII, not dropdown data, so recruiters/HMs never enumerate staff. The only non-admin user-picking flow (recruiter assignment) is itself Admin-only.

CRUD ViewSets (list/create/retrieve/update/delete), searchable/filterable:
`/api/roles/`, `/api/users/` *(ADM-only)*, `/api/domains/`, `/api/skills/`, `/api/clients/`, `/api/client-managers/`, `/api/locations/`, `/api/sources/`, `/api/req-status/`, `/api/candidate-status/`, `/api/application-status/`, `/api/position-status/`, `/api/priorities/`, `/api/notice-periods/`, `/api/req-types/`, `/api/work-modes/`, `/api/screening-modes/`, `/api/rejection-reasons/`, `/api/email-templates/`. *(`/api/interview-rounds/` removed in 0002; `/api/cv-status/` removed in 0008 — split into candidate-status + application-status.)*

**User create/update (`/api/users/`):** accepts a write-only `password` (hashed to `password_hash`; never returned). Password is **required on create**, optional on update, and — whenever supplied — is run through Django's `AUTH_PASSWORD_VALIDATORS`; a weak password → `400 {password:[…]}`.

**Skills & Domains (0005):** a Skill references a **Domain** via `domain_id` (required). `/api/skills/` returns `domain` (id) + read-only `domain_name`; renaming a domain reflects on all skills automatically. `/api/domains/` is **Admin-only for writes** (any authenticated user reads it so the Skill form's dropdown works) — Hiring Managers can *select* a domain when creating a skill inline but cannot create/edit/delete domains. A domain referenced by skills can only be deactivated (permanent delete → `409 referenced`). Domains classify Skills only; Candidates/Requirements reference Skills, never Domains.

**Auto-generated Code (status/type/mode masters):** for req-status, candidate/application/position-status, work-modes, screening-modes, rejection-reasons and req-types, the `*_code` field is a **permanent system identifier**. On **create** it defaults to an UPPER_SNAKE slug of the name but the admin may **edit it once**; the supplied value is normalised (`generate_code`), format-checked (`^[A-Z][A-Z0-9_]*$`) and must be unique. On **update** the code is **frozen** — the API drops any code field, so renaming the display name never changes it. (`client_code` / `template_code` remain fully user-entered.)

**Shared CRUD contract (every master, enforced centrally in `MasterDataViewSet` + `core/validation.py`):**
- **Normalisation + validation** on create/update — trim/collapse/clean text; general text fields are **Title-Cased** with a canonical map for technical terms (`github`→`GitHub`, `sql`→`SQL`, …) and acronym preservation; codes upper-cased. Per-field character rules, max-length. Invalid input → `400` with `{field: message}`.
- **Duplicate prevention** — case-/space-insensitive on unique fields & unique-together groups → `400`. If the match is an **inactive** row → `409 {code:"inactive_duplicate", record:{id,label}}` (reactivate instead).
- `GET /api/{master}/?is_active=true` — list filter so dropdowns show only active rows.
- `DELETE /api/{master}/{id}/` — **soft delete** (`is_active=false`); returns `200 {detail, is_active:false}`.
- `DELETE /api/{master}/{id}/permanent/` — **hard delete**, only if unreferenced; referenced → `409 {code:"referenced", detail, details[]}`; success → `204`.
- `GET /api/{master}/{id}/references/` — `{referenced, total, details:[{entity, count}]}`.
- **Optimistic locking** — send `expected_updated_on` on update; a stale token → `400 {code:"stale"}`.
- Audit (`created_by/on`, `updated_by/on`) filled automatically; `is_active` defaults to true.

## Requirements (UC1)
Read serializer (`fields="__all__"` + friendly names) also returns: `is_expired`/`expired_on` (derived Expired overlay — Target Fill Date passed while non-terminal), `position_counts` (per-seat breakdown), `active_application_count` (open, not-closed applications), `recruitment_ended`/`_on`/`_by`/`_by_name`.

**Expiry is read-only:** when a requirement `is_expired` (and not `recruitment_ended`), `PUT/PATCH` accepts **only `target_fill_date`** (extending it resumes normal ops); any other field → `400`. A `recruitment_ended` requirement is fully read-only. `set-status`, `set-position-status`, `add-positions`, `delete-position` are likewise blocked while expired/ended.

| Method | Path | Role | Notes |
|--------|------|------|-------|
| GET | `/api/requirements/` | any auth | **role-scoped:** ADM → all; REC → only `recruiter`=self; HM → only `hiring_mgr`=self. Filters: `req_status, priority, client, recruiter, hiring_mgr, req_type`; plus server-side `?status=<code>` / `?status=active` (excludes terminal), `?missing=recruiter` / `?missing=hm` (unassigned). Search: tracker no / serial / role / client_req_id / client name |
| POST | `/api/requirements/` | HM, ADM | auto `Req_TrackerNo` + `JD_Serial_Number`; status→New; **auto-creates `positions_open` Open seats**. `req_status` not accepted (workflow-only) |
| GET | `/api/requirements/{id}/` | any auth | role-scoped; a REC/HM hitting a requirement that isn't theirs gets **404** (also applies to every detail action + update) |
| PUT/PATCH | `/api/requirements/{id}/` | **HM only** | edit is Hiring-Manager-only (Admin → `403`); expiry read-only rule above applies |
| DELETE | `/api/requirements/{id}/` | HM, ADM | |
| POST | `/api/requirements/{id}/assign/` | **ADM only** | `{recruiter}` → status Assigned. Reassign is Admin-only; HM & Recruiter → `403`. Non-recruiter / inactive user → `400` |
| POST | `/api/requirements/{id}/set-status/` | **HM only** | `{to_status:"HOLD\|OPEN\|CANCELLED\|CLOSE_LOST", reason?}` — manual lifecycle. Hold/Cancel from any active state; Resume (Hold→Open); Reopen (Cancelled → Open, pipeline preserved); Close Lost is terminal. Illegal targets (event/position-driven: New/Assigned/Open/Partial/Close Filled) → `400`. Admin & Recruiter → `403`. Blocked if expired/ended |
| POST | `/api/requirements/{id}/end-recruitment/` | **HM only** | Permanently stop recruiting an **EXPIRED, partially-filled** requirement. Closes every still-active application as *Positions Withdrawn* and returns those candidates to Talent Pool; requirement stays PARTIAL_FILLED + Expired (no new status), filled seats + history preserved. Response = read payload + `applications_closed`. Admin & Recruiter → `403`. Irreversible |
| GET | `/api/requirements/{id}/positions/` | any auth | the requirement's seats (`position_no`, status, `filled_by_candidate`, `auto_inactive`). Tracked independently of candidates |
| POST | `/api/requirements/{id}/set-position-status/` | **HM only** | `{position_id, to_status:"OPEN\|HOLD\|CANCELLED"}`. Allowed: `Open↔Hold`, `Open/Hold→Cancelled`, `Cancelled→Open`. Manual `Filled` rejected (`400`) — seats fill only on Join; Filled is terminal. Admin & Recruiter → `403`. Recomputes rollup |
| POST | `/api/requirements/{id}/add-positions/` | HM, ADM | `{count}` — add N Open seats to an **active** requirement (New/Assigned/Open/Partial); a Filled req becomes Partially Filled. Blocked when closed/expired/ended → `400` |
| POST | `/api/requirements/{id}/delete-position/` | HM, ADM | `{position_id}` — remove a seat only if never Filled and no recruitment activity (else Cancel it). Blocked when expired |
| GET | `/api/requirements/{id}/status-history/` | any auth | combined requirement + position audit timeline (`StatusChangeHistory`, newest first) |

## Candidates (UC2)
| Method | Path | Role | Notes |
|--------|------|------|-------|
| GET | `/api/candidates/` | any auth | **status-scoped (backend-enforced):** REC/ADM default hides `REJECT_HOLD/JOINED/FAKE/BLACKLISTED`; `?status=<code>` filters, `?status=ALL` shows all. **HM only ever sees `NEW_CV`+`SAVED`** plus candidates mapped to reqs they own. `?requirement=<id>` shows only that req's mapped candidates (access-checked). `?skill=<id>` **repeatable → AND** filter. Search: name/mobile/email/company/location city+state; filters: source/notice_period/work_mode/current_location/uploaded_by/is_willing_to_relocate. List shows only `is_active` rows |
| POST | `/api/candidates/` | REC, ADM | duplicate logic → `201 {action:"created"}` / `200 {action:"updated"}` / **`409` possible-duplicate** (same-mobile/diff-email → `{reason, existing_candidate, submitted}`, nothing written). Optional `requirement` (Review-Pool tag; §9 authz + must be open), `skill_ids` |
| GET/PUT/PATCH | `/api/candidates/{id}/` | REC, ADM (write) | write serializer does **not** expose `candidate_status` — profile status is only settable via `set-status` |
| POST | `/api/candidates/{id}/verify-profile/` | REC, ADM | Verify & update the **master** profile (all non-system fields + `skill_ids` + `verified`), and optionally apply one `decision` (SHORTLIST/NOT_SUITABLE/FAKE/BLACKLIST/SAVE with `requirement`/`decision_reason`/`move_to_talent_pool`). Identity change re-runs duplicate detection → collision opens a review + **409** (not saved). Response: `{candidate, changed_fields, verified, decision}`. HM read-only → `403` |
| POST | `/api/candidates/{id}/set-status/` | REC, ADM | `{status_code, reason}` — mark **Fake** or **Blacklisted** (the only hand-settable statuses; lifecycle → `400`). `reason` **mandatory**. The two are mutually exclusive → `400` |
| POST | `/api/candidates/{id}/clear-status/` | **ADM only** | `{reason?}` — remove a Fake/Blacklisted mark, restore to **Talent Pool**. Only valid when currently Fake/Blacklisted → else `400`. Logged |
| POST | `/api/candidates/{id}/tag-requirements/` | REC, ADM | `{requirement_ids:[…]}` (or `{requirement}`) — add candidate to req Review Pool(s) ("under review"). §9: only each req's assigned recruiter (or admin) may tag → else `403`. Never creates a mapping |
| POST | `/api/candidates/{id}/untag-requirement/` | REC, ADM | `{requirement}` — remove from a req's Review Pool. §9 authz |
| GET | `/api/candidates/{id}/detail/` | any auth | drawer payload: `{candidate, resume, requirement_history[], active_reviews[], timeline[]}` (read-only). `resume.available` = file on disk; `active_reviews` = current Review-Pool associations |
| GET | `/api/candidates/{id}/resume/` | any auth | streams the active `cv_document` (`FileResponse`); `404` when no file on disk |
| GET | `/api/candidates/upload-template/` | any auth | downloads `.xlsx` import template (headers + one example row) |
| POST | `/api/candidates/bulk-preview/` | REC, ADM | multipart `file` — **validate only** (no candidate writes) + persist a reusable **DRAFT batch**; returns a per-row report (`ok`, per-row status, `batch_id`) so import can confirm this exact dataset. Invalid → `400` |
| POST | `/api/candidates/bulk-upload/` | REC, ADM | **Preferred:** `batch_id` (confirms a preview DRAFT — imports the exact validated dataset; must be your own draft). **Fallback:** raw multipart `file`. Optional `requirement` (Review-Pool tag, §9 authz) + `source` (id or name; defaults to Naukri). Per-row report |
| GET | `/api/candidates/unmapped-locations/` | REC, ADM | distinct import "kept as text" locations (Location FK still NULL) with candidate counts + a suggested master match |
| POST | `/api/candidates/reconcile-location/` | REC, ADM | `{text, location_id}` — map every unmapped candidate with that exact text to an existing Location Master city (sets FK, clears text). Does NOT create master rows → `400` if missing |

### Duplicate reviews
A **separate** process from candidate status (never sets "Possible Duplicate" on a candidate).

| Method | Path | Role | Notes |
|--------|------|------|-------|
| POST | `/api/duplicate-reviews/` | REC, ADM | submit a detected duplicate → `PENDING` (dedupes an existing pending review). Body: `{existing_candidate, new_candidate_name, new_mobile, new_email?, detection_reason, submitted_payload?}` |
| GET | `/api/duplicate-reviews/` | **ADM only** | list; filters `?review_status=PENDING\|RESOLVED`, `?resolution=<code>`. Includes both records + full audit (created/resolved by+on) |
| POST | `/api/duplicate-reviews/{id}/resolve/` | **ADM only** | `{resolution, notes?, name?, mobile?, email?}`. Resolutions: **`UPDATED` (primary)** — write the chosen name/mobile/email onto the **existing** candidate (submitted row never imported); **`KEPT_SEPARATE`** — dismiss / "Ignore submission". Legacy `MERGED`/`CORRECTED` behave exactly like `UPDATED`. Applying a mobile/email already on another candidate → `400` (review stays open). Already resolved → `400` |

### Import batches (bulk-upload history)
`GET`-only ViewSet — recruiters see their own uploads, admins see all; DRAFT (preview) batches are excluded.

| Method | Path | Role | Notes |
|--------|------|------|-------|
| GET | `/api/import-batches/` | REC, ADM | list — summary rows (`total_rows`, `created/updated/duplicate/skipped_count`, `status`, timestamps) |
| GET | `/api/import-batches/{id}/` | REC, ADM | detail — adds `file_hash`, full `row_report`, `error_message` |
| GET | `/api/import-batches/{id}/report/` | REC, ADM | re-download the per-row report as `.xlsx` |
| POST | `/api/import-batches/{id}/rollback/` | REC (uploader), ADM | soft-delete the still-untouched candidates this batch created. Only a `COMPLETED` batch → else `400`; non-owner recruiter → `403` |
| POST | `/api/import-batches/{id}/mark-failed/` | **ADM only** | recovery for a batch stuck in `PENDING` → `FAILED`. Any other status → `400` |

## Pipeline (UC3–UC5)
Recruiter data-scope: a recruiter may only act on requirements **assigned to them** (admin bypasses) → otherwise `403`. Action endpoints also require the requirement to be *workable* (not Hold/Cancelled/Closed Lost, not expired, not recruitment-ended) → else `400`. Reads are never blocked by state.

`JdCvMapping` read serializer returns both the STAGE and the last OUTCOME (independent): `application_stage`/`_name`/`_code` (current stage — the single source of truth for per-requirement progress) **and** `latest_outcome`/`latest_outcome_name`/`latest_outcome_code`, plus `is_closed`/`closed_on`, `screening_mode`/`_name`, `screening_datetime`, `rejection_reason`/`_name`, candidate identity fields.

| Method | Path | Role | Notes |
|--------|------|------|-------|
| GET | `/api/pipeline/new-cvs/?requirement=<id>` | REC (assigned), ADM | usable candidates (New_CV or Saved, not already mapped), annotated `matched_skills`/`required_skills`/`skill_match_pct`, **ranked by relevance**. Paginated (`page`,`page_size`≤100) + `search=` name/email/mobile/cv_serial (UC3) |
| POST | `/api/pipeline/review/` | REC (assigned), ADM | `{requirement, candidate, decision, rejection_reason?, comments?}`; decision ∈ `SHORTLISTED, NOT_SUITABLE`. Sets the application stage. Response `{decision, candidate_status, mapping}` (UC3) |
| GET | `/api/pipeline/mappings/?requirement=<id>&status=<code>` | REC (assigned), ADM | load pipeline rows by stage |
| GET | `/api/pipeline/mappings/<id>/timeline/` | REC (assigned), ADM | recruitment timeline for ONE application (this requirement only): `{mapping, timeline[]}` (interactions + JD emails, chronological) |
| POST | `/api/pipeline/jd-preview/` | REC (assigned), ADM | `{requirement, mapping_ids[]}` → render the `JD_EMAIL` template per SHORTLISTED recipient **without sending**. Missing/inactive template → `400` (UC4) |
| POST | `/api/pipeline/send-jd/` | REC (assigned), ADM | `{requirement, mapping_ids[]}` → render + email SHORTLISTED candidates, log `communication_log`, advance to `JD_EMAIL_SENT` (via `SEND_JD`). Same render path as preview (UC4) |
| GET | `/api/pipeline/communications/?requirement=<id>` | REC (assigned), ADM | JD email tracker — every send attempt, newest first (`status`, `recipient`, `sent_by`, `sent_on`, `error_message`) |

### Stage × Outcome engine (centralized)
The single write-path for pipeline state. STAGE (where the candidate is) and OUTCOME (last recorded disposition) are independent; `pipeline.services` is the only place that mutates them.

| Method | Path | Role | Notes |
|--------|------|------|-------|
| POST | `/api/pipeline/outcome/` | REC (assigned), ADM | `{mapping, outcome, reason?, rejection_reason?, move_to_talent_pool?}` → record a stage outcome (advance or close). Returns the updated mapping. Invalid stage/outcome combo or already-closed → `400` |
| POST | `/api/pipeline/advance/` | REC (assigned), ADM | `{mapping, action, screening_datetime?, screening_mode?, reason?}`; action ∈ `SEND_JD` (Shortlisted→JD Email Sent), `SCHEDULE_SCREENING` (JD Email Sent→Screening Scheduled; needs a **future** datetime), `RELEASE_OFFER` (OK to Proceed→Offer Released). Illegal from the current stage → `400` |
| POST | `/api/pipeline/reschedule/` | REC (assigned), ADM | `{mapping, scheduled_at, screening_mode?}` → move a scheduled screening to a **future** time (stage unchanged). Only from Screening Scheduled → else `400` |
| POST | `/api/pipeline/transition/` | REC (assigned), ADM | **back-compat.** `{requirement, mapping_ids[], to_status, comments?, screening_datetime?, screening_mode?, rejection_reason?}` → maps each legacy `to_status` onto the engine (advance/outcome). Superseded by outcome/advance/reschedule |

**Advance actions** (`STAGE_ACTIONS`): `SEND_JD`: Shortlisted→JD Email Sent · `SCHEDULE_SCREENING`: JD Email Sent→Screening Scheduled · `RELEASE_OFFER`: OK to Proceed→Offer Released.
**Outcomes by stage** (`STAGE_OUTCOMES`): JD Email Sent → `DROPPED`(close) · Screening Scheduled → `PASSED`(→OK to Proceed), `REJECTED`/`NO_RESPONSE`/`DROPPED`/`FAKE`/`BLACKLISTED`(close) · OK to Proceed → `REJECTED`/`DROPPED`/`FAKE`(close) · Offer Released → `OFFER_ACCEPTED`(→Awaiting Joining), `OFFER_DECLINED`(close) · Awaiting Joining → `JOINED`(close, **consumes one Open seat → Filled**, refused when none free), `WITHDRAWN`(close). Closing outcomes drive the candidate's global status; non-hired closes (`NO_RESPONSE/DROPPED/NOT_SUITABLE/REJECTED/OFFER_DECLINED/WITHDRAWN`) honour `move_to_talent_pool`.

### Screening rounds
Multi-round screening history per application.

| Method | Path | Role | Notes |
|--------|------|------|-------|
| GET | `/api/pipeline/screenings/?mapping=<id>` | REC (assigned), ADM | chronological rounds for an application |
| POST | `/api/pipeline/screenings/` | REC (assigned), ADM | schedule a round: `{mapping, screening_mode, scheduled_at, interviewer, notes?}`. `interviewer` required (letters/spaces, Title-Cased). → `201` |
| POST | `/api/pipeline/screenings/<id>/complete/` | REC (assigned), ADM | `{outcome, notes?}`; outcome ∈ `PASSED, FAILED, NO_SHOW, CANCELLED, RESCHEDULE_REQUIRED` |
| POST | `/api/pipeline/screenings/<id>/reschedule/` | REC (assigned), ADM | `{scheduled_at}` (future datetime enforced) |

## Dashboard
| Method | Path | Role | Notes |
|--------|------|------|-------|
| GET | `/api/dashboard/` | any auth | **Role-aware** payload: `{role, kpis[], requirement_status[], pipeline_status[], recruiter_workload[], recent_requirements[], recent_candidates[], upcoming_screenings[]}` — scoped to the caller's role (ADM = all, HM = own requirements, REC = assigned reqs + own uploads). `recruiter_workload` (ADM only) = per-recruiter `{recruiter, requirements, candidates}`, idle recruiters omitted. |
