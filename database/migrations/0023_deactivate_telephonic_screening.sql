-- 0023_deactivate_telephonic_screening.sql
-- The current recruiter process runs a single Video screening round; the
-- Telephonic mode is retired for now. Deactivate it (rather than delete) so it
-- stops appearing in the scheduling dropdown but the row — and every historical
-- screening that references it — is preserved and can be re-activated later.
-- Data-only, idempotent — no schema change.

SET search_path = ats, public;

UPDATE screening_mode_master
   SET is_active = FALSE
 WHERE mode_code = 'TELEPHONIC';
