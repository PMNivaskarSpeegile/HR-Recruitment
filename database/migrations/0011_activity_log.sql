-- ============================================================================
-- Migration 0011 — Activity log (audit feed) + application joined_date
-- ----------------------------------------------------------------------------
-- Makes two dashboard signals accurate instead of derived:
--   * activity_log        — a proper cross-entity audit feed (who did what,
--                           when) powering the Admin "Recent activity" panel and
--                           future history/compliance views.
--   * jd_cv_mapping.joined_date — the real date a candidate joined, so
--                           "Joined This Month" / time-to-fill are exact rather
--                           than proxied off updated_on.
-- Idempotent. Backfills joined_date for existing JOINED rows and seeds the feed
-- from existing history the first time it runs.
-- ============================================================================

SET search_path = ats, public;

CREATE TABLE IF NOT EXISTS activity_log (
    activity_id   BIGSERIAL PRIMARY KEY,
    activity_type VARCHAR(40) NOT NULL,
    summary       TEXT NOT NULL,
    req_id        INTEGER REFERENCES requirement_tracker(req_id),
    cv_id         INTEGER REFERENCES candidate_master(cv_id),
    actor_id      INTEGER REFERENCES user_master(user_id),
    created_on    TIMESTAMP(0) NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_activity_log_created ON activity_log(created_on DESC);

ALTER TABLE jd_cv_mapping ADD COLUMN IF NOT EXISTS joined_date DATE;

-- Backfill the real joined date for any existing JOINED applications.
UPDATE jd_cv_mapping m
SET joined_date = COALESCE(m.updated_on::date, CURRENT_DATE)
FROM application_status_master a
WHERE m.application_status_id = a.application_status_id
  AND a.status_code = 'JOINED'
  AND m.joined_date IS NULL;

-- Seed the feed from existing history, but only the first time (keep idempotent).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM activity_log) THEN
        INSERT INTO activity_log (activity_type, summary, req_id, actor_id, created_on)
        SELECT 'requirement_created', 'Requirement opened: ' || jd_role_name, req_id, created_by, created_on
        FROM requirement_tracker
        WHERE created_on IS NOT NULL;

        INSERT INTO activity_log (activity_type, summary, cv_id, actor_id, created_on)
        SELECT 'candidate_added', 'Candidate added: ' || candidate_name, cv_id, uploaded_by, created_on
        FROM candidate_master
        WHERE created_on IS NOT NULL;
    END IF;
END $$;

-- ============================================================================
-- End of migration 0011
-- ============================================================================
