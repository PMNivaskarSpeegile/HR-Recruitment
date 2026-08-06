-- 0024_candidate_import_fields.sql
-- Additive, nullable fields on candidate_master to preserve bulk-import
-- (mentor-approved Naukri template) candidate data exactly as imported:
--   date_of_birth          — the candidate's actual DOB (authoritative)
--   age_at_import          — the Age snapshot as it appeared in the sheet
--                            (never recalculated automatically)
--   postal_address         — postal address as imported (onboarding/logistics)
--   current_location_text  — the ORIGINAL location string when it can't be
--                            mapped to location_master (never silently discarded)
-- No backfill, no changes to existing columns — fully backward compatible.

SET search_path = ats, public;

ALTER TABLE candidate_master
    ADD COLUMN IF NOT EXISTS date_of_birth          date,
    ADD COLUMN IF NOT EXISTS age_at_import          smallint,
    ADD COLUMN IF NOT EXISTS postal_address         varchar(255),
    ADD COLUMN IF NOT EXISTS current_location_text  varchar(150);
