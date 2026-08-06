-- ============================================================================
-- Migration 0013 — Separate CV (resume-review) status from application stage
-- ----------------------------------------------------------------------------
-- The recruiter's initial resume-review verdict (Shortlisted / Not Suitable) is
-- a distinct concept from the application's pipeline stage. It's a per-
-- requirement judgement, so it lives on the application (jd_cv_mapping) as its
-- own column, separate from application_status (the stage).
--
--   jd_cv_mapping.cv_status  — SHORTLISTED | NOT_SUITABLE (nullable; set at review)
--
-- Backfills existing applications: a Not-Suitable stage → NOT_SUITABLE verdict;
-- every other existing application had to be shortlisted to enter the pipeline.
-- Idempotent.
-- ============================================================================

SET search_path = ats, public;

ALTER TABLE jd_cv_mapping ADD COLUMN IF NOT EXISTS cv_status VARCHAR(30);

UPDATE jd_cv_mapping m
SET cv_status = 'NOT_SUITABLE'
FROM application_status_master a
WHERE m.application_status_id = a.application_status_id
  AND a.status_code = 'NOT_SUITABLE'
  AND m.cv_status IS NULL;

UPDATE jd_cv_mapping
SET cv_status = 'SHORTLISTED'
WHERE cv_status IS NULL;

-- ============================================================================
-- End of migration 0013
-- ============================================================================
