--
-- Speegile ATS - reference / master (lookup) data
--
-- The ONE official reference-data seed. Run AFTER `ats db schema.sql` and BEFORE
-- `python manage.py seed_demo`. Contains ONLY static lookup/enum data the app and
-- seed_demo depend on (roles, statuses, priorities, notice periods, req types,
-- work modes, sources, screening modes, rejection reasons, JD email template).
-- No transactional/demo rows (candidates, requirements, mappings, users, clients,
-- skills, locations) - those are created by `manage.py seed_demo`.
--
-- Generated from the live ats_db; business columns only (identity PKs auto-
-- generate). Idempotent: ON CONFLICT DO NOTHING, safe to re-run.
--

SET search_path = ats, public;

-- role_master (3 rows)
INSERT INTO ats.role_master (role_code, role_name) VALUES
    ('ADM', 'Administrator'),
    ('REC', 'Recruiter'),
    ('HM', 'Hiring Manager')
ON CONFLICT DO NOTHING;

-- req_status_master (8 rows)
INSERT INTO ats.req_status_master (status_code, status_name, description, is_active) VALUES
    ('OPEN', 'Open', NULL, TRUE),
    ('ASSIGNED', 'Assigned', NULL, TRUE),
    ('CANCELLED', 'Cancelled', NULL, TRUE),
    ('HOLD', 'Hold', NULL, TRUE),
    ('PARTIAL_FILLED', 'Partial Filled', NULL, TRUE),
    ('CLOSE_FILLED', 'Close Filled', NULL, TRUE),
    ('CLOSE_LOST', 'Close Lost', 'Closed without filling - lost to competitor or budget cut', TRUE),
    ('NEW', 'New', NULL, TRUE)
ON CONFLICT DO NOTHING;

-- priority_master (3 rows)
INSERT INTO ats.priority_master (priority_name, description, is_active) VALUES
    ('High', NULL, TRUE),
    ('Medium', NULL, TRUE),
    ('Low', NULL, TRUE)
ON CONFLICT DO NOTHING;

-- notice_period_master (6 rows)
INSERT INTO ats.notice_period_master (np_name, is_active) VALUES
    ('Immediate', TRUE),
    ('15 Days', TRUE),
    ('30 Days', TRUE),
    ('45 Days', TRUE),
    ('60 Days', TRUE),
    ('90 Days', TRUE)
ON CONFLICT DO NOTHING;

-- req_type_master (2 rows)
INSERT INTO ats.req_type_master (req_type_code, req_type_name, description, is_active) VALUES
    ('FTE', 'Full Time Employment', NULL, TRUE),
    ('TPR', 'Third Party Roll', NULL, TRUE)
ON CONFLICT DO NOTHING;

-- work_mode_master (3 rows)
INSERT INTO ats.work_mode_master (work_mode_code, work_mode_name, is_active) VALUES
    ('WFO', 'Work From Office', TRUE),
    ('WFH', 'Work From Home', TRUE),
    ('HYB', 'Hybrid', TRUE)
ON CONFLICT DO NOTHING;

-- source_master (4 rows)
INSERT INTO ats.source_master (source_name, source_type, is_active) VALUES
    ('Naukri', 'Job Portal', TRUE),
    ('LinkedIn', 'Professional Network', TRUE),
    ('Referral', 'Employee Referral', TRUE),
    ('Apna Jobs', 'Job Portal', TRUE)
ON CONFLICT DO NOTHING;

-- candidate_status_master (7 rows)
INSERT INTO ats.candidate_status_master (status_code, status_name, description, is_active) VALUES
    ('NEW_CV', 'New CV', NULL, TRUE),
    ('SAVED', 'Talent Pool', NULL, TRUE),
    ('FAKE', 'Fake', NULL, TRUE),
    ('POSSIBLE_DUPLICATE', 'Possible Duplicate', NULL, TRUE),
    ('BLACKLISTED', 'Blacklisted', NULL, TRUE),
    ('REJECT_HOLD', 'Reject Hold', NULL, TRUE),
    ('JOINED', 'Joined', NULL, TRUE)
ON CONFLICT DO NOTHING;

