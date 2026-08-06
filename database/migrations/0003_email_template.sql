-- ============================================================================
-- Migration 0003 — Email template master (JD email module)
-- ----------------------------------------------------------------------------
-- Admin-editable email templates (configuration as data). One render function
-- (backend) powers both the JD preview and the actual send, so the preview is
-- always faithful. Placeholders: {candidate_name} {role} {client} {location}
-- {exp} {ctc} {notice} {skills} {sender}
-- ============================================================================

SET search_path = ats, public;

CREATE TABLE IF NOT EXISTS email_template_master (
    template_id   SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    template_code VARCHAR(40)  NOT NULL UNIQUE,
    name          VARCHAR(80)  NOT NULL,
    subject       VARCHAR(255) NOT NULL,
    body          TEXT         NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by    INTEGER REFERENCES user_master(user_id),
    created_on    TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    updated_by    INTEGER REFERENCES user_master(user_id),
    updated_on    TIMESTAMP(0)
);

INSERT INTO email_template_master (template_code, name, subject, body) VALUES
('JD_EMAIL', 'Job Description Email', 'Job Opportunity: {role} at {client}',
'Dear {candidate_name},

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
{sender}')
ON CONFLICT (template_code) DO NOTHING;

-- ============================================================================
-- End of migration 0003
-- ============================================================================
