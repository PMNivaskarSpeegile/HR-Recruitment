-- ============================================================================
-- Migration 0002 — Workflow masters aligned to our recruitment scope
-- ----------------------------------------------------------------------------
-- Scope ends at "OK to Proceed" (handoff to client). No offers/joining.
--   * Adds rejection_reason_master (structured reasons for negative outcomes)
--   * Replaces the misnamed interview_round_master with screening_mode_master
--     (our process = Telephonic / Video screening only)
--   * Adds nullable FKs on jd_cv_mapping: rejection_reason_id, screening_mode_id
--   * Aligns cv_status display "Not Relevant" -> "Not Suitable"
-- Idempotent where possible. interview_round_master is intentionally dropped.
-- ============================================================================

SET search_path = ats, public;

-- 1. screening_mode_master ---------------------------------------------------
CREATE TABLE IF NOT EXISTS screening_mode_master (
    screening_mode_id SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode_name   VARCHAR(40) NOT NULL UNIQUE,
    mode_code   VARCHAR(20) UNIQUE,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_by  INTEGER REFERENCES user_master(user_id),
    created_on  TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO screening_mode_master (mode_name, mode_code, description) VALUES
    ('Telephonic', 'TELEPHONIC', 'Screening conducted over a phone call'),
    ('Video',      'VIDEO',      'Screening conducted over a video call')
ON CONFLICT (mode_name) DO NOTHING;

-- 2. rejection_reason_master -------------------------------------------------
CREATE TABLE IF NOT EXISTS rejection_reason_master (
    reason_id   SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reason_name VARCHAR(80) NOT NULL UNIQUE,
    reason_code VARCHAR(30) UNIQUE,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_by  INTEGER REFERENCES user_master(user_id),
    created_on  TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO rejection_reason_master (reason_name, reason_code) VALUES
    ('Skills mismatch',            'SKILLS_MISMATCH'),
    ('Insufficient experience',    'LOW_EXPERIENCE'),
    ('CTC expectations too high',  'CTC_EXPECTATION'),
    ('Location / relocation',      'LOCATION'),
    ('Notice period too long',     'NOTICE_PERIOD'),
    ('Not interested',             'NOT_INTERESTED'),
    ('Unreachable',                'UNREACHABLE'),
    ('Failed screening',           'FAILED_SCREENING'),
    ('Duplicate / fake profile',   'DUPLICATE_FAKE'),
    ('Position closed',            'POSITION_CLOSED')
ON CONFLICT (reason_name) DO NOTHING;

-- 3. jd_cv_mapping foreign keys ---------------------------------------------
ALTER TABLE jd_cv_mapping ADD COLUMN IF NOT EXISTS rejection_reason_id SMALLINT;
ALTER TABLE jd_cv_mapping ADD COLUMN IF NOT EXISTS screening_mode_id   SMALLINT;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_jdcv_rejection_reason') THEN
    ALTER TABLE jd_cv_mapping ADD CONSTRAINT fk_jdcv_rejection_reason
      FOREIGN KEY (rejection_reason_id) REFERENCES rejection_reason_master(reason_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_jdcv_screening_mode') THEN
    ALTER TABLE jd_cv_mapping ADD CONSTRAINT fk_jdcv_screening_mode
      FOREIGN KEY (screening_mode_id) REFERENCES screening_mode_master(screening_mode_id);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_jdcv_reason ON jd_cv_mapping(rejection_reason_id);

-- 4. cv_status display alignment --------------------------------------------
UPDATE cv_status_master
   SET status_name = 'Not Suitable'
 WHERE status_code = 'NOT_SUITABLE' AND status_name = 'Not Relevant';

-- 5. Drop the misnamed interview_round_master -------------------------------
-- Safe: no transactional table references it (screening is captured on
-- jd_cv_mapping via screening_mode_id + screening_datetime now).
DROP TABLE IF EXISTS interview_round_master;

-- ============================================================================
-- End of migration 0002
-- ============================================================================
