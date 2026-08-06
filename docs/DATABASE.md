# Database

- **Engine:** PostgreSQL · **Schema:** `ats` · **Access:** Django ORM with `managed = False` (Django never creates/alters these tables).
- **Source of truth:** `database/ats db schema.sql` — a `pg_dump --schema-only` of the live DB, reflecting the base schema plus every migration applied. The Django models in `backend/admin_module/models.py` mirror this schema.
- **Migrations:** versioned SQL in `database/migrations/` (`0001`–`0030`), applied in filename order via `python backend/manage.py migrate_sql <file>` (idempotent / additive). See `database/migrations/README.md` for the full per-file history — regenerate the schema dump after adding one.

## Tables (schema `ats`)

### Master / reference
| Table | Purpose |
|-------|---------|
| `role_master` | User roles (ADM / REC / HM) |
| `user_master` | Application users + auth (`username`, `password_hash`) |
| `client_master` | Client companies (`client_code` unique, auto-generated) |
| `client_manager_master` | Client-side contacts (unique per `client_id`+`email`) |
| `skill_master` | Skills; `domain_id` FK → `domain_master` (0005) |
| `domain_master` | Controlled skill domains, promoted from free text (0005) |
| `location_master` | City/state/country (unique triple) |
| `source_master` | Candidate sourcing channels |
| `notice_period_master` | Notice-period buckets |
| `work_mode_master` | On-site / Hybrid / WFH |
| `req_type_master` | Requirement types |
| `priority_master` | Requirement priorities |
| `req_status_master` | Requirement lifecycle statuses (`status_code`) |
| `candidate_status_master` | Global candidate disposition (0006) |
| `application_status_master` | Per-application pipeline STAGE / OUTCOME (0006; `kind`+`sort_order` in 0021) |
| `position_status_master` | Per-seat lifecycle (0006) |
| `screening_mode_master` | Screening modes (Telephonic, Video) |
| `rejection_reason_master` | Standard rejection reasons |
| `email_template_master` | Admin-editable email templates (0003) |

*Dropped along the way: `interview_round_master` (0002 — single-recruiter screening), `cv_status_master` (0008 — split into `candidate_status_master` + `application_status_master`).*

### Transactional / operational
| Table | Purpose |
|-------|---------|
| `requirement_tracker` | Job requisitions |
| `requirement_position` | One row per hire-able seat in a requirement (0006) |
| `candidate_master` | Candidate CV database |
| `jd_cv_mapping` | Candidate × requirement application/pipeline (unique on `(req_id, cv_id)`) |
| `candidate_skill` | Candidate ↔ skill tags (unique `(cv_id, skill_id)`) |
| `cv_document` | Résumé file metadata (files on disk) |
| `candidate_interaction` | Recruiter notes / status-change audit |
| `communication_log` | JD emails / outbound communications |
| `screening` | One row per screening round of an application (0012) |
| `candidate_requirement_review` | Pre-pipeline "Review Pool" — candidate under review for a requirement, before Shortlist (0028; unique `(cv_id, req_id)`, `status` default `ACTIVE`) |
| `candidate_duplicate_review` | Duplicate-review workflow: submitted payload + clashing `existing_cv_id` (0016) |

### Audit / logging
| Table | Purpose |
|-------|---------|
| `activity_log` | Cross-entity activity feed for the Admin panel (0011) |
| `candidate_profile_audit` | Field-level change log on candidate profiles (0019) |
| `status_change_history` | Unified requirement + position status-change audit (0020) |

### Import
| Table | Purpose |
|-------|---------|
| `bulk_import_batch` | Bulk-upload batch tracking + per-row report (`row_report` JSONB) (0025) |

## Status codes

Referenced in code via `backend/core/constants.py`. `*_master.status_code` columns hold UPPER_SNAKE identifiers (widened to `VARCHAR(50)` in 0009).

### Requirement (`req_status_master.status_code`)
`NEW`, `ASSIGNED`, `OPEN`, `HOLD`, `CANCELLED`, `PARTIAL_FILLED`, `CLOSE_FILLED` (displayed "Filled"), `CLOSE_LOST` (terminal).
*There is no stored `EXPIRED` status — "Expired" is a derived, read-only overlay (target fill date passed while non-terminal).*

### Candidate disposition (`candidate_status_master.status_code`)
Global, one per candidate. `NEW_CV`, `SAVED` (displayed "Talent Pool"), `POSSIBLE_DUPLICATE`, `FAKE`, `BLACKLISTED`, plus system-managed lifecycle statuses `REJECT_HOLD` + `JOINED` (0017).

