-- 0018_pipeline_stage_refactor.sql
-- Pipeline refactor: clean separation of stages vs. outcomes.
--   * "Offered" → display "Offer Released" (code kept OFFERED for compatibility).
--   * New stage AWAITING_JOINING + new outcome OFFER_DECLINED.
--   * "Schedule Screening" is no longer a stage (it's a recruiter action) —
--     migrate any application there to Screening Scheduled, then drop the status.
-- Additive/safe; candidate & audit history untouched.

SET search_path = ats, public;

UPDATE application_status_master SET status_name = 'Offer Released' WHERE status_code = 'OFFERED';

INSERT INTO application_status_master (status_code, status_name) VALUES
    ('AWAITING_JOINING', 'Awaiting Joining'),
    ('OFFER_DECLINED',   'Offer Declined')
ON CONFLICT (status_code) DO NOTHING;

DO $$
DECLARE
    sched_id     INT;
    scheduled_id INT;
BEGIN
    SELECT application_status_id INTO sched_id
      FROM application_status_master WHERE status_code = 'SCHEDULE_SCREENING';
    IF sched_id IS NOT NULL THEN
        SELECT application_status_id INTO scheduled_id
          FROM application_status_master WHERE status_code = 'SCREENING_SCHEDULED';
        -- Move applications off the retired stage, then remove it.
        UPDATE jd_cv_mapping SET application_stage_id = scheduled_id
         WHERE application_stage_id = sched_id;
        DELETE FROM application_status_master WHERE application_status_id = sched_id;
    END IF;
END $$;
