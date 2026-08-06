-- 0019_candidate_profile_verification.sql
-- Candidate Profile Verification & Update: extra master-profile fields, a
-- verification stamp, and a field-level audit trail. Additive only — does not
-- touch lifecycle, statuses, or the duplicate-review workflow.

SET search_path = ats, public;

-- Extra (non-system) master-profile fields.
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS current_designation VARCHAR(120);
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS relevant_exp        NUMERIC(4,1);
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS certifications      TEXT;
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS additional_notes    TEXT;

-- Verification stamp (set on "Verify & Update Profile", typically during screening).
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS profile_verified    BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS profile_verified_by INTEGER REFERENCES user_master (user_id);
ALTER TABLE candidate_master ADD COLUMN IF NOT EXISTS profile_verified_on TIMESTAMP;

-- Field-level audit trail — one row per changed field per update (never overwritten).
CREATE TABLE IF NOT EXISTS candidate_profile_audit (
    audit_id    SERIAL PRIMARY KEY,
    cv_id       INTEGER NOT NULL REFERENCES candidate_master (cv_id),
    field_name  VARCHAR(60) NOT NULL,
    old_value   TEXT,
    new_value   TEXT,
    source      VARCHAR(40) NOT NULL DEFAULT 'Recruiter Manual Update',
    changed_by  INTEGER REFERENCES user_master (user_id),
    changed_on  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profile_audit_cv ON candidate_profile_audit (cv_id, changed_on DESC);
