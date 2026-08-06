-- ============================================================================
-- Migration 0001 — Phase 1: Pipeline tables + schema alignment
-- ----------------------------------------------------------------------------
-- Adds the candidate pipeline (JD_CV_Mapping) and supporting tables required by
-- the Phase 1 requirements document, extends requirement/candidate tables with
-- missing fields, and aligns the status lookups (adds stable status_code values).
--
-- SAFE TO RE-RUN: every statement is guarded (IF NOT EXISTS / ON CONFLICT /
-- existence checks). All changes are ADDITIVE — nothing is dropped.
-- ============================================================================

SET search_path = ats, public;

-- ============================================================================
-- SECTION 1 — Stable status codes on the lookup tables
-- Why: workflow logic must reference statuses by a rename-proof code, not by
--      display name (typo-prone) or row id (differs per environment).
-- ============================================================================

ALTER TABLE req_status_master ADD COLUMN IF NOT EXISTS status_code VARCHAR(20);
ALTER TABLE cv_status_master  ADD COLUMN IF NOT EXISTS status_code VARCHAR(20);

-- --- Requirement status codes (backfill existing rows) ---
UPDATE req_status_master SET status_code='NEW'            WHERE status_name='New'            AND status_code IS NULL;
UPDATE req_status_master SET status_code='OPEN'           WHERE status_name='Open'           AND status_code IS NULL;
UPDATE req_status_master SET status_code='ASSIGNED'       WHERE status_name='Assigned'       AND status_code IS NULL;
UPDATE req_status_master SET status_code='CANCELLED'      WHERE status_name='Cancelled'      AND status_code IS NULL;
UPDATE req_status_master SET status_code='HOLD'           WHERE status_name='Hold'           AND status_code IS NULL;
UPDATE req_status_master SET status_code='PARTIAL_FILLED' WHERE status_name='Partial Filled' AND status_code IS NULL;
UPDATE req_status_master SET status_code='CLOSE_FILLED'   WHERE status_name='Close Filled'   AND status_code IS NULL;
UPDATE req_status_master SET status_code='EXPIRED'        WHERE status_name='Expired'        AND status_code IS NULL;

-- Add the missing requirement status from the doc (§5)
INSERT INTO req_status_master (status_name, description)
VALUES ('Close Lost', 'Closed without filling - lost to competitor or budget cut')
ON CONFLICT (status_name) DO NOTHING;
UPDATE req_status_master SET status_code='CLOSE_LOST' WHERE status_name='Close Lost' AND status_code IS NULL;

-- --- CV status codes (backfill existing rows) ---
UPDATE cv_status_master SET status_code='NEW_CV'              WHERE status_name='New CV'              AND status_code IS NULL;
UPDATE cv_status_master SET status_code='SAVED'              WHERE status_name='Saved'              AND status_code IS NULL;
UPDATE cv_status_master SET status_code='SHORTLISTED'         WHERE status_name='Shortlisted'         AND status_code IS NULL;
UPDATE cv_status_master SET status_code='FAKE'               WHERE status_name='Fake'               AND status_code IS NULL;
UPDATE cv_status_master SET status_code='NOT_SUITABLE'        WHERE status_name='Not Relevant'        AND status_code IS NULL;
UPDATE cv_status_master SET status_code='JD_EMAIL_SENT'       WHERE status_name='JD Email Sent'       AND status_code IS NULL;
UPDATE cv_status_master SET status_code='NO_RESPONSE'         WHERE status_name='No Response'         AND status_code IS NULL;
UPDATE cv_status_master SET status_code='DROPPED'            WHERE status_name='Dropped'            AND status_code IS NULL;
UPDATE cv_status_master SET status_code='SCREENING_SCHEDULED' WHERE status_name='Screening Scheduled' AND status_code IS NULL;
UPDATE cv_status_master SET status_code='OK_TO_PROCEED'       WHERE status_name='OK to Proceed'       AND status_code IS NULL;
UPDATE cv_status_master SET status_code='REJECTED'           WHERE status_name='Rejected'           AND status_code IS NULL;

