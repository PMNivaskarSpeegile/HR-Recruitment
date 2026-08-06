-- ============================================================================
-- Migration 0009 — Widen master Code columns for auto-generated identifiers
-- ----------------------------------------------------------------------------
-- Code is now auto-generated from the display name as an UPPER_SNAKE identifier
-- (e.g. "Work From Home" -> "WORK_FROM_HOME"). Several code columns were sized
-- for short abbreviations (VARCHAR(10)/(20)) and can't hold a generated code, so
-- widen every auto-generated code column to VARCHAR(50). Also re-seed the
-- SCHEDULE_SCREENING application status if it's missing.
-- Idempotent.
-- ============================================================================

SET search_path = ats, public;

ALTER TABLE req_status_master        ALTER COLUMN status_code      TYPE VARCHAR(50);
ALTER TABLE candidate_status_master  ALTER COLUMN status_code      TYPE VARCHAR(50);
ALTER TABLE application_status_master ALTER COLUMN status_code     TYPE VARCHAR(50);
ALTER TABLE position_status_master   ALTER COLUMN status_code      TYPE VARCHAR(50);
ALTER TABLE work_mode_master         ALTER COLUMN work_mode_code   TYPE VARCHAR(50);
ALTER TABLE screening_mode_master    ALTER COLUMN mode_code        TYPE VARCHAR(50);
ALTER TABLE rejection_reason_master  ALTER COLUMN reason_code      TYPE VARCHAR(50);
ALTER TABLE req_type_master          ALTER COLUMN req_type_code    TYPE VARCHAR(50);

INSERT INTO application_status_master (status_code, status_name, is_active) VALUES
    ('SCHEDULE_SCREENING', 'Schedule Screening', TRUE)
ON CONFLICT (status_code) DO NOTHING;

-- ============================================================================
-- End of migration 0009
-- ============================================================================
