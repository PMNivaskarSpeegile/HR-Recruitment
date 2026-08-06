-- 0028_candidate_requirement_review.sql
-- Pre-pipeline "candidate under review for a requirement" association (the Review
-- Pool). This is EXPLICIT (created by tagging) — it replaces the old implicit
-- skill-match association — and is completely separate from jd_cv_mapping, which
-- continues to mean "candidate entered the recruitment pipeline (Shortlist)".
--
-- One ACTIVE row per (candidate, requirement); a candidate may be under review for
-- many requirements. Resolved (with a resolution + audit) on a recruiter decision,
-- untag, or requirement closure. Additive & backward compatible — no existing
-- table is changed.

SET search_path = ats, public;

CREATE TABLE IF NOT EXISTS candidate_requirement_review (
    review_id    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cv_id        integer NOT NULL,
    req_id       integer NOT NULL,
    status       character varying(20) NOT NULL DEFAULT 'ACTIVE',
    resolution   character varying(30),
    tagged_by    integer,
    tagged_on    timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    resolved_by  integer,
    resolved_on  timestamp without time zone,
    created_on   timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_on   timestamp without time zone,
    CONSTRAINT candidate_requirement_review_cv_id_fkey
        FOREIGN KEY (cv_id) REFERENCES candidate_master (cv_id) ON DELETE CASCADE,
    CONSTRAINT candidate_requirement_review_req_id_fkey
        FOREIGN KEY (req_id) REFERENCES requirement_tracker (req_id),
    CONSTRAINT candidate_requirement_review_tagged_by_fkey
        FOREIGN KEY (tagged_by) REFERENCES user_master (user_id),
    CONSTRAINT candidate_requirement_review_resolved_by_fkey
        FOREIGN KEY (resolved_by) REFERENCES user_master (user_id),
    -- One association per (candidate, requirement). Re-tagging after a RESOLVED
    -- decision reactivates the same row (status → ACTIVE), preserving history.
    CONSTRAINT uq_candidate_requirement_review UNIQUE (cv_id, req_id)
);

-- Review-pool listing per requirement, and a candidate's active tags.
CREATE INDEX IF NOT EXISTS ix_crr_req_status ON candidate_requirement_review (req_id, status);
CREATE INDEX IF NOT EXISTS ix_crr_cv_status  ON candidate_requirement_review (cv_id, status);