### Application (`application_status_master`, classified by `kind`)
Split from the retired `cv_status_master`. `kind` is `STAGE` (position in the flow) or `OUTCOME` (a recorded disposition); `sort_order` orders the stages (0021).

**STAGES** (pipeline progression, in order):
`SHORTLISTED` → `JD_EMAIL_SENT` → `SCREENING_SCHEDULED` → `OK_TO_PROCEED` → `OFFERED` (displayed "Offer Released") → `AWAITING_JOINING`. (`NEW` also exists as the initial stage.)

**OUTCOMES:** `PASSED`, `OFFER_ACCEPTED`, `NO_RESPONSE`, `DROPPED`, `NOT_SUITABLE`, `REJECTED`, `OFFER_DECLINED`, `WITHDRAWN`, `JOINED`, `FAKE` (0022), `BLACKLISTED`, and the system-generated requirement-closure outcomes `REQ_CLOSE_FILLED`, `REQ_CLOSE_LOST`, `REQ_POSITIONS_WITHDRAWN` (0026).

*`SCHEDULE_SCREENING` was retired in 0018 — screening is now a recruiter action, not a status. Display "Offered" → "Offer Released" (code unchanged).*

### Position (`position_status_master.status_code`)
`OPEN`, `IN_PROGRESS` (legacy), `FILLED`, `CANCELLED`, `HOLD`, plus system-managed `INACTIVE` (0020, set by the requirement Hold/Cancel cascade).

## `jd_cv_mapping` status columns

The legacy `cv_status_id` was dropped (0008). Application status is now modelled with:

| Column | Meaning |
|--------|---------|
| `application_stage_id` | Current STAGE (FK → `application_status_master`). Renamed from `application_status_id` in 0014. |
| `latest_outcome_id` | Most recent OUTCOME, if any (FK → `application_status_master`) (0021) |
| `is_closed` | Whether the application is closed (0021) |
| `closed_on` / `closed_by` | When/who closed it (0021) |
| `joined_date` | Real join date, for time-to-fill metrics (0011) |
| `screening_mode_id` / `screening_datetime` | Legacy inline screening fields (kept; the `screening` table is authoritative) |
| `rejection_reason_id` | FK → `rejection_reason_master` |

## Notable columns added after the base schema

- **`candidate_master`** — lifecycle: `active_rejection_count`, `reject_hold_start`, `reject_hold_until`, `joined_date`, `last_status_changed_on` (0017); profile verification: `profile_verified`, `profile_verified_by`, `profile_verified_on` (0019); import: `date_of_birth`, `age_at_import`, `postal_address`, `current_location_text` (0024), `import_batch_id` → `bulk_import_batch` (0025). (`candidate_status_id` FK added 0006.)
- **`requirement_tracker`** — `recruitment_ended`, `recruitment_ended_on`, `recruitment_ended_by` (0027) for the End-Recruitment workflow on expired, partially-filled requirements.
- **`requirement_position`** — `status_source` (MANUAL / AUTO_REQ_HOLD / AUTO_REQ_CANCEL / AUTO_END_RECRUITMENT), drives selective auto-reopen (0020).
- **`skill_master`** — `domain_id` FK → `domain_master` (0005).

## Key conventions

- Every table carries audit columns (`created_by/on`; most masters and transactional tables also have `updated_by/on`).
- `mobile` (and `email`, `cv_serial`) is a unique identity key on `candidate_master`; duplicate logic keys on `mobile`.
- Base-schema timestamps are `TIMESTAMP(0)` **without** time zone; newer tables/columns (0016+ audit/import tables and lifecycle fields) use a bare `TIMESTAMP`. Django runs `USE_TZ = False` to match. Migrate to `timestamptz` + `USE_TZ = True` only if multi-timezone support is ever needed.

## Migration history

The full `0001`–`0030` per-file changelog lives in `database/migrations/README.md`. Highlights: 0005 domain master; 0006–0008 positions + candidate/application status split (retiring `cv_status_master`); 0011 activity log; 0012 screening; 0014 stage rename; 0016 duplicate review; 0017 candidate lifecycle; 0018/0021/0022/0026 stage-vs-outcome model + closure outcomes; 0019 profile verification; 0020 position workflow; 0024/0025 bulk import; 0027 end-recruitment; 0028 review pool. **0029/0030 are data-only** (a `req_date` fix and a screening backfill — no DDL).
</content>
</invoke>