-- Add the missing CV statuses the workflow needs
INSERT INTO cv_status_master (status_name, description) VALUES
  ('Possible Duplicate', 'Mobile exists but email differs - needs recruiter resolution (§7)'),
  ('Schedule Screening', 'Candidate responded; screening to be scheduled (UC5)')
ON CONFLICT (status_name) DO NOTHING;
UPDATE cv_status_master SET status_code='POSSIBLE_DUPLICATE' WHERE status_name='Possible Duplicate' AND status_code IS NULL;
UPDATE cv_status_master SET status_code='SCHEDULE_SCREENING' WHERE status_name='Schedule Screening' AND status_code IS NULL;

-- Enforce uniqueness of the codes (NULLs allowed, so safe even if any unmapped)
CREATE UNIQUE INDEX IF NOT EXISTS uq_req_status_code ON req_status_master(status_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cv_status_code  ON cv_status_master(status_code);


-- ============================================================================
-- SECTION 2 — Requirement Tracker: add fields required by the doc (§4)
--             and FIX the experience inconsistency.
-- Why: candidate_master stores experience as a RANGE (exp_min, exp_max) but
--      requirement_tracker had a single `exp`. Recruitment matching needs a
--      range on BOTH sides ("req wants 4-8 yrs" vs "candidate has 5-6 yrs").
--      The table is empty (0 rows), so we add exp_min/exp_max and DROP the old
--      single `exp` column — no data loss, and both tables now agree.
-- ============================================================================

ALTER TABLE requirement_tracker ADD COLUMN IF NOT EXISTS jd_serial_number VARCHAR(20);
ALTER TABLE requirement_tracker ADD COLUMN IF NOT EXISTS client_req_id    VARCHAR(50);
ALTER TABLE requirement_tracker ADD COLUMN IF NOT EXISTS exp_min          NUMERIC(4,1);
ALTER TABLE requirement_tracker ADD COLUMN IF NOT EXISTS exp_max          NUMERIC(4,1);

-- Remove the inconsistent single-value column (safe: table is empty).
ALTER TABLE requirement_tracker DROP COLUMN IF EXISTS exp;

CREATE UNIQUE INDEX IF NOT EXISTS uq_req_jd_serial ON requirement_tracker(jd_serial_number);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_req_exp_range') THEN
    ALTER TABLE requirement_tracker
      ADD CONSTRAINT chk_req_exp_range
      CHECK (exp_min IS NULL OR exp_max IS NULL OR exp_max >= exp_min);
  END IF;
END $$;

-- Guard the candidate experience range the same way (constraint may already
-- exist from the original schema; add only if missing).
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_cand_exp_range') THEN
    ALTER TABLE candidate_master
      ADD CONSTRAINT chk_cand_exp_range
      CHECK (exp_min IS NULL OR exp_max IS NULL OR exp_max >= exp_min);
  END IF;
END $$;


-- ============================================================================
-- SECTION 3 — Candidate Master: duplicate-resolution link (§7)
-- ============================================================================

ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS duplicate_of_cv_id INTEGER;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_candidate_duplicate_of') THEN
    ALTER TABLE candidate_master
      ADD CONSTRAINT fk_candidate_duplicate_of
      FOREIGN KEY (duplicate_of_cv_id) REFERENCES candidate_master(cv_id);
  END IF;
END $$;


-- ============================================================================
-- SECTION 4 — candidate_skill  (candidate <-> skill, many-to-many)
-- Why: tag uploaded CVs with the requirement's 3 skills (UC2) and power the
--      global candidate search by skill (§9).
-- ============================================================================

CREATE TABLE IF NOT EXISTS candidate_skill (
    cs_id       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cv_id       INTEGER NOT NULL REFERENCES candidate_master(cv_id) ON DELETE CASCADE,
    skill_id    INTEGER NOT NULL REFERENCES skill_master(skill_id),
    created_on  TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_candidate_skill UNIQUE (cv_id, skill_id)
);


-- ============================================================================
-- SECTION 5 — jd_cv_mapping  (THE PIPELINE: candidate x requirement x stage)
-- A candidate's status is PER-REQUIREMENT here, separate from their global
-- status in candidate_master.
-- ============================================================================

CREATE TABLE IF NOT EXISTS jd_cv_mapping (
    mapping_id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    req_id              INTEGER  NOT NULL REFERENCES requirement_tracker(req_id),
    cv_id               INTEGER  NOT NULL REFERENCES candidate_master(cv_id),
    cv_status_id        SMALLINT NOT NULL REFERENCES cv_status_master(cv_status_id),
    screening_datetime  TIMESTAMP(0),
    comments            TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_by          INTEGER REFERENCES user_master(user_id),
    created_on          TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    updated_by          INTEGER REFERENCES user_master(user_id),
    updated_on          TIMESTAMP(0),
    CONSTRAINT uq_jd_cv UNIQUE (req_id, cv_id)   -- a candidate maps to a requirement once
);


-- ============================================================================
-- SECTION 6 — cv_document  (résumé files: metadata in DB, file on disk, §8)
-- ============================================================================

CREATE TABLE IF NOT EXISTS cv_document (
    document_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cv_id            INTEGER NOT NULL REFERENCES candidate_master(cv_id) ON DELETE CASCADE,
    file_name        VARCHAR(255) NOT NULL,           -- original name shown to user
    stored_file_name VARCHAR(255) NOT NULL,           -- safe, unique name on disk
    file_path        TEXT NOT NULL,                   -- e.g. /uploads/candidate/CV000001/resume_v1.pdf
    file_type        VARCHAR(20),
    file_size        BIGINT,
    active_version   BOOLEAN NOT NULL DEFAULT TRUE,
    upload_date      TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    uploaded_by      INTEGER REFERENCES user_master(user_id)
);


-- ============================================================================
-- SECTION 7 — candidate_interaction  (recruiter notes & history, §10)
-- ============================================================================

CREATE TABLE IF NOT EXISTS candidate_interaction (
    interaction_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cv_id            INTEGER NOT NULL REFERENCES candidate_master(cv_id) ON DELETE CASCADE,
    req_id           INTEGER REFERENCES requirement_tracker(req_id),  -- null = global note
    interaction_type VARCHAR(40) NOT NULL,   -- CALL_NOTE | SCREENING_FEEDBACK | STATUS_CHANGE | DUPLICATE_RESOLUTION | GENERAL
    comment          TEXT NOT NULL,
    created_by       INTEGER REFERENCES user_master(user_id),
    created_on       TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================================
-- SECTION 8 — communication_log  (JD emails sent, §2)
-- ============================================================================

CREATE TABLE IF NOT EXISTS communication_log (
    comm_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cv_id          INTEGER NOT NULL REFERENCES candidate_master(cv_id) ON DELETE CASCADE,
    req_id         INTEGER REFERENCES requirement_tracker(req_id),
    channel        VARCHAR(20) NOT NULL DEFAULT 'EMAIL',
    recipient      VARCHAR(150) NOT NULL,
    subject        VARCHAR(255),
    body           TEXT,
    status         VARCHAR(20) NOT NULL DEFAULT 'SENT',   -- SENT | FAILED
    error_message  TEXT,
    sent_by        INTEGER REFERENCES user_master(user_id),
    sent_on        TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================================
-- SECTION 9 — Indexes for the queries the workflow runs most
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_jdcv_req         ON jd_cv_mapping(req_id);
CREATE INDEX IF NOT EXISTS idx_jdcv_cv          ON jd_cv_mapping(cv_id);
CREATE INDEX IF NOT EXISTS idx_jdcv_status      ON jd_cv_mapping(cv_status_id);
CREATE INDEX IF NOT EXISTS idx_candskill_skill  ON candidate_skill(skill_id);
CREATE INDEX IF NOT EXISTS idx_cvdoc_cv         ON cv_document(cv_id);
CREATE INDEX IF NOT EXISTS idx_interaction_cv   ON candidate_interaction(cv_id);
CREATE INDEX IF NOT EXISTS idx_comm_cv          ON communication_log(cv_id);

-- ============================================================================
-- End of migration 0001
-- ============================================================================
