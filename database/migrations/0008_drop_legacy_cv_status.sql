-- ============================================================================
-- Migration 0008 — Retire the legacy mixed cv_status (redesign cleanup)
-- ----------------------------------------------------------------------------
-- Phase 4 (final) of the recruitment-workflow redesign. The candidate
-- disposition and application/pipeline stage are now owned by the dedicated
-- masters (candidate_status_master / application_status_master, backfilled in
-- 0007 and read everywhere since the code cutover). This removes the old mixed
-- column + table so there is a single source of truth.
--
--   * drop candidate_master.cv_status_id  (→ candidate_status_id)
--   * drop jd_cv_mapping.cv_status_id      (→ application_status_id)
--   * drop cv_status_master
-- Idempotent (IF EXISTS). NOT reversible — run only after the code no longer
-- references cv_status.
-- ============================================================================

SET search_path = ats, public;

ALTER TABLE candidate_master DROP COLUMN IF EXISTS cv_status_id;
ALTER TABLE jd_cv_mapping    DROP COLUMN IF EXISTS cv_status_id;
DROP TABLE IF EXISTS cv_status_master;

-- ============================================================================
-- End of migration 0008
-- ============================================================================
