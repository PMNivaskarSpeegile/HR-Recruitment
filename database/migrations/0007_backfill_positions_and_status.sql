-- ============================================================================
-- Migration 0007 — Backfill positions + split status (DATA)
-- ----------------------------------------------------------------------------
-- Phase 2 of the recruitment-workflow redesign (see docs/POSITION_REDESIGN.md).
-- Populates the structures added in 0006 from existing data. The legacy
-- cv_status columns are left intact and authoritative until the code cutover;
-- this migration only fills the NEW columns/rows so we can switch reads over
-- safely. Idempotent (re-running maps to the same values; positions are only
-- generated for requirements that don't have any yet).
-- ============================================================================

SET search_path = ats, public;

-- 1. candidate_master.candidate_status_id  <-  cv_status (disposition subset) --
-- Direct code match (NEW_CV / SAVED / FAKE / POSSIBLE_DUPLICATE all exist in
-- candidate_status_master).
UPDATE candidate_master c
SET candidate_status_id = cs.candidate_status_id
FROM cv_status_master old, candidate_status_master cs
WHERE c.cv_status_id = old.cv_status_id
  AND cs.status_code = old.status_code;

-- Fallback: anything unmapped (null cv_status, or a stray pipeline code on a
-- candidate) becomes "New CV".
UPDATE candidate_master
SET candidate_status_id = (SELECT candidate_status_id FROM candidate_status_master WHERE status_code = 'NEW_CV')
WHERE candidate_status_id IS NULL;

-- 2. jd_cv_mapping.application_status_id  <-  cv_status (pipeline stage) --------
-- Direct code match for the pipeline statuses.
UPDATE jd_cv_mapping m
SET application_status_id = aps.application_status_id
FROM cv_status_master old, application_status_master aps
WHERE m.cv_status_id = old.cv_status_id
  AND aps.status_code = old.status_code;

-- A mapping that carried the candidate-level "Fake" flag maps to the closest
-- pipeline outcome, "Not Suitable".
UPDATE jd_cv_mapping m
SET application_status_id = (SELECT application_status_id FROM application_status_master WHERE status_code = 'NOT_SUITABLE')
FROM cv_status_master old
WHERE m.cv_status_id = old.cv_status_id
  AND old.status_code = 'FAKE'
  AND m.application_status_id IS NULL;

-- Fallback: any remaining unmapped application → "New".
UPDATE jd_cv_mapping
SET application_status_id = (SELECT application_status_id FROM application_status_master WHERE status_code = 'NEW')
WHERE application_status_id IS NULL;

-- 3. Generate one requirement_position row per seat ---------------------------
-- positions_open seats per requirement; the first positions_filled marked
-- Closed, the rest Open. Historical closed seats have no linked winning
-- application (no "Joined" data existed pre-redesign), so filled_by_mapping_id
-- stays NULL. Only runs for requirements that have no positions yet.
INSERT INTO requirement_position (req_id, position_no, position_status_id, is_active, created_on)
SELECT r.req_id,
       gs.n,
       CASE WHEN gs.n <= COALESCE(r.positions_filled, 0)
            THEN (SELECT position_status_id FROM position_status_master WHERE status_code = 'FILLED')
            ELSE (SELECT position_status_id FROM position_status_master WHERE status_code = 'OPEN')
       END,
       TRUE,
       now()
FROM requirement_tracker r
CROSS JOIN LATERAL generate_series(1, GREATEST(COALESCE(r.positions_open, 1), 1)) AS gs(n)
WHERE NOT EXISTS (SELECT 1 FROM requirement_position rp WHERE rp.req_id = r.req_id);

-- ============================================================================
-- End of migration 0007
-- ============================================================================
