-- 0014_rename_application_stage.sql
-- Rename the per-application STAGE field on jd_cv_mapping from
-- application_status_id -> application_stage_id.
--
-- Rationale: this FK holds the application's pipeline STAGE (Shortlisted,
-- JD Email Sent, Screening Scheduled, OK to Proceed, Offered, Joined, ...).
-- "application_stage" names the concept correctly and disambiguates it from
--   * candidate_master.candidate_status  (the candidate's GLOBAL disposition), and
--   * jd_cv_mapping.cv_status             (the recruiter's resume-review VERDICT).
--
-- Pure column RENAME: no data is moved or lost, the FK to
-- application_status_master (the stage catalog, unchanged) is preserved.
-- Idempotent: only renames if the old column exists and the new one does not.

SET search_path = ats, public;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'ats' AND table_name = 'jd_cv_mapping'
          AND column_name = 'application_status_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'ats' AND table_name = 'jd_cv_mapping'
          AND column_name = 'application_stage_id'
    ) THEN
        ALTER TABLE jd_cv_mapping RENAME COLUMN application_status_id TO application_stage_id;
    END IF;
END $$;
