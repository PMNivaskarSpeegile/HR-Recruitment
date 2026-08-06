-- 0029_fix_requirement_req_date.sql
-- Data fix for the date-mapping bug (see the "Required by wrote the wrong date
-- field" changelog entry). Under the old bug the requirement form wrote the user's
-- "Required by" deadline into req_date (the creation date). That both showed the
-- deadline as "Created" AND broke recruiter assignment: assign sets
-- assigned_date = today, and the DB constraint chk_dates (assigned_date >= req_date)
-- fails whenever req_date holds a FUTURE date.
--
-- This restores req_date to the actual creation date, and — where the deadline was
-- lost into req_date (target_fill_date empty) — recovers it into target_fill_date.
-- Data-only, idempotent, no schema change. New requirements are already correct
-- (req_date is set server-side; the field is no longer user-writable).

SET search_path = ats, public;

-- 1) Recover a "Required by" deadline that was lost into req_date.
UPDATE requirement_tracker
   SET target_fill_date = req_date
 WHERE target_fill_date IS NULL
   AND created_on IS NOT NULL
   AND req_date > created_on::date;

-- 2) Reset a future/misplaced req_date back to the true creation date.
UPDATE requirement_tracker
   SET req_date = created_on::date
 WHERE created_on IS NOT NULL
   AND req_date > created_on::date;

-- 3) Safety net: any remaining future req_date (creation timestamp missing) → today.
UPDATE requirement_tracker
   SET req_date = CURRENT_DATE
 WHERE req_date > CURRENT_DATE;
