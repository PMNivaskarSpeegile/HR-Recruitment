--
-- Speegile ATS - PostgreSQL schema (schema: ats)
--
-- SOURCE OF TRUTH for a fresh database. Generated from the live ats_db via
--   pg_dump --schema-only -n ats --no-owner --no-privileges
-- which reflects the base schema plus every database/migrations/*.sql applied
-- (through 0030_backfill_mapping_screening.sql — the latest migration).
--
-- The Django models are managed=False and mirror THIS schema (see backend/
-- admin_module/models.py). Django never creates/alters these tables.
--
-- To regenerate after adding a numbered migration, re-run the pg_dump above.
-- See database/README.md for setup.
--

--
-- PostgreSQL database dump
--



SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
-- SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: ats; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA IF NOT EXISTS ats;
SET search_path = ats, public;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: activity_log; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.activity_log (
    activity_id bigint NOT NULL,
    activity_type character varying(40) NOT NULL,
    summary text NOT NULL,
    req_id integer,
    cv_id integer,
    actor_id integer,
    created_on timestamp(0) without time zone DEFAULT now() NOT NULL
);


--
-- Name: activity_log_activity_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

CREATE SEQUENCE ats.activity_log_activity_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: activity_log_activity_id_seq; Type: SEQUENCE OWNED BY; Schema: ats; Owner: -
--

ALTER SEQUENCE ats.activity_log_activity_id_seq OWNED BY ats.activity_log.activity_id;


--
-- Name: application_status_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.application_status_master (
    application_status_id smallint NOT NULL,
    status_code character varying(50) NOT NULL,
    status_name character varying(60) NOT NULL,
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone,
    updated_by integer,
    updated_on timestamp(0) without time zone,
    kind character varying(10),
    sort_order smallint
);


--
-- Name: application_status_master_application_status_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

CREATE SEQUENCE ats.application_status_master_application_status_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: application_status_master_application_status_id_seq; Type: SEQUENCE OWNED BY; Schema: ats; Owner: -
--

ALTER SEQUENCE ats.application_status_master_application_status_id_seq OWNED BY ats.application_status_master.application_status_id;


--
-- Name: candidate_duplicate_review; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.candidate_duplicate_review (
    review_id integer NOT NULL,
    existing_cv_id integer NOT NULL,
    new_candidate_name character varying(150) NOT NULL,
    new_mobile character varying(20) NOT NULL,
    new_email character varying(150),
    submitted_payload jsonb,
    detection_reason character varying(120) NOT NULL,
    review_status character varying(20) DEFAULT 'PENDING'::character varying NOT NULL,
    resolution character varying(30),
    notes text,
    created_by integer,
    created_on timestamp without time zone DEFAULT now() NOT NULL,
    resolved_by integer,
    resolved_on timestamp without time zone
);


--
-- Name: candidate_duplicate_review_review_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

CREATE SEQUENCE ats.candidate_duplicate_review_review_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: candidate_duplicate_review_review_id_seq; Type: SEQUENCE OWNED BY; Schema: ats; Owner: -
--

ALTER SEQUENCE ats.candidate_duplicate_review_review_id_seq OWNED BY ats.candidate_duplicate_review.review_id;


--
-- Name: candidate_interaction; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.candidate_interaction (
    interaction_id integer NOT NULL,
    cv_id integer NOT NULL,
    req_id integer,
    interaction_type character varying(40) NOT NULL,
    comment text NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: candidate_interaction_interaction_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.candidate_interaction ALTER COLUMN interaction_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.candidate_interaction_interaction_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: candidate_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.candidate_master (
    cv_id integer NOT NULL,
    cv_serial character varying(20) NOT NULL,
    candidate_name character varying(100) NOT NULL,
    mobile character varying(15) NOT NULL,
    email character varying(150) NOT NULL,
    exp_min numeric(4,1),
    exp_max numeric(4,1),
    current_location_id integer,
    preferred_location_id integer,
    notice_period_id smallint,
    work_mode_id smallint,
    current_company character varying(100),
    current_ctc_lpa numeric(7,2),
    expected_ctc_lpa numeric(7,2),
    highest_qualification character varying(80),
    source_id smallint,
    is_duplicate boolean DEFAULT false NOT NULL,
    is_willing_to_relocate boolean DEFAULT false NOT NULL,
    uploaded_by integer NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_on timestamp(0) without time zone,
    updated_by integer,
    duplicate_of_cv_id integer,
    candidate_status_id smallint,
    active_rejection_count integer DEFAULT 0 NOT NULL,
    reject_hold_start date,
    reject_hold_until date,
    joined_date date,
    last_status_changed_on timestamp without time zone,
    current_designation character varying(120),
    relevant_exp numeric(4,1),
    certifications text,
    additional_notes text,
    date_of_birth date,
    age_at_import smallint,
    postal_address character varying(255),
    current_location_text character varying(150),
    import_batch_id integer,
    profile_verified boolean DEFAULT false NOT NULL,
    profile_verified_by integer,
    profile_verified_on timestamp without time zone,
    CONSTRAINT chk_cand_exp_range CHECK (((exp_min IS NULL) OR (exp_max IS NULL) OR (exp_max >= exp_min))),
    CONSTRAINT chk_ctc_positive CHECK (((current_ctc_lpa IS NULL) OR (current_ctc_lpa >= (0)::numeric))),
    CONSTRAINT chk_ectc_positive CHECK (((expected_ctc_lpa IS NULL) OR (expected_ctc_lpa >= (0)::numeric))),
    CONSTRAINT chk_exp_max_positive CHECK (((exp_max IS NULL) OR (exp_max >= (0)::numeric))),
    CONSTRAINT chk_exp_min_positive CHECK (((exp_min IS NULL) OR (exp_min >= (0)::numeric)))
);


--
-- Name: candidate_master_cv_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.candidate_master ALTER COLUMN cv_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.candidate_master_cv_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: candidate_profile_audit; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.candidate_profile_audit (
    audit_id integer NOT NULL,
    cv_id integer NOT NULL,
    field_name character varying(60) NOT NULL,
    old_value text,
    new_value text,
    source character varying(40) DEFAULT 'Recruiter Manual Update'::character varying NOT NULL,
    changed_by integer,
    changed_on timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: candidate_profile_audit_audit_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

CREATE SEQUENCE ats.candidate_profile_audit_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: candidate_profile_audit_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: ats; Owner: -
--

ALTER SEQUENCE ats.candidate_profile_audit_audit_id_seq OWNED BY ats.candidate_profile_audit.audit_id;


--
-- Name: candidate_skill; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.candidate_skill (
    cs_id integer NOT NULL,
    cv_id integer NOT NULL,
    skill_id integer NOT NULL,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: candidate_skill_cs_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.candidate_skill ALTER COLUMN cs_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.candidate_skill_cs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: candidate_status_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.candidate_status_master (
    candidate_status_id smallint NOT NULL,
    status_code character varying(50) NOT NULL,
    status_name character varying(60) NOT NULL,
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone,
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: candidate_status_master_candidate_status_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

CREATE SEQUENCE ats.candidate_status_master_candidate_status_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: candidate_status_master_candidate_status_id_seq; Type: SEQUENCE OWNED BY; Schema: ats; Owner: -
--

ALTER SEQUENCE ats.candidate_status_master_candidate_status_id_seq OWNED BY ats.candidate_status_master.candidate_status_id;


--
-- Name: client_manager_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.client_manager_master (
    client_mgr_id integer NOT NULL,
    client_id integer NOT NULL,
    manager_name character varying(100) NOT NULL,
    designation character varying(80),
    email character varying(150) NOT NULL,
    mobile character varying(15),
    department character varying(60),
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_on timestamp(0) without time zone,
    updated_by integer
);


--
-- Name: client_manager_master_client_mgr_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.client_manager_master ALTER COLUMN client_mgr_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.client_manager_master_client_mgr_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: client_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.client_master (
    client_id integer NOT NULL,
    client_code character varying(50) NOT NULL,
    client_name character varying(120) NOT NULL,
    industry character varying(60),
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_on timestamp(0) without time zone,
    updated_by integer
);


--
-- Name: client_master_client_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.client_master ALTER COLUMN client_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.client_master_client_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: communication_log; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.communication_log (
    comm_id integer NOT NULL,
    cv_id integer NOT NULL,
    req_id integer,
    channel character varying(20) DEFAULT 'EMAIL'::character varying NOT NULL,
    recipient character varying(150) NOT NULL,
    subject character varying(255),
    body text,
    status character varying(20) DEFAULT 'SENT'::character varying NOT NULL,
    error_message text,
    sent_by integer,
    sent_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: communication_log_comm_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.communication_log ALTER COLUMN comm_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.communication_log_comm_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: cv_document; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.cv_document (
    document_id integer NOT NULL,
    cv_id integer NOT NULL,
    file_name character varying(255) NOT NULL,
    stored_file_name character varying(255) NOT NULL,
    file_path text NOT NULL,
    file_type character varying(20),
    file_size bigint,
    active_version boolean DEFAULT true NOT NULL,
    upload_date timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    uploaded_by integer
);


--
-- Name: cv_document_document_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.cv_document ALTER COLUMN document_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.cv_document_document_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: domain_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.domain_master (
    domain_id integer NOT NULL,
    domain_name character varying(60) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone,
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: domain_master_domain_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

CREATE SEQUENCE ats.domain_master_domain_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: domain_master_domain_id_seq; Type: SEQUENCE OWNED BY; Schema: ats; Owner: -
--

ALTER SEQUENCE ats.domain_master_domain_id_seq OWNED BY ats.domain_master.domain_id;


--
-- Name: email_template_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.email_template_master (
    template_id smallint NOT NULL,
    template_code character varying(40) NOT NULL,
    name character varying(80) NOT NULL,
    subject character varying(255) NOT NULL,
    body text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: email_template_master_template_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.email_template_master ALTER COLUMN template_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.email_template_master_template_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: jd_cv_mapping; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.jd_cv_mapping (
    mapping_id integer NOT NULL,
    req_id integer NOT NULL,
    cv_id integer NOT NULL,
    screening_datetime timestamp(0) without time zone,
    comments text,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by integer,
    updated_on timestamp(0) without time zone,
    rejection_reason_id smallint,
    screening_mode_id smallint,
    application_stage_id smallint,
    joined_date date,
    latest_outcome_id smallint,
    is_closed boolean DEFAULT false NOT NULL,
    closed_on timestamp without time zone,
    closed_by integer
);


--
-- Name: jd_cv_mapping_mapping_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.jd_cv_mapping ALTER COLUMN mapping_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.jd_cv_mapping_mapping_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: location_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.location_master (
    location_id integer NOT NULL,
    city character varying(60) NOT NULL,
    state character varying(60) NOT NULL,
    country character varying(60) DEFAULT 'India'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_on timestamp(0) without time zone,
    updated_by integer
);


--
-- Name: location_master_location_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.location_master ALTER COLUMN location_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.location_master_location_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: notice_period_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.notice_period_master (
    np_id smallint NOT NULL,
    np_name character varying(30) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: notice_period_master_np_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.notice_period_master ALTER COLUMN np_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.notice_period_master_np_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: position_status_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.position_status_master (
    position_status_id smallint NOT NULL,
    status_code character varying(50) NOT NULL,
    status_name character varying(60) NOT NULL,
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone,
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: position_status_master_position_status_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

CREATE SEQUENCE ats.position_status_master_position_status_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: position_status_master_position_status_id_seq; Type: SEQUENCE OWNED BY; Schema: ats; Owner: -
--

ALTER SEQUENCE ats.position_status_master_position_status_id_seq OWNED BY ats.position_status_master.position_status_id;


--
-- Name: priority_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.priority_master (
    priority_id smallint NOT NULL,
    priority_name character varying(30) NOT NULL,
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: priority_master_priority_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.priority_master ALTER COLUMN priority_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.priority_master_priority_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rejection_reason_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.rejection_reason_master (
    reason_id smallint NOT NULL,
    reason_name character varying(80) NOT NULL,
    reason_code character varying(50),
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: rejection_reason_master_reason_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.rejection_reason_master ALTER COLUMN reason_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.rejection_reason_master_reason_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: req_status_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.req_status_master (
    status_id smallint NOT NULL,
    status_name character varying(50) NOT NULL,
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    status_code character varying(50),
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: req_status_master_status_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.req_status_master ALTER COLUMN status_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.req_status_master_status_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: req_type_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.req_type_master (
    req_type_id smallint NOT NULL,
    req_type_code character varying(50) NOT NULL,
    req_type_name character varying(60) NOT NULL,
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: req_type_master_req_type_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.req_type_master ALTER COLUMN req_type_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.req_type_master_req_type_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: requirement_position; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.requirement_position (
    position_id integer NOT NULL,
    req_id integer NOT NULL,
    position_no integer NOT NULL,
    position_status_id smallint,
    filled_by_mapping_id integer,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone,
    updated_by integer,
    updated_on timestamp(0) without time zone,
    status_source character varying(20)
);


--
-- Name: requirement_position_position_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

CREATE SEQUENCE ats.requirement_position_position_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: requirement_position_position_id_seq; Type: SEQUENCE OWNED BY; Schema: ats; Owner: -
--

ALTER SEQUENCE ats.requirement_position_position_id_seq OWNED BY ats.requirement_position.position_id;


--
-- Name: requirement_tracker; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.requirement_tracker (
    req_id integer NOT NULL,
    req_tracker_no character varying(20) NOT NULL,
    client_id integer NOT NULL,
    client_mgr_id integer,
    hiring_mgr_id integer,
    recruiter_id integer,
    req_type_id smallint NOT NULL,
    jd_role_name character varying(120) NOT NULL,
    location_id integer,
    jd_rate_lpa numeric(7,2),
    np_id smallint,
    req_status_id smallint NOT NULL,
    priority_id smallint,
    positions_open smallint DEFAULT 1 NOT NULL,
    positions_filled smallint DEFAULT 0 NOT NULL,
    skill1_id integer,
    skill2_id integer,
    skill3_id integer,
    req_date date NOT NULL,
    assigned_date date,
    target_fill_date date,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_on timestamp(0) without time zone,
    updated_by integer,
    jd_text text,
    comments text,
    is_active boolean DEFAULT true NOT NULL,
    jd_serial_number character varying(20),
    client_req_id character varying(50),
    exp_min numeric(4,1),
    exp_max numeric(4,1),
    recruitment_ended boolean DEFAULT false NOT NULL,
    recruitment_ended_on timestamp without time zone,
    recruitment_ended_by integer,
    CONSTRAINT chk_dates CHECK (((assigned_date IS NULL) OR (assigned_date >= req_date))),
    CONSTRAINT chk_positions CHECK ((positions_filled <= positions_open)),
    CONSTRAINT chk_req_exp_range CHECK (((exp_min IS NULL) OR (exp_max IS NULL) OR (exp_max >= exp_min)))
);


--
-- Name: requirement_tracker_req_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.requirement_tracker ALTER COLUMN req_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.requirement_tracker_req_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: role_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.role_master (
    role_id integer NOT NULL,
    role_code character varying(10) NOT NULL,
    role_name character varying(50) NOT NULL
);


--
-- Name: role_master_role_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.role_master ALTER COLUMN role_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.role_master_role_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: screening; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.screening (
    screening_id bigint NOT NULL,
    mapping_id integer NOT NULL,
    screening_mode_id smallint NOT NULL,
    status character varying(20) DEFAULT 'SCHEDULED'::character varying NOT NULL,
    outcome character varying(30),
    scheduled_at timestamp(0) without time zone,
    interviewer character varying(150),
    notes text,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone,
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: screening_mode_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.screening_mode_master (
    screening_mode_id smallint NOT NULL,
    mode_name character varying(40) NOT NULL,
    mode_code character varying(50),
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: screening_mode_master_screening_mode_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.screening_mode_master ALTER COLUMN screening_mode_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.screening_mode_master_screening_mode_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: screening_screening_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

CREATE SEQUENCE ats.screening_screening_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: screening_screening_id_seq; Type: SEQUENCE OWNED BY; Schema: ats; Owner: -
--

ALTER SEQUENCE ats.screening_screening_id_seq OWNED BY ats.screening.screening_id;


--
-- Name: skill_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.skill_master (
    skill_id integer NOT NULL,
    skill_name character varying(80) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_on timestamp(0) without time zone,
    updated_by integer,
    domain_id integer
);


--
-- Name: skill_master_skill_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.skill_master ALTER COLUMN skill_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.skill_master_skill_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: source_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.source_master (
    source_id smallint NOT NULL,
    source_name character varying(60) NOT NULL,
    source_type character varying(40),
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: source_master_source_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.source_master ALTER COLUMN source_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.source_master_source_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: status_change_history; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.status_change_history (
    history_id integer NOT NULL,
    entity_type character varying(20) NOT NULL,
    entity_id integer NOT NULL,
    previous_status character varying(30),
    new_status character varying(30) NOT NULL,
    reason text,
    change_type character varying(10) DEFAULT 'MANUAL'::character varying NOT NULL,
    changed_by integer,
    changed_on timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: status_change_history_history_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

CREATE SEQUENCE ats.status_change_history_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: status_change_history_history_id_seq; Type: SEQUENCE OWNED BY; Schema: ats; Owner: -
--

ALTER SEQUENCE ats.status_change_history_history_id_seq OWNED BY ats.status_change_history.history_id;


--
-- Name: user_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.user_master (
    user_id integer NOT NULL,
    full_name character varying(100) NOT NULL,
    email character varying(150) NOT NULL,
    mobile character varying(15),
    role_id integer NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    username character varying(50) NOT NULL,
    password_hash text NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_on timestamp(0) without time zone,
    updated_by integer
);


--
-- Name: user_master_user_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.user_master ALTER COLUMN user_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.user_master_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: work_mode_master; Type: TABLE; Schema: ats; Owner: -
--

CREATE TABLE ats.work_mode_master (
    work_mode_id smallint NOT NULL,
    work_mode_code character varying(50) NOT NULL,
    work_mode_name character varying(30) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_on timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by integer,
    updated_on timestamp(0) without time zone
);


--
-- Name: work_mode_master_work_mode_id_seq; Type: SEQUENCE; Schema: ats; Owner: -
--

ALTER TABLE ats.work_mode_master ALTER COLUMN work_mode_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ats.work_mode_master_work_mode_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: activity_log activity_id; Type: DEFAULT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.activity_log ALTER COLUMN activity_id SET DEFAULT nextval('ats.activity_log_activity_id_seq'::regclass);


--
-- Name: application_status_master application_status_id; Type: DEFAULT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.application_status_master ALTER COLUMN application_status_id SET DEFAULT nextval('ats.application_status_master_application_status_id_seq'::regclass);


--
-- Name: candidate_duplicate_review review_id; Type: DEFAULT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_duplicate_review ALTER COLUMN review_id SET DEFAULT nextval('ats.candidate_duplicate_review_review_id_seq'::regclass);


--
-- Name: candidate_profile_audit audit_id; Type: DEFAULT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_profile_audit ALTER COLUMN audit_id SET DEFAULT nextval('ats.candidate_profile_audit_audit_id_seq'::regclass);


--
-- Name: candidate_status_master candidate_status_id; Type: DEFAULT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_status_master ALTER COLUMN candidate_status_id SET DEFAULT nextval('ats.candidate_status_master_candidate_status_id_seq'::regclass);


--
-- Name: domain_master domain_id; Type: DEFAULT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.domain_master ALTER COLUMN domain_id SET DEFAULT nextval('ats.domain_master_domain_id_seq'::regclass);


--
-- Name: position_status_master position_status_id; Type: DEFAULT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.position_status_master ALTER COLUMN position_status_id SET DEFAULT nextval('ats.position_status_master_position_status_id_seq'::regclass);


--
-- Name: requirement_position position_id; Type: DEFAULT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_position ALTER COLUMN position_id SET DEFAULT nextval('ats.requirement_position_position_id_seq'::regclass);


--
-- Name: screening screening_id; Type: DEFAULT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.screening ALTER COLUMN screening_id SET DEFAULT nextval('ats.screening_screening_id_seq'::regclass);


--
-- Name: status_change_history history_id; Type: DEFAULT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.status_change_history ALTER COLUMN history_id SET DEFAULT nextval('ats.status_change_history_history_id_seq'::regclass);


--
-- Name: activity_log activity_log_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.activity_log
    ADD CONSTRAINT activity_log_pkey PRIMARY KEY (activity_id);


--
-- Name: application_status_master application_status_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.application_status_master
    ADD CONSTRAINT application_status_master_pkey PRIMARY KEY (application_status_id);


--
-- Name: application_status_master application_status_master_status_code_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.application_status_master
    ADD CONSTRAINT application_status_master_status_code_key UNIQUE (status_code);


--
-- Name: candidate_duplicate_review candidate_duplicate_review_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_duplicate_review
    ADD CONSTRAINT candidate_duplicate_review_pkey PRIMARY KEY (review_id);


--
-- Name: candidate_interaction candidate_interaction_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_interaction
    ADD CONSTRAINT candidate_interaction_pkey PRIMARY KEY (interaction_id);


--
-- Name: candidate_master candidate_master_cv_serial_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_cv_serial_key UNIQUE (cv_serial);


--
-- Name: candidate_master candidate_master_email_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_email_key UNIQUE (email);


--
-- Name: candidate_master candidate_master_mobile_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_mobile_key UNIQUE (mobile);


--
-- Name: candidate_master candidate_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_pkey PRIMARY KEY (cv_id);


--
-- Name: candidate_profile_audit candidate_profile_audit_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_profile_audit
    ADD CONSTRAINT candidate_profile_audit_pkey PRIMARY KEY (audit_id);


--
-- Name: candidate_skill candidate_skill_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_skill
    ADD CONSTRAINT candidate_skill_pkey PRIMARY KEY (cs_id);


--
-- Name: candidate_status_master candidate_status_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_status_master
    ADD CONSTRAINT candidate_status_master_pkey PRIMARY KEY (candidate_status_id);


--
-- Name: candidate_status_master candidate_status_master_status_code_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_status_master
    ADD CONSTRAINT candidate_status_master_status_code_key UNIQUE (status_code);


--
-- Name: client_manager_master client_manager_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.client_manager_master
    ADD CONSTRAINT client_manager_master_pkey PRIMARY KEY (client_mgr_id);


--
-- Name: client_master client_master_client_code_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.client_master
    ADD CONSTRAINT client_master_client_code_key UNIQUE (client_code);


--
-- Name: client_master client_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.client_master
    ADD CONSTRAINT client_master_pkey PRIMARY KEY (client_id);


--
-- Name: communication_log communication_log_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.communication_log
    ADD CONSTRAINT communication_log_pkey PRIMARY KEY (comm_id);


--
-- Name: cv_document cv_document_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.cv_document
    ADD CONSTRAINT cv_document_pkey PRIMARY KEY (document_id);


--
-- Name: domain_master domain_master_domain_name_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.domain_master
    ADD CONSTRAINT domain_master_domain_name_key UNIQUE (domain_name);


--
-- Name: domain_master domain_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.domain_master
    ADD CONSTRAINT domain_master_pkey PRIMARY KEY (domain_id);


--
-- Name: email_template_master email_template_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.email_template_master
    ADD CONSTRAINT email_template_master_pkey PRIMARY KEY (template_id);


--
-- Name: email_template_master email_template_master_template_code_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.email_template_master
    ADD CONSTRAINT email_template_master_template_code_key UNIQUE (template_code);


--
-- Name: jd_cv_mapping jd_cv_mapping_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.jd_cv_mapping
    ADD CONSTRAINT jd_cv_mapping_pkey PRIMARY KEY (mapping_id);


--
-- Name: location_master location_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.location_master
    ADD CONSTRAINT location_master_pkey PRIMARY KEY (location_id);


--
-- Name: notice_period_master notice_period_master_np_name_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.notice_period_master
    ADD CONSTRAINT notice_period_master_np_name_key UNIQUE (np_name);


--
-- Name: notice_period_master notice_period_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.notice_period_master
    ADD CONSTRAINT notice_period_master_pkey PRIMARY KEY (np_id);


--
-- Name: position_status_master position_status_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.position_status_master
    ADD CONSTRAINT position_status_master_pkey PRIMARY KEY (position_status_id);


--
-- Name: position_status_master position_status_master_status_code_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.position_status_master
    ADD CONSTRAINT position_status_master_status_code_key UNIQUE (status_code);


--
-- Name: priority_master priority_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.priority_master
    ADD CONSTRAINT priority_master_pkey PRIMARY KEY (priority_id);


--
-- Name: priority_master priority_master_priority_name_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.priority_master
    ADD CONSTRAINT priority_master_priority_name_key UNIQUE (priority_name);


--
-- Name: rejection_reason_master rejection_reason_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.rejection_reason_master
    ADD CONSTRAINT rejection_reason_master_pkey PRIMARY KEY (reason_id);


--
-- Name: rejection_reason_master rejection_reason_master_reason_code_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.rejection_reason_master
    ADD CONSTRAINT rejection_reason_master_reason_code_key UNIQUE (reason_code);


--
-- Name: rejection_reason_master rejection_reason_master_reason_name_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.rejection_reason_master
    ADD CONSTRAINT rejection_reason_master_reason_name_key UNIQUE (reason_name);


--
-- Name: req_status_master req_status_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.req_status_master
    ADD CONSTRAINT req_status_master_pkey PRIMARY KEY (status_id);


--
-- Name: req_status_master req_status_master_status_name_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.req_status_master
    ADD CONSTRAINT req_status_master_status_name_key UNIQUE (status_name);


--
-- Name: req_type_master req_type_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.req_type_master
    ADD CONSTRAINT req_type_master_pkey PRIMARY KEY (req_type_id);


--
-- Name: req_type_master req_type_master_req_type_code_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.req_type_master
    ADD CONSTRAINT req_type_master_req_type_code_key UNIQUE (req_type_code);


--
-- Name: requirement_position requirement_position_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_position
    ADD CONSTRAINT requirement_position_pkey PRIMARY KEY (position_id);


--
-- Name: requirement_position requirement_position_req_id_position_no_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_position
    ADD CONSTRAINT requirement_position_req_id_position_no_key UNIQUE (req_id, position_no);


--
-- Name: requirement_tracker requirement_tracker_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_pkey PRIMARY KEY (req_id);


--
-- Name: requirement_tracker requirement_tracker_req_tracker_no_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_req_tracker_no_key UNIQUE (req_tracker_no);


--
-- Name: role_master role_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.role_master
    ADD CONSTRAINT role_master_pkey PRIMARY KEY (role_id);


--
-- Name: role_master role_master_role_code_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.role_master
    ADD CONSTRAINT role_master_role_code_key UNIQUE (role_code);


--
-- Name: role_master role_master_role_name_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.role_master
    ADD CONSTRAINT role_master_role_name_key UNIQUE (role_name);


--
-- Name: screening_mode_master screening_mode_master_mode_code_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.screening_mode_master
    ADD CONSTRAINT screening_mode_master_mode_code_key UNIQUE (mode_code);


--
-- Name: screening_mode_master screening_mode_master_mode_name_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.screening_mode_master
    ADD CONSTRAINT screening_mode_master_mode_name_key UNIQUE (mode_name);


--
-- Name: screening_mode_master screening_mode_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.screening_mode_master
    ADD CONSTRAINT screening_mode_master_pkey PRIMARY KEY (screening_mode_id);


--
-- Name: screening screening_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.screening
    ADD CONSTRAINT screening_pkey PRIMARY KEY (screening_id);


--
-- Name: skill_master skill_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.skill_master
    ADD CONSTRAINT skill_master_pkey PRIMARY KEY (skill_id);


--
-- Name: skill_master skill_master_skill_name_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.skill_master
    ADD CONSTRAINT skill_master_skill_name_key UNIQUE (skill_name);


--
-- Name: source_master source_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.source_master
    ADD CONSTRAINT source_master_pkey PRIMARY KEY (source_id);


--
-- Name: source_master source_master_source_name_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.source_master
    ADD CONSTRAINT source_master_source_name_key UNIQUE (source_name);


--
-- Name: status_change_history status_change_history_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.status_change_history
    ADD CONSTRAINT status_change_history_pkey PRIMARY KEY (history_id);


--
-- Name: candidate_skill uq_candidate_skill; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_skill
    ADD CONSTRAINT uq_candidate_skill UNIQUE (cv_id, skill_id);


--
-- Name: client_manager_master uq_client_mgr_email; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.client_manager_master
    ADD CONSTRAINT uq_client_mgr_email UNIQUE (client_id, email);


--
-- Name: jd_cv_mapping uq_jd_cv; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.jd_cv_mapping
    ADD CONSTRAINT uq_jd_cv UNIQUE (req_id, cv_id);


--
-- Name: location_master uq_location; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.location_master
    ADD CONSTRAINT uq_location UNIQUE (city, state, country);


--
-- Name: user_master user_master_email_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.user_master
    ADD CONSTRAINT user_master_email_key UNIQUE (email);


--
-- Name: user_master user_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.user_master
    ADD CONSTRAINT user_master_pkey PRIMARY KEY (user_id);


--
-- Name: user_master user_master_username_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.user_master
    ADD CONSTRAINT user_master_username_key UNIQUE (username);


--
-- Name: work_mode_master work_mode_master_pkey; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.work_mode_master
    ADD CONSTRAINT work_mode_master_pkey PRIMARY KEY (work_mode_id);


--
-- Name: work_mode_master work_mode_master_work_mode_code_key; Type: CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.work_mode_master
    ADD CONSTRAINT work_mode_master_work_mode_code_key UNIQUE (work_mode_code);


--
-- Name: idx_activity_log_created; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_activity_log_created ON ats.activity_log USING btree (created_on DESC);


--
-- Name: idx_candskill_skill; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_candskill_skill ON ats.candidate_skill USING btree (skill_id);


--
-- Name: idx_comm_cv; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_comm_cv ON ats.communication_log USING btree (cv_id);


--
-- Name: idx_cvdoc_cv; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_cvdoc_cv ON ats.cv_document USING btree (cv_id);


--
-- Name: idx_dupreview_existing; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_dupreview_existing ON ats.candidate_duplicate_review USING btree (existing_cv_id);


--
-- Name: idx_dupreview_status; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_dupreview_status ON ats.candidate_duplicate_review USING btree (review_status);


--
-- Name: idx_interaction_cv; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_interaction_cv ON ats.candidate_interaction USING btree (cv_id);


--
-- Name: idx_jdcv_cv; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_jdcv_cv ON ats.jd_cv_mapping USING btree (cv_id);


--
-- Name: idx_jdcv_reason; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_jdcv_reason ON ats.jd_cv_mapping USING btree (rejection_reason_id);


--
-- Name: idx_jdcv_req; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_jdcv_req ON ats.jd_cv_mapping USING btree (req_id);


--
-- Name: idx_profile_audit_cv; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_profile_audit_cv ON ats.candidate_profile_audit USING btree (cv_id, changed_on DESC);


--
-- Name: idx_requirement_position_req; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_requirement_position_req ON ats.requirement_position USING btree (req_id);


--
-- Name: idx_screening_mapping; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_screening_mapping ON ats.screening USING btree (mapping_id);


--
-- Name: idx_status_history_entity; Type: INDEX; Schema: ats; Owner: -
--

CREATE INDEX idx_status_history_entity ON ats.status_change_history USING btree (entity_type, entity_id, changed_on DESC);


--
-- Name: uq_req_jd_serial; Type: INDEX; Schema: ats; Owner: -
--

CREATE UNIQUE INDEX uq_req_jd_serial ON ats.requirement_tracker USING btree (jd_serial_number);


--
-- Name: uq_req_status_code; Type: INDEX; Schema: ats; Owner: -
--

CREATE UNIQUE INDEX uq_req_status_code ON ats.req_status_master USING btree (status_code);


--
-- Name: activity_log activity_log_actor_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.activity_log
    ADD CONSTRAINT activity_log_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES ats.user_master(user_id);


--
-- Name: activity_log activity_log_cv_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.activity_log
    ADD CONSTRAINT activity_log_cv_id_fkey FOREIGN KEY (cv_id) REFERENCES ats.candidate_master(cv_id);


--
-- Name: activity_log activity_log_req_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.activity_log
    ADD CONSTRAINT activity_log_req_id_fkey FOREIGN KEY (req_id) REFERENCES ats.requirement_tracker(req_id);


--
-- Name: application_status_master application_status_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.application_status_master
    ADD CONSTRAINT application_status_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: application_status_master application_status_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.application_status_master
    ADD CONSTRAINT application_status_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: candidate_duplicate_review candidate_duplicate_review_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_duplicate_review
    ADD CONSTRAINT candidate_duplicate_review_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: candidate_duplicate_review candidate_duplicate_review_existing_cv_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_duplicate_review
    ADD CONSTRAINT candidate_duplicate_review_existing_cv_id_fkey FOREIGN KEY (existing_cv_id) REFERENCES ats.candidate_master(cv_id);


--
-- Name: candidate_duplicate_review candidate_duplicate_review_resolved_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_duplicate_review
    ADD CONSTRAINT candidate_duplicate_review_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES ats.user_master(user_id);


--
-- Name: candidate_interaction candidate_interaction_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_interaction
    ADD CONSTRAINT candidate_interaction_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: candidate_interaction candidate_interaction_cv_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_interaction
    ADD CONSTRAINT candidate_interaction_cv_id_fkey FOREIGN KEY (cv_id) REFERENCES ats.candidate_master(cv_id) ON DELETE CASCADE;


--
-- Name: candidate_interaction candidate_interaction_req_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_interaction
    ADD CONSTRAINT candidate_interaction_req_id_fkey FOREIGN KEY (req_id) REFERENCES ats.requirement_tracker(req_id);


--
-- Name: candidate_master candidate_master_candidate_status_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_candidate_status_id_fkey FOREIGN KEY (candidate_status_id) REFERENCES ats.candidate_status_master(candidate_status_id);


--
-- Name: candidate_master candidate_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: candidate_master candidate_master_current_location_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_current_location_id_fkey FOREIGN KEY (current_location_id) REFERENCES ats.location_master(location_id);


--
-- Name: candidate_master candidate_master_notice_period_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_notice_period_id_fkey FOREIGN KEY (notice_period_id) REFERENCES ats.notice_period_master(np_id);


--
-- Name: candidate_master candidate_master_preferred_location_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_preferred_location_id_fkey FOREIGN KEY (preferred_location_id) REFERENCES ats.location_master(location_id);


--
-- Name: candidate_master candidate_master_profile_verified_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_profile_verified_by_fkey FOREIGN KEY (profile_verified_by) REFERENCES ats.user_master(user_id);


--
-- Name: candidate_master candidate_master_source_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_source_id_fkey FOREIGN KEY (source_id) REFERENCES ats.source_master(source_id);


--
-- Name: candidate_master candidate_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: candidate_master candidate_master_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES ats.user_master(user_id);


--
-- Name: candidate_master candidate_master_work_mode_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_work_mode_id_fkey FOREIGN KEY (work_mode_id) REFERENCES ats.work_mode_master(work_mode_id);


--
-- Name: candidate_profile_audit candidate_profile_audit_changed_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_profile_audit
    ADD CONSTRAINT candidate_profile_audit_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES ats.user_master(user_id);


--
-- Name: candidate_profile_audit candidate_profile_audit_cv_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_profile_audit
    ADD CONSTRAINT candidate_profile_audit_cv_id_fkey FOREIGN KEY (cv_id) REFERENCES ats.candidate_master(cv_id);


--
-- Name: candidate_skill candidate_skill_cv_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_skill
    ADD CONSTRAINT candidate_skill_cv_id_fkey FOREIGN KEY (cv_id) REFERENCES ats.candidate_master(cv_id) ON DELETE CASCADE;


--
-- Name: candidate_skill candidate_skill_skill_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_skill
    ADD CONSTRAINT candidate_skill_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES ats.skill_master(skill_id);


--
-- Name: candidate_status_master candidate_status_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_status_master
    ADD CONSTRAINT candidate_status_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: candidate_status_master candidate_status_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_status_master
    ADD CONSTRAINT candidate_status_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: client_manager_master client_manager_master_client_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.client_manager_master
    ADD CONSTRAINT client_manager_master_client_id_fkey FOREIGN KEY (client_id) REFERENCES ats.client_master(client_id);


--
-- Name: client_manager_master client_manager_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.client_manager_master
    ADD CONSTRAINT client_manager_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: client_manager_master client_manager_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.client_manager_master
    ADD CONSTRAINT client_manager_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: client_master client_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.client_master
    ADD CONSTRAINT client_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: client_master client_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.client_master
    ADD CONSTRAINT client_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: communication_log communication_log_cv_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.communication_log
    ADD CONSTRAINT communication_log_cv_id_fkey FOREIGN KEY (cv_id) REFERENCES ats.candidate_master(cv_id) ON DELETE CASCADE;


--
-- Name: communication_log communication_log_req_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.communication_log
    ADD CONSTRAINT communication_log_req_id_fkey FOREIGN KEY (req_id) REFERENCES ats.requirement_tracker(req_id);


--
-- Name: communication_log communication_log_sent_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.communication_log
    ADD CONSTRAINT communication_log_sent_by_fkey FOREIGN KEY (sent_by) REFERENCES ats.user_master(user_id);


--
-- Name: cv_document cv_document_cv_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.cv_document
    ADD CONSTRAINT cv_document_cv_id_fkey FOREIGN KEY (cv_id) REFERENCES ats.candidate_master(cv_id) ON DELETE CASCADE;


--
-- Name: cv_document cv_document_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.cv_document
    ADD CONSTRAINT cv_document_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES ats.user_master(user_id);


--
-- Name: domain_master domain_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.domain_master
    ADD CONSTRAINT domain_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: domain_master domain_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.domain_master
    ADD CONSTRAINT domain_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: email_template_master email_template_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.email_template_master
    ADD CONSTRAINT email_template_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: email_template_master email_template_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.email_template_master
    ADD CONSTRAINT email_template_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: candidate_master fk_candidate_duplicate_of; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT fk_candidate_duplicate_of FOREIGN KEY (duplicate_of_cv_id) REFERENCES ats.candidate_master(cv_id);


--
-- Name: jd_cv_mapping fk_jdcv_rejection_reason; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.jd_cv_mapping
    ADD CONSTRAINT fk_jdcv_rejection_reason FOREIGN KEY (rejection_reason_id) REFERENCES ats.rejection_reason_master(reason_id);


--
-- Name: jd_cv_mapping fk_jdcv_screening_mode; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.jd_cv_mapping
    ADD CONSTRAINT fk_jdcv_screening_mode FOREIGN KEY (screening_mode_id) REFERENCES ats.screening_mode_master(screening_mode_id);


--
-- Name: jd_cv_mapping jd_cv_mapping_application_status_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.jd_cv_mapping
    ADD CONSTRAINT jd_cv_mapping_application_status_id_fkey FOREIGN KEY (application_stage_id) REFERENCES ats.application_status_master(application_status_id);


--
-- Name: jd_cv_mapping jd_cv_mapping_closed_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.jd_cv_mapping
    ADD CONSTRAINT jd_cv_mapping_closed_by_fkey FOREIGN KEY (closed_by) REFERENCES ats.user_master(user_id);


--
-- Name: jd_cv_mapping jd_cv_mapping_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.jd_cv_mapping
    ADD CONSTRAINT jd_cv_mapping_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: jd_cv_mapping jd_cv_mapping_cv_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.jd_cv_mapping
    ADD CONSTRAINT jd_cv_mapping_cv_id_fkey FOREIGN KEY (cv_id) REFERENCES ats.candidate_master(cv_id);


--
-- Name: jd_cv_mapping jd_cv_mapping_latest_outcome_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.jd_cv_mapping
    ADD CONSTRAINT jd_cv_mapping_latest_outcome_id_fkey FOREIGN KEY (latest_outcome_id) REFERENCES ats.application_status_master(application_status_id);


--
-- Name: jd_cv_mapping jd_cv_mapping_req_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.jd_cv_mapping
    ADD CONSTRAINT jd_cv_mapping_req_id_fkey FOREIGN KEY (req_id) REFERENCES ats.requirement_tracker(req_id);


--
-- Name: jd_cv_mapping jd_cv_mapping_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.jd_cv_mapping
    ADD CONSTRAINT jd_cv_mapping_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: location_master location_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.location_master
    ADD CONSTRAINT location_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: location_master location_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.location_master
    ADD CONSTRAINT location_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: notice_period_master notice_period_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.notice_period_master
    ADD CONSTRAINT notice_period_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: notice_period_master notice_period_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.notice_period_master
    ADD CONSTRAINT notice_period_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: position_status_master position_status_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.position_status_master
    ADD CONSTRAINT position_status_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: position_status_master position_status_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.position_status_master
    ADD CONSTRAINT position_status_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: priority_master priority_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.priority_master
    ADD CONSTRAINT priority_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: priority_master priority_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.priority_master
    ADD CONSTRAINT priority_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: rejection_reason_master rejection_reason_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.rejection_reason_master
    ADD CONSTRAINT rejection_reason_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: rejection_reason_master rejection_reason_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.rejection_reason_master
    ADD CONSTRAINT rejection_reason_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: req_status_master req_status_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.req_status_master
    ADD CONSTRAINT req_status_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: req_status_master req_status_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.req_status_master
    ADD CONSTRAINT req_status_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: req_type_master req_type_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.req_type_master
    ADD CONSTRAINT req_type_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: req_type_master req_type_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.req_type_master
    ADD CONSTRAINT req_type_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: requirement_position requirement_position_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_position
    ADD CONSTRAINT requirement_position_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: requirement_position requirement_position_filled_by_mapping_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_position
    ADD CONSTRAINT requirement_position_filled_by_mapping_id_fkey FOREIGN KEY (filled_by_mapping_id) REFERENCES ats.jd_cv_mapping(mapping_id);


--
-- Name: requirement_position requirement_position_position_status_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_position
    ADD CONSTRAINT requirement_position_position_status_id_fkey FOREIGN KEY (position_status_id) REFERENCES ats.position_status_master(position_status_id);


--
-- Name: requirement_position requirement_position_req_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_position
    ADD CONSTRAINT requirement_position_req_id_fkey FOREIGN KEY (req_id) REFERENCES ats.requirement_tracker(req_id);


--
-- Name: requirement_position requirement_position_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_position
    ADD CONSTRAINT requirement_position_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: requirement_tracker requirement_tracker_client_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_client_id_fkey FOREIGN KEY (client_id) REFERENCES ats.client_master(client_id);


--
-- Name: requirement_tracker requirement_tracker_client_mgr_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_client_mgr_id_fkey FOREIGN KEY (client_mgr_id) REFERENCES ats.client_manager_master(client_mgr_id);


--
-- Name: requirement_tracker requirement_tracker_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: requirement_tracker requirement_tracker_hiring_mgr_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_hiring_mgr_id_fkey FOREIGN KEY (hiring_mgr_id) REFERENCES ats.user_master(user_id);


--
-- Name: requirement_tracker requirement_tracker_location_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_location_id_fkey FOREIGN KEY (location_id) REFERENCES ats.location_master(location_id);


--
-- Name: requirement_tracker requirement_tracker_np_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_np_id_fkey FOREIGN KEY (np_id) REFERENCES ats.notice_period_master(np_id);


--
-- Name: requirement_tracker requirement_tracker_priority_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_priority_id_fkey FOREIGN KEY (priority_id) REFERENCES ats.priority_master(priority_id);


--
-- Name: requirement_tracker requirement_tracker_recruiter_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_recruiter_id_fkey FOREIGN KEY (recruiter_id) REFERENCES ats.user_master(user_id);


--
-- Name: requirement_tracker requirement_tracker_req_status_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_req_status_id_fkey FOREIGN KEY (req_status_id) REFERENCES ats.req_status_master(status_id);


--
-- Name: requirement_tracker requirement_tracker_req_type_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_req_type_id_fkey FOREIGN KEY (req_type_id) REFERENCES ats.req_type_master(req_type_id);


--
-- Name: requirement_tracker requirement_tracker_skill1_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_skill1_id_fkey FOREIGN KEY (skill1_id) REFERENCES ats.skill_master(skill_id);


--
-- Name: requirement_tracker requirement_tracker_skill2_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_skill2_id_fkey FOREIGN KEY (skill2_id) REFERENCES ats.skill_master(skill_id);


--
-- Name: requirement_tracker requirement_tracker_skill3_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_skill3_id_fkey FOREIGN KEY (skill3_id) REFERENCES ats.skill_master(skill_id);


--
-- Name: requirement_tracker requirement_tracker_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.requirement_tracker
    ADD CONSTRAINT requirement_tracker_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: screening screening_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.screening
    ADD CONSTRAINT screening_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: screening screening_mapping_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.screening
    ADD CONSTRAINT screening_mapping_id_fkey FOREIGN KEY (mapping_id) REFERENCES ats.jd_cv_mapping(mapping_id);


--
-- Name: screening_mode_master screening_mode_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.screening_mode_master
    ADD CONSTRAINT screening_mode_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: screening_mode_master screening_mode_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.screening_mode_master
    ADD CONSTRAINT screening_mode_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: screening screening_screening_mode_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.screening
    ADD CONSTRAINT screening_screening_mode_id_fkey FOREIGN KEY (screening_mode_id) REFERENCES ats.screening_mode_master(screening_mode_id);


--
-- Name: screening screening_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.screening
    ADD CONSTRAINT screening_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: skill_master skill_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.skill_master
    ADD CONSTRAINT skill_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: skill_master skill_master_domain_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.skill_master
    ADD CONSTRAINT skill_master_domain_id_fkey FOREIGN KEY (domain_id) REFERENCES ats.domain_master(domain_id);


--
-- Name: skill_master skill_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.skill_master
    ADD CONSTRAINT skill_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: source_master source_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.source_master
    ADD CONSTRAINT source_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: source_master source_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.source_master
    ADD CONSTRAINT source_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: status_change_history status_change_history_changed_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.status_change_history
    ADD CONSTRAINT status_change_history_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES ats.user_master(user_id);


--
-- Name: user_master user_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.user_master
    ADD CONSTRAINT user_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: user_master user_master_role_id_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.user_master
    ADD CONSTRAINT user_master_role_id_fkey FOREIGN KEY (role_id) REFERENCES ats.role_master(role_id);


--
-- Name: user_master user_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.user_master
    ADD CONSTRAINT user_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- Name: work_mode_master work_mode_master_created_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.work_mode_master
    ADD CONSTRAINT work_mode_master_created_by_fkey FOREIGN KEY (created_by) REFERENCES ats.user_master(user_id);


--
-- Name: work_mode_master work_mode_master_updated_by_fkey; Type: FK CONSTRAINT; Schema: ats; Owner: -
--

ALTER TABLE ONLY ats.work_mode_master
    ADD CONSTRAINT work_mode_master_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES ats.user_master(user_id);


--
-- PostgreSQL database dump complete
--


--
-- Bulk import batch tracking (migration 0025). Appended block: table + FK
-- constraints + indexes (valid on replay — all referenced tables exist above).
--

CREATE TABLE ats.bulk_import_batch (
    batch_id integer GENERATED BY DEFAULT AS IDENTITY NOT NULL,
    batch_uid character varying(32),
    uploaded_by integer,
    file_name character varying(255),
    file_hash character varying(64),
    source_id smallint,
    requirement_id integer,
    sheet_name character varying(100),
    header_row smallint,
    total_rows integer DEFAULT 0 NOT NULL,
    created_count integer DEFAULT 0 NOT NULL,
    updated_count integer DEFAULT 0 NOT NULL,
    duplicate_count integer DEFAULT 0 NOT NULL,
    skipped_count integer DEFAULT 0 NOT NULL,
    status character varying(12) DEFAULT 'PENDING'::character varying NOT NULL,
    row_report jsonb,
    error_message text,
    created_on timestamp without time zone DEFAULT now() NOT NULL,
    completed_on timestamp without time zone,
    CONSTRAINT bulk_import_batch_pkey PRIMARY KEY (batch_id)
);

ALTER TABLE ONLY ats.bulk_import_batch
    ADD CONSTRAINT bulk_import_batch_uploaded_by_fk FOREIGN KEY (uploaded_by) REFERENCES ats.user_master(user_id);
ALTER TABLE ONLY ats.bulk_import_batch
    ADD CONSTRAINT bulk_import_batch_source_fk FOREIGN KEY (source_id) REFERENCES ats.source_master(source_id);
ALTER TABLE ONLY ats.bulk_import_batch
    ADD CONSTRAINT bulk_import_batch_requirement_fk FOREIGN KEY (requirement_id) REFERENCES ats.requirement_tracker(req_id);
ALTER TABLE ONLY ats.candidate_master
    ADD CONSTRAINT candidate_master_import_batch_fk FOREIGN KEY (import_batch_id) REFERENCES ats.bulk_import_batch(batch_id);

CREATE INDEX ix_bulk_import_batch_uploaded_by ON ats.bulk_import_batch (uploaded_by);
CREATE INDEX ix_candidate_master_import_batch ON ats.candidate_master (import_batch_id);


--
-- Name: candidate_requirement_review; Type: TABLE; Schema: ats; Owner: -
-- Pre-pipeline "candidate under review for a requirement" (the Review Pool).
-- Separate from jd_cv_mapping (which means the candidate entered the pipeline).
-- (Self-contained block; all referenced tables are created above.)
--
CREATE TABLE ats.candidate_requirement_review (
    review_id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
    cv_id integer NOT NULL,
    req_id integer NOT NULL,
    status character varying(20) DEFAULT 'ACTIVE'::character varying NOT NULL,
    resolution character varying(30),
    tagged_by integer,
    tagged_on timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    resolved_by integer,
    resolved_on timestamp without time zone,
    created_on timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_on timestamp without time zone
);

ALTER TABLE ONLY ats.candidate_requirement_review
    ADD CONSTRAINT candidate_requirement_review_pkey PRIMARY KEY (review_id);
ALTER TABLE ONLY ats.candidate_requirement_review
    ADD CONSTRAINT uq_candidate_requirement_review UNIQUE (cv_id, req_id);
ALTER TABLE ONLY ats.candidate_requirement_review
    ADD CONSTRAINT candidate_requirement_review_cv_id_fkey FOREIGN KEY (cv_id) REFERENCES ats.candidate_master(cv_id) ON DELETE CASCADE;
ALTER TABLE ONLY ats.candidate_requirement_review
    ADD CONSTRAINT candidate_requirement_review_req_id_fkey FOREIGN KEY (req_id) REFERENCES ats.requirement_tracker(req_id);
ALTER TABLE ONLY ats.candidate_requirement_review
    ADD CONSTRAINT candidate_requirement_review_tagged_by_fkey FOREIGN KEY (tagged_by) REFERENCES ats.user_master(user_id);
ALTER TABLE ONLY ats.candidate_requirement_review
    ADD CONSTRAINT candidate_requirement_review_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES ats.user_master(user_id);

CREATE INDEX ix_crr_req_status ON ats.candidate_requirement_review (req_id, status);
CREATE INDEX ix_crr_cv_status ON ats.candidate_requirement_review (cv_id, status);
