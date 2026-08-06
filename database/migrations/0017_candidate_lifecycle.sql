-- 0017_candidate_lifecycle.sql
-- Candidate lifecycle automation: Reject-Hold + Joined retention.
-- Adds the two system-managed candidate statuses and the working/automation
-- fields on candidate_master. History (applications, interactions, activity)
-- is untouched — active_rejection_count is only a working counter for automation.

SET search_path = ats, public;

-- New system-managed candidate statuses (Talent Pool = existing SAVED code).
INSERT INTO candidate_status_master (status_code, status_name) VALUES
    ('REJECT_HOLD', 'Reject Hold'),
    ('JOINED',      'Joined')
ON CONFLICT (status_code) DO NOTHING;

-- Working / automation fields on the candidate. Additive only.
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS active_rejection_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS reject_hold_start      DATE;
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS reject_hold_until      DATE;
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS joined_date            DATE;
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS last_status_changed_on TIMESTAMP;
