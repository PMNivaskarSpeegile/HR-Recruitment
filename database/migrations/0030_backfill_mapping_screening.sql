-- 0030_backfill_mapping_screening.sql
-- The pipeline board's "Screening" column reads the denormalized
-- jd_cv_mapping.screening_datetime / screening_mode_id. Historically those were
-- left NULL — the scheduled round was written only to the `screening` table — so
-- the column showed blank. schedule/reschedule now keep them in sync; this
-- backfills existing scheduled applications from their latest SCHEDULED round.
-- Data-only, idempotent (only fills rows that are still NULL).

SET search_path = ats, public;

UPDATE jd_cv_mapping m
   SET screening_mode_id = s.screening_mode_id,
       screening_datetime = s.scheduled_at
  FROM (
    SELECT DISTINCT ON (mapping_id)
           mapping_id, screening_mode_id, scheduled_at
      FROM screening
     WHERE status = 'SCHEDULED' AND is_active = TRUE
     ORDER BY mapping_id, scheduled_at DESC, screening_id DESC
  ) s
 WHERE m.mapping_id = s.mapping_id
   AND m.screening_datetime IS NULL;
