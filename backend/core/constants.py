"""
Central place for the stable codes used across the app.

WHY: business logic constantly asks questions like "is this CV shortlisted?"
or "is this user a recruiter?". Hardcoding the literal strings/ids in many
places is fragile and error-prone. We reference these constants instead, and
they map to the `status_code` / `role_code` columns in the database.
"""


class Roles:
    """Maps to ats.role_master.role_code"""
    ADMIN = "ADM"
    RECRUITER = "REC"
    HIRING_MANAGER = "HM"


class ReqStatus:
    """Maps to ats.req_status_master.status_code (requirement lifecycle, §5).

    NOTE: there is no 'Expired' status. Expiry is a DERIVED, read-only overlay
    (Target Fill Date passed while the requirement is non-terminal) — see
    requirements.services.requirement_is_expired — never a stored status."""
    NEW = "NEW"
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    HOLD = "HOLD"
    CANCELLED = "CANCELLED"
    # Auto-derived, WORKABLE while recruiting. A partially-filled requirement that
    # has EXPIRED can have recruitment explicitly ended by the HM (see
    # pipeline.services.end_recruitment) — that closes the remaining applications
    # but leaves the requirement in PARTIAL_FILLED (no separate terminal status).
    PARTIAL_FILLED = "PARTIAL_FILLED"
    CLOSE_FILLED = "CLOSE_FILLED"   # displayed "Filled"
    CLOSE_LOST = "CLOSE_LOST"       # displayed "Closed Lost" — terminal, no reopen

    # Terminal states the rollup / expiry overlay must never disturb.
    TERMINAL = (CLOSE_FILLED, CANCELLED, CLOSE_LOST)
    # Irreversible closures that free remaining active applications back to the
    # Talent Pool. CANCELLED is reopenable, so its pipeline is preserved and it is
    # intentionally absent. The terminal-partial case is handled by end_recruitment
    # WITHOUT a status change (requirement stays PARTIAL_FILLED + Expired).
    APPLICATION_CLOSING = (CLOSE_FILLED, CLOSE_LOST)
    # States a recruiter may actively work (pipeline actions allowed).
    WORKABLE = (NEW, ASSIGNED, OPEN, PARTIAL_FILLED)


class CandidateStatus:
    """Maps to ats.candidate_status_master.status_code — global candidate
    disposition (post-redesign; see docs/POSITION_REDESIGN.md)."""
    NEW_CV = "NEW_CV"
    SAVED = "SAVED"  # displayed as "Talent Pool" in the UI (code kept as SAVED)
    REJECT_HOLD = "REJECT_HOLD"  # system: 2 active rejections → 6-month cool-off
    JOINED = "JOINED"            # system: candidate placed (2-year retention)
    FAKE = "FAKE"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    BLACKLISTED = "BLACKLISTED"

    # Statuses a recruiter may set MANUALLY. Everything else is SYSTEM-managed:
    # NEW_CV (creation), POSSIBLE_DUPLICATE (detection), and the lifecycle
    # statuses SAVED (Talent Pool) / REJECT_HOLD / JOINED (driven by application
    # outcomes + the daily maintenance job) are never set by hand.
    MANUAL_CHANGEABLE = (FAKE, BLACKLISTED)

    # Candidate Database visibility. The default recruiter/admin view hides these
    # (a Status filter with "All" overrides). Hiring Managers ONLY ever see the
    # two "workable" statuses, enforced on the backend.
    DB_DEFAULT_HIDDEN = (REJECT_HOLD, JOINED, FAKE, BLACKLISTED)
    HM_VISIBLE = (NEW_CV, SAVED)


class ApplicationStatus:
    """Maps to ats.application_status_master.status_code. Rows are classified by
    `kind`: STAGE (the candidate's position in the flow) vs OUTCOME (a recorded
    disposition). jd_cv_mapping.application_stage holds a STAGE; latest_outcome
    holds an OUTCOME. The stage×outcome machine lives in pipeline.services."""
    # --- Pipeline STAGES (progression only) ---
    NEW = "NEW"
    SHORTLISTED = "SHORTLISTED"
    JD_EMAIL_SENT = "JD_EMAIL_SENT"
    SCREENING_SCHEDULED = "SCREENING_SCHEDULED"
    OK_TO_PROCEED = "OK_TO_PROCEED"
    OFFERED = "OFFERED"                  # displayed as "Offer Released"
    AWAITING_JOINING = "AWAITING_JOINING"

    STAGES = (NEW, SHORTLISTED, JD_EMAIL_SENT, SCREENING_SCHEDULED,
              OK_TO_PROCEED, OFFERED, AWAITING_JOINING)

    # --- OUTCOMES (recorded dispositions; advance a stage or close the app) ---
    PASSED = "PASSED"                    # screening passed → advances to OK to Proceed
    OFFER_ACCEPTED = "OFFER_ACCEPTED"    # advances to Awaiting Joining
    NO_RESPONSE = "NO_RESPONSE"
    DROPPED = "DROPPED"
    NOT_SUITABLE = "NOT_SUITABLE"
    REJECTED = "REJECTED"
    OFFER_DECLINED = "OFFER_DECLINED"
    WITHDRAWN = "WITHDRAWN"
    JOINED = "JOINED"
    FAKE = "FAKE"
    BLACKLISTED = "BLACKLISTED"

    # System-generated closing outcomes, recorded when a REQUIREMENT reaches an
    # irreversible terminal state and its remaining active applications are
    # auto-closed. Non-rejection (candidates return to the Talent Pool).
    REQ_CLOSE_FILLED = "REQ_CLOSE_FILLED"              # requirement fully filled
    REQ_POSITIONS_WITHDRAWN = "REQ_POSITIONS_WITHDRAWN"  # partially filled, remaining withdrawn
    REQ_CLOSE_LOST = "REQ_CLOSE_LOST"                 # requirement closed lost

    REQ_CLOSURE_OUTCOMES = (REQ_CLOSE_FILLED, REQ_POSITIONS_WITHDRAWN, REQ_CLOSE_LOST)

    # Closing outcomes that are "non-hired" and eligible for the optional
    # "Move to Talent Pool?" recruiter prompt (Joined/Fake/Blacklist excluded).
    TALENT_POOL_PROMPT_OUTCOMES = (NO_RESPONSE, DROPPED, NOT_SUITABLE, REJECTED,
                                   OFFER_DECLINED, WITHDRAWN)


