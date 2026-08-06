-- 0020_position_workflow.sql
-- Requirement/Position workflow enhancement: a system-managed "Inactive" seat
-- status, a per-seat status_source marker (drives selective auto-reopen), and a
-- unified status-change audit log for requirements + positions.
-- Additive & idempotent — nothing dropped; existing OPEN/HOLD/FILLED/CANCELLED
-- rows are untouched. ("Expired" is a derived overlay, never a stored status,
-- so no requirement-status row is added or removed here.)

SET search_path = ats, public;

-- 1. New system-managed position status: Inactive (set ONLY by the requirement
--    Hold/Cancel cascade — never a manual choice).
INSERT INTO position_status_master (status_code, status_name) VALUES
    ('INACTIVE', 'Inactive')
ON CONFLICT (status_code) DO NOTHING;

-- 2. Why a seat reached its current status. NULL / 'MANUAL' = human action;
--    'AUTO_REQ_HOLD' / 'AUTO_REQ_CANCEL' = requirement-level cascade. Only
--    auto-sourced seats are automatically reopened when the requirement resumes.
ALTER TABLE requirement_position ADD COLUMN IF NOT EXISTS status_source VARCHAR(20);

-- 3. Unified status-change audit (requirements AND positions), append-only.
CREATE TABLE IF NOT EXISTS status_change_history (
    history_id      SERIAL PRIMARY KEY,
    entity_type     VARCHAR(20) NOT NULL,   -- 'REQUIREMENT' | 'POSITION'
    entity_id       INTEGER     NOT NULL,
    previous_status VARCHAR(30),
    new_status      VARCHAR(30) NOT NULL,
    reason          TEXT,
    change_type     VARCHAR(10) NOT NULL DEFAULT 'MANUAL',  -- 'MANUAL' | 'AUTO'
    changed_by      INTEGER REFERENCES user_master (user_id),
    changed_on      TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_status_history_entity
    ON status_change_history (entity_type, entity_id, changed_on DESC);
