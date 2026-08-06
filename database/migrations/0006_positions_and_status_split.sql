-- ============================================================================
-- Migration 0006 — Positions + Candidate/Application status split (ADDITIVE)
-- ----------------------------------------------------------------------------
-- Phase 1 of the recruitment-workflow redesign (see docs/POSITION_REDESIGN.md).
-- This migration ONLY ADDS structures — nothing is dropped and no existing
-- column is read differently yet, so the running app is unaffected and this is
-- fully reversible. Backfill happens in 0007; the legacy cv_status columns are
-- retired in 0008 after the code cutover.
--
-- Adds:
--   * candidate_status_master   — global candidate disposition
--   * application_status_master — per-(candidate,requirement) pipeline stage
--   * position_status_master    — per-seat lifecycle
--   * requirement_position      — one row per hire-able seat in a requirement
--   * candidate_master.candidate_status_id      (nullable FK, backfilled in 0007)
--   * jd_cv_mapping.application_status_id        (nullable FK, backfilled in 0007)
-- Idempotent (IF NOT EXISTS / ON CONFLICT DO NOTHING).
-- ============================================================================

SET search_path = ats, public;

-- 1. Candidate disposition master --------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_status_master (
    candidate_status_id SMALLSERIAL PRIMARY KEY,
    status_code VARCHAR(30) NOT NULL UNIQUE,
    status_name VARCHAR(60) NOT NULL,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_by  INTEGER REFERENCES user_master(user_id),
    created_on  TIMESTAMP(0),
    updated_by  INTEGER REFERENCES user_master(user_id),
    updated_on  TIMESTAMP(0)
);

INSERT INTO candidate_status_master (status_code, status_name) VALUES
    ('NEW_CV',             'New CV'),
    ('SAVED',              'Saved'),
    ('FAKE',               'Fake'),
    ('POSSIBLE_DUPLICATE', 'Possible Duplicate'),
    ('BLACKLISTED',        'Blacklisted')
ON CONFLICT (status_code) DO NOTHING;

-- 2. Application (pipeline) status master ------------------------------------
CREATE TABLE IF NOT EXISTS application_status_master (
    application_status_id SMALLSERIAL PRIMARY KEY,
    status_code VARCHAR(30) NOT NULL UNIQUE,
    status_name VARCHAR(60) NOT NULL,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_by  INTEGER REFERENCES user_master(user_id),
    created_on  TIMESTAMP(0),
    updated_by  INTEGER REFERENCES user_master(user_id),
    updated_on  TIMESTAMP(0)
);

INSERT INTO application_status_master (status_code, status_name) VALUES
    ('NEW',                 'New'),
    ('SHORTLISTED',         'Shortlisted'),
    ('JD_EMAIL_SENT',       'JD Email Sent'),
    ('NO_RESPONSE',         'No Response'),
    ('DROPPED',             'Dropped'),
    ('SCHEDULE_SCREENING',  'Schedule Screening'),
    ('SCREENING_SCHEDULED', 'Screening Scheduled'),
    ('NOT_SUITABLE',        'Not Suitable'),
    ('REJECTED',            'Rejected'),
    ('OK_TO_PROCEED',       'OK to Proceed'),
    ('OFFERED',             'Offered'),
    ('JOINED',              'Joined'),
    ('WITHDRAWN',           'Withdrawn')
ON CONFLICT (status_code) DO NOTHING;

-- 3. Position (seat) status master -------------------------------------------
CREATE TABLE IF NOT EXISTS position_status_master (
    position_status_id SMALLSERIAL PRIMARY KEY,
    status_code VARCHAR(30) NOT NULL UNIQUE,
    status_name VARCHAR(60) NOT NULL,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_by  INTEGER REFERENCES user_master(user_id),
    created_on  TIMESTAMP(0),
    updated_by  INTEGER REFERENCES user_master(user_id),
    updated_on  TIMESTAMP(0)
);

INSERT INTO position_status_master (status_code, status_name) VALUES
    ('OPEN',        'Open'),
    ('IN_PROGRESS', 'In Progress'),
    ('FILLED',      'Filled'),
    ('CANCELLED',   'Cancelled'),
    ('HOLD',        'Hold')
ON CONFLICT (status_code) DO NOTHING;

-- 4. Requirement positions (one row per seat) --------------------------------
CREATE TABLE IF NOT EXISTS requirement_position (
    position_id        SERIAL PRIMARY KEY,
    req_id             INTEGER NOT NULL REFERENCES requirement_tracker(req_id),
    position_no        INTEGER NOT NULL,
    position_status_id SMALLINT REFERENCES position_status_master(position_status_id),
    -- The winning application that filled this seat (set on Join); via it we
    -- reach the candidate + requirement, so no direct candidate FK is needed.
    filled_by_mapping_id INTEGER REFERENCES jd_cv_mapping(mapping_id),
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_by         INTEGER REFERENCES user_master(user_id),
    created_on         TIMESTAMP(0),
    updated_by         INTEGER REFERENCES user_master(user_id),
    updated_on         TIMESTAMP(0),
    UNIQUE (req_id, position_no)
);
CREATE INDEX IF NOT EXISTS idx_requirement_position_req ON requirement_position(req_id);

-- 5. New nullable status FKs (backfilled in 0007; old columns kept until 0008) -
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS candidate_status_id SMALLINT REFERENCES candidate_status_master(candidate_status_id);
ALTER TABLE jd_cv_mapping    ADD COLUMN IF NOT EXISTS application_status_id SMALLINT REFERENCES application_status_master(application_status_id);

-- ============================================================================
-- End of migration 0006
-- ============================================================================