class PositionStatus:
    """Maps to ats.position_status_master.status_code — per-seat lifecycle.
    A seat a candidate joins into becomes FILLED (the mentor's terminology)."""
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"   # legacy master row, not used by the workflow
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    HOLD = "HOLD"
    # System-managed only: set when the requirement is Held/Cancelled, cleared
    # (back to Open) when it resumes. Never a manual choice.
    INACTIVE = "INACTIVE"


class PositionSource:
    """requirement_position.status_source — WHY a seat is in its current status.
    Only auto-sourced seats are automatically reopened when a requirement
    resumes/reopens; MANUAL Hold/Cancel are left for the HM to reopen by hand."""
    MANUAL = "MANUAL"
    AUTO_REQ_HOLD = "AUTO_REQ_HOLD"
    AUTO_REQ_CANCEL = "AUTO_REQ_CANCEL"
    # Seat withdrawn by a permanent End-Recruitment decision. Recorded for seat
    # history/reporting; deliberately NOT in AUTO, so a Cancel→reopen never
    # resurrects it (recruitment_ended is permanent).
    AUTO_END_RECRUITMENT = "AUTO_END_RECRUITMENT"
    AUTO = (AUTO_REQ_HOLD, AUTO_REQ_CANCEL)


class ChangeType:
    """status_change_history.change_type — was the change made by a human or the
    system cascade?"""
    MANUAL = "MANUAL"
    AUTO = "AUTO"


class AuditEntity:
    """status_change_history.entity_type."""
    REQUIREMENT = "REQUIREMENT"
    POSITION = "POSITION"
    APPLICATION = "APPLICATION"


class ScreeningMode:
    """screening_mode_master.mode_code — the built-in modes the sequential rules
    reference. New modes can be added via the master with no code change (they
    simply have no special ordering constraint)."""
    TELEPHONIC = "TELEPHONIC"
    VIDEO = "VIDEO"


class ScreeningStatus:
    """screening.status — a round's lifecycle."""
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"


class ScreeningOutcome:
    """screening.outcome — recorded when a round is completed."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    NO_SHOW = "NO_SHOW"
    CANCELLED = "CANCELLED"
    RESCHEDULE_REQUIRED = "RESCHEDULE_REQUIRED"

    ALL = (PASSED, FAILED, NO_SHOW, CANCELLED, RESCHEDULE_REQUIRED)


class InteractionType:
    """Maps to ats.candidate_interaction.interaction_type (§10)."""
    CALL_NOTE = "CALL_NOTE"
    SCREENING_FEEDBACK = "SCREENING_FEEDBACK"
    STATUS_CHANGE = "STATUS_CHANGE"
    DUPLICATE_RESOLUTION = "DUPLICATE_RESOLUTION"
    GENERAL = "GENERAL"


class DuplicateReview:
    """candidate_duplicate_review.review_status / .resolution codes. A SEPARATE
    process from candidate_status — never sets 'Possible Duplicate' on a candidate."""
    # review_status
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    # resolution (how an admin closed it).
    UPDATED = "UPDATED"        # applied the chosen name/mobile/email to the existing record
    KEPT_SEPARATE = "KEPT_SEPARATE"  # dismissed — existing record kept as-is ("Ignored")
    # Legacy values (kept for historical rows + backward-compat); the UI now writes
    # UPDATED for both "same person / adopt submitted" and "fix existing typo".
    MERGED = "MERGED"
    CORRECTED = "CORRECTED"
    RESOLUTIONS = (UPDATED, KEPT_SEPARATE, MERGED, CORRECTED)


class ReviewStatus:
    """candidate_requirement_review.status — the PRE-PIPELINE review association
    ("candidate under review for a requirement"). Completely separate from
    jd_cv_mapping, which means the candidate has ENTERED the pipeline (Shortlist)."""
    ACTIVE = "ACTIVE"       # under review for the requirement (shows in its Review Pool)
    RESOLVED = "RESOLVED"   # a decision was made / untagged / requirement closed


class ReviewResolution:
    """candidate_requirement_review.resolution — how an ACTIVE review ended."""
    SHORTLISTED = "SHORTLISTED"    # → entered the pipeline (jd_cv_mapping created)
    NOT_SUITABLE = "NOT_SUITABLE"  # rejected at review; never entered the pipeline
    TALENT_POOL = "TALENT_POOL"    # kept in the central pool; not this requirement
    FAKE = "FAKE"
    BLACKLISTED = "BLACKLISTED"
    UNTAGGED = "UNTAGGED"          # recruiter removed the candidate from the pool
    REQ_CLOSED = "REQ_CLOSED"      # requirement reached a terminal/ended state
