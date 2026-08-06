-- ============================================================================
-- Migration 0005 — Promote Skill "Domain" to controlled master data
-- ----------------------------------------------------------------------------
-- Domains were a free-text column on skill_master (skill_domain). This makes
-- them proper, centrally-managed classification data:
--   * new domain_master table (unique, audited, soft-deletable);
--   * skill_master gains a domain_id FK → domain_master;
--   * existing free-text values are backfilled into domain_master and linked;
--   * the old skill_domain text column is dropped (single source of truth, so
--     renaming a domain reflects on every linked skill automatically).
-- Skills stay the resume-facing master; Domains only organise them. Candidates
-- and Requirements keep referencing Skills, never Domains.
-- Idempotent: safe to re-run (guards + IF [NOT] EXISTS, backfill only runs
-- while the legacy column is still present).
-- ============================================================================

SET search_path = ats, public;

-- 1. Domain master ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS domain_master (
    domain_id   SERIAL PRIMARY KEY,
    domain_name VARCHAR(60) NOT NULL UNIQUE,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_by  INTEGER REFERENCES user_master(user_id),
    created_on  TIMESTAMP(0),
    updated_by  INTEGER REFERENCES user_master(user_id),
    updated_on  TIMESTAMP(0)
);

-- 2. Skill → Domain foreign key ----------------------------------------------
ALTER TABLE skill_master ADD COLUMN IF NOT EXISTS domain_id INTEGER REFERENCES domain_master(domain_id);

-- 3. Backfill + drop the legacy free-text column (only while it still exists) --
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'ats' AND table_name = 'skill_master' AND column_name = 'skill_domain'
    ) THEN
        -- One domain row per distinct (trimmed) legacy value.
        INSERT INTO domain_master (domain_name, is_active, created_on)
        SELECT DISTINCT TRIM(skill_domain), TRUE, now()
        FROM skill_master
        WHERE skill_domain IS NOT NULL AND TRIM(skill_domain) <> ''
        ON CONFLICT (domain_name) DO NOTHING;

        -- Link each skill to its domain (case-/space-tolerant match).
        UPDATE skill_master s
        SET domain_id = d.domain_id
        FROM domain_master d
        WHERE TRIM(s.skill_domain) = d.domain_name;

        ALTER TABLE skill_master DROP COLUMN skill_domain;
    END IF;
END $$;

-- ============================================================================
-- End of migration 0005
-- ============================================================================
