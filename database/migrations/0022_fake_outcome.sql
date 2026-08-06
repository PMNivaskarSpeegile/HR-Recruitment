-- 0022_fake_outcome.sql
-- Fake is now a first-class stage OUTCOME (recorded on the application via
-- jd_cv_mapping.latest_outcome), not a special case. Add the master row.
-- Data-only, additive, idempotent — no schema change.

SET search_path = ats, public;

INSERT INTO application_status_master (status_code, status_name, kind, is_active) VALUES
    ('FAKE', 'Fake', 'OUTCOME', TRUE)
ON CONFLICT (status_code) DO UPDATE SET kind = 'OUTCOME', status_name = 'Fake';
