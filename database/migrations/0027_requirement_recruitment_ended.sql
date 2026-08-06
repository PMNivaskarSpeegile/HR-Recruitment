-- 0027_requirement_recruitment_ended.sql
-- "End Recruitment" is a permanent Hiring-Manager business decision on an
-- expired, partially-filled requirement: the remaining open seats are withdrawn
-- (Inactive) and the remaining active applications are closed, while the
-- requirement KEEPS its calculated status (Partial Filled) + Expired indicator.
--
-- This flag is the source of truth that freezes the automatic status rollup
-- (so inactivating the open seats does NOT roll the requirement to Close Filled)
-- and permanently blocks further recruitment. Additive & backward compatible —
-- existing rows default to FALSE (recruitment not ended).

SET search_path = ats, public;

ALTER TABLE requirement_tracker
    ADD COLUMN IF NOT EXISTS recruitment_ended    boolean      NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS recruitment_ended_on timestamp,
    ADD COLUMN IF NOT EXISTS recruitment_ended_by integer;

-- Match the existing FK convention (created_by / updated_by → user_master).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'requirement_tracker_recruitment_ended_by_fkey'
          AND table_schema = 'ats'
    ) THEN
        ALTER TABLE requirement_tracker
            ADD CONSTRAINT requirement_tracker_recruitment_ended_by_fkey
            FOREIGN KEY (recruitment_ended_by) REFERENCES user_master (user_id);
    END IF;
END $$;
