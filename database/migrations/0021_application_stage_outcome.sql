-- 0021_application_stage_outcome.sql
-- Separate pipeline STAGES from stage OUTCOMES on the application (jd_cv_mapping).
--   * application_status_master gains `kind` (STAGE | OUTCOME) + `sort_order`.
--   * jd_cv_mapping gains latest_outcome_id / is_closed / closed_on / closed_by.
-- application_stage_id now holds a STAGE only; the recorded disposition lives in
-- latest_outcome_id. Additive & idempotent; existing rows are re-classified and
-- closed applications (whose stage column currently holds an outcome) are
-- backfilled to (best-effort prior stage + latest_outcome + is_closed).

SET search_path = ats, public;

-- 1. Classify the application-status master --------------------------------
ALTER TABLE application_status_master ADD COLUMN IF NOT EXISTS kind       VARCHAR(10);
ALTER TABLE application_status_master ADD COLUMN IF NOT EXISTS sort_order SMALLINT;

UPDATE application_status_master SET kind = 'STAGE', sort_order = CASE status_code
        WHEN 'NEW' THEN 0
        WHEN 'SHORTLISTED' THEN 10
        WHEN 'JD_EMAIL_SENT' THEN 20
        WHEN 'SCREENING_SCHEDULED' THEN 30
        WHEN 'OK_TO_PROCEED' THEN 40
        WHEN 'OFFERED' THEN 50
        WHEN 'AWAITING_JOINING' THEN 60 END
 WHERE status_code IN ('NEW','SHORTLISTED','JD_EMAIL_SENT','SCREENING_SCHEDULED',
                       'OK_TO_PROCEED','OFFERED','AWAITING_JOINING');

UPDATE application_status_master SET kind = 'OUTCOME'
 WHERE status_code IN ('NO_RESPONSE','DROPPED','NOT_SUITABLE','REJECTED',
                       'OFFER_DECLINED','WITHDRAWN','JOINED','FAKE','SCHEDULE_SCREENING');

-- New outcomes: Blacklisted (close), Offer Accepted (advance→Awaiting Joining),
-- Passed (advance→OK to Proceed).
INSERT INTO application_status_master (status_code, status_name, kind, is_active) VALUES
    ('BLACKLISTED',    'Blacklisted',    'OUTCOME', TRUE),
    ('OFFER_ACCEPTED', 'Offer Accepted', 'OUTCOME', TRUE),
    ('PASSED',         'OK to Proceed',  'OUTCOME', TRUE)
ON CONFLICT (status_code) DO UPDATE SET kind = EXCLUDED.kind, status_name = EXCLUDED.status_name;

-- 2. Application stage/outcome split on jd_cv_mapping ----------------------
ALTER TABLE jd_cv_mapping ADD COLUMN IF NOT EXISTS latest_outcome_id SMALLINT REFERENCES application_status_master(application_status_id);
ALTER TABLE jd_cv_mapping ADD COLUMN IF NOT EXISTS is_closed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE jd_cv_mapping ADD COLUMN IF NOT EXISTS closed_on TIMESTAMP;
ALTER TABLE jd_cv_mapping ADD COLUMN IF NOT EXISTS closed_by INTEGER REFERENCES user_master(user_id);

-- 3. Backfill: applications whose "stage" is actually an OUTCOME (closed) ---
DO $$
DECLARE r RECORD; prior TEXT; stg_id INT;
BEGIN
  FOR r IN
    SELECT m.mapping_id, m.application_stage_id, m.updated_on, m.created_on, s.status_code
      FROM jd_cv_mapping m
      JOIN application_status_master s ON s.application_status_id = m.application_stage_id
     WHERE s.kind = 'OUTCOME'
  LOOP
    prior := CASE r.status_code
        WHEN 'NOT_SUITABLE'   THEN 'SHORTLISTED'
        WHEN 'NO_RESPONSE'    THEN 'JD_EMAIL_SENT'
        WHEN 'DROPPED'        THEN 'JD_EMAIL_SENT'
        WHEN 'REJECTED'       THEN 'SCREENING_SCHEDULED'
        WHEN 'FAKE'           THEN 'SCREENING_SCHEDULED'
        WHEN 'OFFER_DECLINED' THEN 'OFFERED'
        WHEN 'WITHDRAWN'      THEN 'AWAITING_JOINING'
        WHEN 'JOINED'         THEN 'AWAITING_JOINING'
        ELSE 'SHORTLISTED' END;
    SELECT application_status_id INTO stg_id FROM application_status_master WHERE status_code = prior;
    UPDATE jd_cv_mapping
       SET latest_outcome_id   = r.application_stage_id,
           application_stage_id = stg_id,
           is_closed            = TRUE,
           closed_on            = COALESCE(r.updated_on, r.created_on)
     WHERE mapping_id = r.mapping_id;
  END LOOP;
END $$;
