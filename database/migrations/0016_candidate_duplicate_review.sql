-- 0016_candidate_duplicate_review.sql
-- Duplicate Review workflow — a SEPARATE business process from the candidate
-- lifecycle (candidate_status is never touched). A review captures a detected
-- possible-duplicate (same mobile, different email) so an Admin can resolve it
-- (merge later / keep separate / correct data). Full audit: who/when created &
-- resolved. No candidate data is moved here — this is the review + resolution
-- record, and the future entry point for merge.

SET search_path = ats, public;

CREATE TABLE IF NOT EXISTS candidate_duplicate_review (
    review_id           SERIAL PRIMARY KEY,
    existing_cv_id      INTEGER NOT NULL REFERENCES candidate_master (cv_id),
    new_candidate_name  VARCHAR(150) NOT NULL,
    new_mobile          VARCHAR(20)  NOT NULL,
    new_email           VARCHAR(150),
    submitted_payload   JSONB,                     -- full submitted data (for future merge)
    detection_reason    VARCHAR(120) NOT NULL,
    review_status       VARCHAR(20)  NOT NULL DEFAULT 'PENDING',   -- PENDING | RESOLVED
    resolution          VARCHAR(30),               -- MERGED | KEPT_SEPARATE | CORRECTED
    notes               TEXT,
    created_by          INTEGER REFERENCES user_master (user_id),
    created_on          TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_by         INTEGER REFERENCES user_master (user_id),
    resolved_on         TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dupreview_status   ON candidate_duplicate_review (review_status);
CREATE INDEX IF NOT EXISTS idx_dupreview_existing ON candidate_duplicate_review (existing_cv_id);
