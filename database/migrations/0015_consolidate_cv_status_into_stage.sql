-- 0015_consolidate_cv_status_into_stage.sql
-- Consolidate the status model: application_stage becomes the SINGLE source of
-- truth for a candidate's per-requirement progress. The redundant review-verdict
-- column jd_cv_mapping.cv_status (added in 0013) is removed.
--
-- Data preservation: the only verdict information not already reflected in the
-- stage is the "Not Suitable" review outcome. Under the old model a Not-Suitable
-- review set application_stage = REJECTED while cv_status = NOT_SUITABLE. We now
-- promote those to the dedicated NOT_SUITABLE stage so the disposition is not
-- lost. Shortlisted verdicts need no action — their stage is already SHORTLISTED
-- or has legitimately progressed beyond it, so we must NOT rewrite them (that
-- would regress candidates already in the pipeline).
--
-- Idempotent: guarded on the column still existing; DROP is unconditional-safe.

SET search_path = ats, public;

DO $$
DECLARE
    not_suitable_id INT;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'ats' AND table_name = 'jd_cv_mapping'
          AND column_name = 'cv_status'
    ) THEN
        SELECT application_status_id INTO not_suitable_id
          FROM application_status_master WHERE status_code = 'NOT_SUITABLE';

        -- Promote review "Not Suitable" outcomes to the NOT_SUITABLE stage.
        UPDATE jd_cv_mapping
           SET application_stage_id = not_suitable_id
         WHERE cv_status = 'NOT_SUITABLE'
           AND application_stage_id IS DISTINCT FROM not_suitable_id;

        ALTER TABLE jd_cv_mapping DROP COLUMN cv_status;
    END IF;
END $$;
