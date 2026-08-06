-- ============================================================================
-- Migration 0010 — Widen client_master.client_code for auto-generated codes
-- ----------------------------------------------------------------------------
-- Client Code now follows the same lifecycle as other master codes: it's
-- auto-generated from the client name (e.g. "Tata Consultancy Services" ->
-- "TATA_CONSULTANCY_SERVICES"), editable once before the first save, then frozen.
-- The old VARCHAR(10) can't hold a generated code, so widen it to VARCHAR(50).
-- Existing codes are unchanged. Idempotent.
-- ============================================================================

SET search_path = ats, public;

ALTER TABLE client_master ALTER COLUMN client_code TYPE VARCHAR(50);

-- ============================================================================
-- End of migration 0010
-- ============================================================================
