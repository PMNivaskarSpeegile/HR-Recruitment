-- 0026_requirement_closure_outcomes.sql
-- When a requirement reaches an irreversible terminal state (Close Filled /
-- Close Lost) or an expired, partially-filled requirement has recruitment ended,
-- its remaining ACTIVE applications are auto-closed with a system-generated,
-- non-rejection OUTCOME and the candidates return to the Talent Pool.
--
-- These are the three closure outcomes. Data-only, additive, idempotent — no
-- structural schema change (rows in the existing application_status_master).

SET search_path = ats, public;

INSERT INTO application_status_master (status_code, status_name, kind, is_active) VALUES
    ('REQ_CLOSE_FILLED',        'Requirement Filled',      'OUTCOME', TRUE),
    ('REQ_POSITIONS_WITHDRAWN', 'Positions Withdrawn',     'OUTCOME', TRUE),
    ('REQ_CLOSE_LOST',          'Requirement Closed Lost', 'OUTCOME', TRUE)
ON CONFLICT (status_code) DO UPDATE
    SET kind = 'OUTCOME', status_name = EXCLUDED.status_name, is_active = TRUE;