-- application_status_master (21 rows)
INSERT INTO ats.application_status_master (status_code, status_name, description, kind, sort_order, is_active) VALUES
    ('NEW', 'New', NULL, 'STAGE', 0, TRUE),
    ('SHORTLISTED', 'Shortlisted', NULL, 'STAGE', 10, TRUE),
    ('JD_EMAIL_SENT', 'JD Email Sent', NULL, 'STAGE', 20, TRUE),
    ('NO_RESPONSE', 'No Response', NULL, 'OUTCOME', NULL, TRUE),
    ('DROPPED', 'Dropped', NULL, 'OUTCOME', NULL, TRUE),
    ('SCREENING_SCHEDULED', 'Screening Scheduled', NULL, 'STAGE', 30, TRUE),
    ('NOT_SUITABLE', 'Not Suitable', NULL, 'OUTCOME', NULL, TRUE),
    ('REJECTED', 'Rejected', NULL, 'OUTCOME', NULL, TRUE),
    ('OK_TO_PROCEED', 'OK to Proceed', NULL, 'STAGE', 40, TRUE),
    ('OFFERED', 'Offer Released', NULL, 'STAGE', 50, TRUE),
    ('JOINED', 'Joined', NULL, 'OUTCOME', NULL, TRUE),
    ('WITHDRAWN', 'Withdrawn', NULL, 'OUTCOME', NULL, TRUE),
    ('AWAITING_JOINING', 'Awaiting Joining', NULL, 'STAGE', 60, TRUE),
    ('OFFER_DECLINED', 'Offer Declined', NULL, 'OUTCOME', NULL, TRUE),
    ('BLACKLISTED', 'Blacklisted', NULL, 'OUTCOME', NULL, TRUE),
    ('OFFER_ACCEPTED', 'Offer Accepted', NULL, 'OUTCOME', NULL, TRUE),
    ('PASSED', 'OK to Proceed', NULL, 'OUTCOME', NULL, TRUE),
    ('FAKE', 'Fake', NULL, 'OUTCOME', NULL, TRUE),
    -- System requirement-closure outcomes (auto-closed remaining applications).
    ('REQ_CLOSE_FILLED', 'Requirement Filled', NULL, 'OUTCOME', NULL, TRUE),
    ('REQ_POSITIONS_WITHDRAWN', 'Positions Withdrawn', NULL, 'OUTCOME', NULL, TRUE),
    ('REQ_CLOSE_LOST', 'Requirement Closed Lost', NULL, 'OUTCOME', NULL, TRUE)
ON CONFLICT DO NOTHING;

-- position_status_master (5 rows)
INSERT INTO ats.position_status_master (status_code, status_name, description, is_active) VALUES
    ('OPEN', 'Open', NULL, TRUE),
    ('FILLED', 'Filled', NULL, TRUE),
    ('CANCELLED', 'Cancelled', NULL, TRUE),
    ('HOLD', 'Hold', NULL, TRUE),
    ('INACTIVE', 'Inactive', NULL, TRUE)
ON CONFLICT DO NOTHING;

-- screening_mode_master (2 rows) — Telephonic retired (inactive); single Video
-- round is the current process. Row kept so it can be re-activated later.
INSERT INTO ats.screening_mode_master (mode_code, mode_name, description, is_active) VALUES
    ('TELEPHONIC', 'Telephonic', 'Screening conducted over a phone call', FALSE),
    ('VIDEO', 'Video', 'Screening conducted over a video call', TRUE)
ON CONFLICT DO NOTHING;

-- rejection_reason_master (10 rows)
INSERT INTO ats.rejection_reason_master (reason_code, reason_name, description, is_active) VALUES
    ('SKILLS_MISMATCH', 'Skills mismatch', NULL, TRUE),
    ('LOW_EXPERIENCE', 'Insufficient experience', NULL, TRUE),
    ('CTC_EXPECTATION', 'CTC expectations too high', NULL, TRUE),
    ('LOCATION', 'Location / relocation', NULL, TRUE),
    ('NOTICE_PERIOD', 'Notice period too long', NULL, TRUE),
    ('NOT_INTERESTED', 'Not interested', NULL, TRUE),
    ('UNREACHABLE', 'Unreachable', NULL, TRUE),
    ('FAILED_SCREENING', 'Failed screening', NULL, TRUE),
    ('DUPLICATE_FAKE', 'Duplicate / fake profile', NULL, TRUE),
    ('POSITION_CLOSED', 'Position closed', NULL, TRUE)
ON CONFLICT DO NOTHING;

-- email_template_master (1 rows)
INSERT INTO ats.email_template_master (template_code, name, subject, body, is_active) VALUES
    ('JD_EMAIL', 'Job Description Email', 'Job Opportunity: {role} at {client}', 'Dear {candidate_name},

We have an opportunity that matches your profile:

Role: {role}
Client: {client}
Location: {location}
Experience: {exp}
Rate (CTC): {ctc}
Notice period: {notice}
Key skills: {skills}

Please reply to this email to confirm your interest and availability.

Regards,
{sender}', TRUE)
ON CONFLICT DO NOTHING;

