-- ============================================================================
-- Migration 0012 — Screening rounds (sequential screening workflow)
-- ----------------------------------------------------------------------------
-- Replaces the single inline screening (jd_cv_mapping.screening_mode /
-- screening_datetime) with a dedicated `screening` table: one row per screening
-- round of an application, so recruiters can run Telephonic → Video → … in
-- sequence, each with its own status, outcome, interviewer and notes.
--
-- Screening TYPE reuses screening_mode_master (extensible — a new mode row = a
-- new screening type, no code change). Status/outcome are fixed workflow enums.
-- The legacy inline columns are LEFT IN PLACE to avoid breaking existing APIs.
-- Idempotent.
-- ============================================================================

SET search_path = ats, public;

CREATE TABLE IF NOT EXISTS screening (
    screening_id      BIGSERIAL PRIMARY KEY,
    mapping_id        INTEGER NOT NULL REFERENCES jd_cv_mapping(mapping_id),
    screening_mode_id SMALLINT NOT NULL REFERENCES screening_mode_master(screening_mode_id),
    status            VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED',  -- SCHEDULED | COMPLETED
    outcome           VARCHAR(30),   -- PASSED|FAILED|NO_SHOW|CANCELLED|RESCHEDULE_REQUIRED (set on completion)
    scheduled_at      TIMESTAMP(0),
    interviewer       VARCHAR(150),
    notes             TEXT,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_by        INTEGER REFERENCES user_master(user_id),
    created_on        TIMESTAMP(0),
    updated_by        INTEGER REFERENCES user_master(user_id),
    updated_on        TIMESTAMP(0)
);
CREATE INDEX IF NOT EXISTS idx_screening_mapping ON screening(mapping_id);

-- ============================================================================
-- End of migration 0012
-- ============================================================================
