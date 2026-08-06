# Database Migrations

This project's database is **managed manually** (the Django models use `managed = False`),
so schema changes live here as **numbered, ordered SQL files** — the same idea as Flyway/Liquibase,
kept simple.

## Convention
- Files are applied **in filename order**: `0001_...`, `0002_...`, etc.
- Each file is **idempotent** where possible (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`,
  guarded `ALTER`s) so re-running it is safe.
- Never edit a migration that has already been applied in a shared environment — add a new one.

## How to apply

**Option A — via psql:**
```bash
psql -U postgres -d ats_db -f database/migrations/0001_phase1_pipeline.sql
```

**Option B — via the project helper (no psql needed):**
```bash
python backend/manage.py migrate_sql 0001_phase1_pipeline.sql
```
(The `migrate_sql` management command is added in the foundation module.)

## History
| File | Purpose |
|------|---------|
| `0001_phase1_pipeline.sql` | Phase 1: pipeline tables (`jd_cv_mapping`, `candidate_skill`, `cv_document`, `candidate_interaction`, `communication_log`), requirement/candidate field additions, status alignment + `status_code` codes. |
| `0002_workflow_masters.sql` | Workflow masters: add `screening_mode_master` + `rejection_reason_master`, drop `interview_round_master`, add `jd_cv_mapping.screening_mode_id`/`rejection_reason_id`, rename cv_status "Not Relevant" → "Not Suitable". |
| `0003_email_template.sql` | JD email module: add `email_template_master` (admin-editable templates) + seed the `JD_EMAIL` template with `{placeholder}` tokens rendered per recipient at preview/send. |
| `0004_master_audit_columns.sql` | Add `updated_by`/`updated_on` to the 9 masters that only had `created_*` (req/cv status, priority, notice period, req type, work mode, source, screening mode, rejection reason) — enables full audit + optimistic locking on every master. |
| `0005_domain_master.sql` | Promote Skill "Domain" to controlled master data: new `domain_master`, `skill_master.domain_id` FK, backfill distinct free-text values + link, drop the legacy `skill_domain` column. Domains classify Skills only (Candidates/Requirements still reference Skills). |
| `0006_positions_and_status_split.sql` | Recruitment redesign (additive): new `candidate_status_master`, `application_status_master`, `position_status_master` (seeded) + `requirement_position` (one row per seat) + nullable `candidate_master.candidate_status_id` / `jd_cv_mapping.application_status_id`. Nothing dropped. See `docs/POSITION_REDESIGN.md`. |
| `0007_backfill_positions_and_status.sql` | Recruitment redesign (data): backfill the new status FKs from the legacy `cv_status` (candidate disposition subset + application/pipeline subset; mapping `FAKE`→`NOT_SUITABLE`) and generate `requirement_position` rows per requirement (`positions_open` seats, first `positions_filled` Filled). |
| `0008_drop_legacy_cv_status.sql` | Recruitment redesign (cleanup): drop `candidate_master.cv_status_id` + `jd_cv_mapping.cv_status_id` and the mixed `cv_status_master`. Candidate disposition + application/pipeline status are now the single source of truth. Run only after the code cutover (not reversible). |
| `0009_widen_code_columns.sql` | Widen every auto-generated master **Code** column to `VARCHAR(50)` (they now hold UPPER_SNAKE identifiers derived from the name, e.g. `WORK_FROM_HOME`), and re-seed the `SCHEDULE_SCREENING` application status. |
| `0010_widen_client_code.sql` | Widen `client_master.client_code` to `VARCHAR(50)` — Client Code now follows the same auto-generate-from-name lifecycle (e.g. `TATA_CONSULTANCY_SERVICES`, editable once before first save, then frozen). |
| `0011_activity_log.sql` | Add `activity_log` (cross-entity audit feed powering the Admin activity panel) + `jd_cv_mapping.joined_date` (real join date for accurate Joined-This-Month / time-to-fill). Backfills `joined_date` for existing JOINED rows and seeds the feed from existing requirement/candidate history. |
| `0012_screening.sql` | Add `screening` (one row per screening round of an application) for the sequential screening workflow: type (FK `screening_mode_master`, extensible), status (Scheduled/Completed), outcome (Passed/Failed/No Show/Cancelled/Reschedule Required), scheduled_at, interviewer, notes, audit. Legacy inline `jd_cv_mapping.screening_mode/screening_datetime` left intact. |
| `0013_application_cv_status.sql` | Add `jd_cv_mapping.cv_status` — the recruiter's resume-review verdict (Shortlisted / Not Suitable), separate from `application_stage` (the pipeline stage). Backfills existing applications (Not-Suitable stage → verdict; all others were shortlisted to enter the pipeline). |
| `0014_rename_application_stage.sql` | Rename the per-application STAGE column `jd_cv_mapping.application_status_id → application_stage_id` (pure column rename, no data loss). Names the concept correctly and disambiguates it from `candidate_master.candidate_status` (global) and `jd_cv_mapping.cv_status` (review verdict). The `application_status_master` stage catalog it points to is unchanged. |
| `0018_pipeline_stage_refactor.sql` | Pipeline stages-vs-outcomes refactor: rename `OFFERED` display → "Offer Released" (code unchanged); add `AWAITING_JOINING` (stage) + `OFFER_DECLINED` (outcome); migrate any `SCHEDULE_SCREENING` application → `SCREENING_SCHEDULED` and **drop** `SCHEDULE_SCREENING` (screening is now a recruiter action, not a status). Additive/safe; history untouched. |
| `0017_candidate_lifecycle.sql` | Candidate lifecycle automation: add system statuses `REJECT_HOLD` + `JOINED` to `candidate_status_master`, and working fields on `candidate_master` (`active_rejection_count`, `reject_hold_start`, `reject_hold_until`, `joined_date`, `last_status_changed_on`). Drives Reject-Hold (2 rejections → 6-month cool-off) and Joined (2-year) restoration via the daily `run_candidate_lifecycle` command. Additive; history untouched. |
| `0016_candidate_duplicate_review.sql` | Add `candidate_duplicate_review` — the Duplicate Review workflow (separate from candidate status). Stores the submitted new-candidate details, the `existing_cv_id` it clashed with, detection reason, `review_status` (Pending/Resolved), `resolution` (Merged/Kept-Separate/Corrected), notes, `submitted_payload` JSONB, and full audit (created/resolved by+on). Entry point for future merge. |
| `0022_fake_outcome.sql` | Adds the `FAKE` application OUTCOME row (data-only) — Fake is now a first-class stage outcome recorded on `jd_cv_mapping.latest_outcome`. |
| `0021_application_stage_outcome.sql` | Separate pipeline STAGES from stage OUTCOMES: `application_status_master.kind`/`sort_order` + new outcomes (Blacklisted/Offer Accepted/Passed); `jd_cv_mapping.latest_outcome_id`/`is_closed`/`closed_on`/`closed_by`; backfills closed applications to (prior stage + outcome). |
| `0020_position_workflow.sql` | Requirement/Position two-workflow model: adds the system-managed `INACTIVE` position status, `requirement_position.status_source` (MANUAL / AUTO_REQ_HOLD / AUTO_REQ_CANCEL), and a unified `status_change_history` audit table (requirements + positions). Additive; drives the Hold/Cancel→Inactive cascade + selective auto-reopen. |
| `0015_consolidate_cv_status_into_stage.sql` | Consolidate the status model: make `application_stage` the single source of truth and **drop** `jd_cv_mapping.cv_status` (the redundant review verdict from `0013`). First promotes review "Not Suitable" outcomes (old: stage `REJECTED` + `cv_status=NOT_SUITABLE`) to the dedicated `NOT_SUITABLE` stage; Shortlisted verdicts are left untouched to avoid regressing candidates who progressed. Idempotent (guarded on the column existing). |
| `0019_candidate_profile_verification.sql` | Verify-&-Update workflow: add `candidate_profile_audit` (records each field change to the master candidate profile) + `candidate_master` fields `profile_verified`/`profile_verified_by`/`profile_verified_on` and extra profile columns (`current_designation`, `relevant_exp`, `certifications`, `additional_notes`). |
| `0023_deactivate_telephonic_screening.sql` | Data-only: deactivate the legacy "Telephonic" screening mode in `screening_mode_master` (kept for history, hidden from new scheduling). |
| `0024_candidate_import_fields.sql` | Bulk-import fields on `candidate_master`: `date_of_birth`, `age_at_import`, `postal_address`, and `current_location_text` (imported location kept as text until reconciled to Location Master). |
| `0025_bulk_import_batch.sql` | Add `bulk_import_batch` (one row per upload: file hash, header row, counts, status DRAFT/PENDING/COMPLETED/FAILED/ROLLED_BACK, audit) + `candidate_master.import_batch_id` FK — powers import history, draft→confirm, and rollback. |
| `0026_requirement_closure_outcomes.sql` | Data-only: add the `REQ_CLOSE_FILLED`, `REQ_CLOSE_LOST`, `REQ_POSITIONS_WITHDRAWN` application OUTCOME rows used when a requirement closes and its remaining candidates are freed to the Talent Pool. |
| `0027_requirement_recruitment_ended.sql` | Add `requirement_tracker.recruitment_ended` (+ `recruitment_ended_on`/`recruitment_ended_by`) — the permanent "End Recruitment" decision on an expired, partially-filled requirement (status stays Partial Filled; remaining seats go Inactive). |
| `0028_candidate_requirement_review.sql` | Add `candidate_requirement_review` — the explicit **pre-pipeline Review Pool** tag (candidate "under review" for a requirement), separate from `jd_cv_mapping` (which still means "entered the pipeline via Shortlist"). `status` default `ACTIVE`, UNIQUE `(cv_id, req_id)`, resolution + tagged/resolved audit. |
| `0029_fix_requirement_req_date.sql` | Data-only: reset a future/misplaced `requirement_tracker.req_date` (from an old form bug) to the true creation date and recover any lost deadline into `target_fill_date`. No DDL. |
| `0030_backfill_mapping_screening.sql` | Data-only: backfill `jd_cv_mapping.screening_datetime`/`screening_mode` from each application's latest `SCHEDULED` screening round so the board shows the mode/time. No DDL. |
