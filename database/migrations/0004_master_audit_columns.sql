-- ============================================================================
-- Migration 0004 — Audit columns for the remaining master tables
-- ----------------------------------------------------------------------------
-- Adds updated_by / updated_on to the master tables that only had created_*,
-- so every master can record who last changed it and support optimistic
-- locking (the updated_on timestamp is the concurrency token). Idempotent.
-- ============================================================================

SET search_path = ats, public;

ALTER TABLE req_status_master      ADD COLUMN IF NOT EXISTS updated_by INTEGER REFERENCES user_master(user_id);
ALTER TABLE req_status_master      ADD COLUMN IF NOT EXISTS updated_on TIMESTAMP(0);

ALTER TABLE cv_status_master       ADD COLUMN IF NOT EXISTS updated_by INTEGER REFERENCES user_master(user_id);
ALTER TABLE cv_status_master       ADD COLUMN IF NOT EXISTS updated_on TIMESTAMP(0);

ALTER TABLE priority_master        ADD COLUMN IF NOT EXISTS updated_by INTEGER REFERENCES user_master(user_id);
ALTER TABLE priority_master        ADD COLUMN IF NOT EXISTS updated_on TIMESTAMP(0);

ALTER TABLE notice_period_master   ADD COLUMN IF NOT EXISTS updated_by INTEGER REFERENCES user_master(user_id);
ALTER TABLE notice_period_master   ADD COLUMN IF NOT EXISTS updated_on TIMESTAMP(0);

ALTER TABLE req_type_master        ADD COLUMN IF NOT EXISTS updated_by INTEGER REFERENCES user_master(user_id);
ALTER TABLE req_type_master        ADD COLUMN IF NOT EXISTS updated_on TIMESTAMP(0);

ALTER TABLE work_mode_master       ADD COLUMN IF NOT EXISTS updated_by INTEGER REFERENCES user_master(user_id);
ALTER TABLE work_mode_master       ADD COLUMN IF NOT EXISTS updated_on TIMESTAMP(0);

ALTER TABLE source_master          ADD COLUMN IF NOT EXISTS updated_by INTEGER REFERENCES user_master(user_id);
ALTER TABLE source_master          ADD COLUMN IF NOT EXISTS updated_on TIMESTAMP(0);

ALTER TABLE screening_mode_master  ADD COLUMN IF NOT EXISTS updated_by INTEGER REFERENCES user_master(user_id);
ALTER TABLE screening_mode_master  ADD COLUMN IF NOT EXISTS updated_on TIMESTAMP(0);

ALTER TABLE rejection_reason_master ADD COLUMN IF NOT EXISTS updated_by INTEGER REFERENCES user_master(user_id);
ALTER TABLE rejection_reason_master ADD COLUMN IF NOT EXISTS updated_on TIMESTAMP(0);

-- ============================================================================
-- End of migration 0004
-- ============================================================================
