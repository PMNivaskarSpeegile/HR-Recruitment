"""
Candidate domain logic (UC2).

Owns: duplicate detection (§7), CV-serial generation, create/update, skill
tagging, and Excel bulk import. Kept out of the views so the rules are testable
and reused by both the manual form and the bulk uploader.
"""
import logging
import re
import unicodedata
from datetime import datetime

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models.functions import Lower
from django.utils import timezone

from admin_module.models import (
    CandidateInteraction,
    CandidateMaster,
    CandidateSkill,
    CandidateStatusMaster,
    JdCvMapping,
    LocationMaster,
    NoticePeriodMaster,
    SkillMaster,
    SourceMaster,
    WorkModeMaster,
)
from core.constants import (
    ApplicationStatus, CandidateStatus, DuplicateReview, InteractionType,
    ReviewResolution, ReviewStatus,
)

logger = logging.getLogger("ats")

# Outcomes of an upsert attempt (also used in the bulk-import report).
CREATED = "CREATED"
UPDATED = "UPDATED"
POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"

_MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# CV serial
# ---------------------------------------------------------------------------
def next_cv_serial() -> str:
    """Next CV serial like CV-000001 (parse the max so it stays stable)."""
    last = (
        CandidateMaster.objects
        .filter(cv_serial__startswith="CV-")
        .order_by("-cv_serial")
        .values_list("cv_serial", flat=True)
        .first()
    )
    seq = (int(last.rsplit("-", 1)[-1]) + 1) if last else 1
    return f"CV-{seq:06d}"


# ---------------------------------------------------------------------------
# Duplicate detection (§7) — mobile is the primary identifier.
# ---------------------------------------------------------------------------
def detect_duplicate(mobile: str, email: str):
    existing = CandidateMaster.objects.filter(mobile=mobile).first()
    if existing is None:
        return None, CREATED
    if (existing.email or "").strip().lower() == (email or "").strip().lower():
        return existing, UPDATED
    return existing, POSSIBLE_DUPLICATE


# ---------------------------------------------------------------------------
# Skill tagging
# ---------------------------------------------------------------------------
def requirement_skill_ids(requirement) -> list:
    if requirement is None:
        return []
    return [s for s in (requirement.skill1_id, requirement.skill2_id, requirement.skill3_id) if s]


def tag_skills(candidate, skill_ids):
    for skill_id in {s for s in skill_ids if s}:
        CandidateSkill.objects.get_or_create(candidate=candidate, skill_id=skill_id)


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------
@transaction.atomic
def upsert_candidate(*, data: dict, user, requirement=None, extra_skill_ids=None, allow_update=True):
    """Create or update a candidate applying the duplicate rules.

    Returns {"action": CREATED|UPDATED|POSSIBLE_DUPLICATE, "candidate": <obj or existing>}.
    On POSSIBLE_DUPLICATE nothing is written — the caller surfaces it for the
    recruiter to resolve (mobile is UNIQUE, so we never create a clashing row).
    """
    mobile = data.get("mobile")
    email = data.get("email")
    existing, action = detect_duplicate(mobile, email)

    # Candidate skills come from the candidate's OWN profile (manual entry / bulk
    # sheet / Verify & Update) — NEVER copied from the requirement. Selecting a
    # requirement instead creates an explicit pre-pipeline Review tag (below).
    skill_ids = set(extra_skill_ids or [])

    if action == POSSIBLE_DUPLICATE:
        logger.info("Possible duplicate for mobile %s (existing cv_id=%s)", mobile, existing.cv_id)
        return {"action": POSSIBLE_DUPLICATE, "candidate": existing}

    if action == UPDATED:
        if allow_update:
            for field, value in data.items():
                setattr(existing, field, value)
            existing.updated_by = user
            existing.updated_on = timezone.now()
            existing.save()
            tag_skills(existing, skill_ids)
            if requirement is not None:
                tag_candidate_for_review(candidate=existing, requirement=requirement, user=user)
            logger.info("Candidate updated: %s (cv_id=%s)", existing.cv_serial, existing.cv_id)
        return {"action": UPDATED, "candidate": existing}

    # CREATE — retry on the (rare) serial collision.
    new_cand_status = CandidateStatusMaster.objects.get(status_code=CandidateStatus.NEW_CV)
    last_error = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with transaction.atomic():
                candidate = CandidateMaster.objects.create(
                    cv_serial=next_cv_serial(),
                    candidate_status=new_cand_status,
                    uploaded_by=user,
                    created_by=user,
                    created_on=timezone.now(),
                    is_active=True,
                    is_duplicate=False,
                    **data,
                )
            tag_skills(candidate, skill_ids)
            if requirement is not None:
                tag_candidate_for_review(candidate=candidate, requirement=requirement, user=user)
            logger.info("Candidate created: %s (cv_id=%s)", candidate.cv_serial, candidate.cv_id)
            from core.activity import ActivityType, log_activity
            log_activity(
                ActivityType.CANDIDATE_ADDED,
                f"Candidate added: {candidate.candidate_name}",
                candidate=candidate, actor=user,
            )
            return {"action": CREATED, "candidate": candidate}
        except IntegrityError as exc:
            last_error = exc
            # Only a cv_serial race is safe to retry (a fresh serial fixes it).
            # A genuine mobile/email UNIQUE violation must surface immediately —
            # retrying identical data would just fail again.
            if "cv_serial" not in str(exc).lower():
                raise
            logger.warning("CV serial collision (attempt %d) — retrying", attempt)
    raise last_error


# ---------------------------------------------------------------------------
# Duplicate Review — shared create/dedupe (used by the single-create escalation
# AND bulk upload) so both feed the same Admin Pending Duplicate Review queue.
# ---------------------------------------------------------------------------
def record_possible_duplicate(*, existing_candidate, new_candidate_name, new_mobile,
                              new_email, detection_reason, submitted_payload, user):
    """Create (or reuse) a PENDING CandidateDuplicateReview. Dedupes on
    (existing_candidate, new_mobile, new_email) among PENDING reviews so repeated
    detections don't pile up. Never touches candidate status. Returns
    (review, created)."""
    from admin_module.models import CandidateDuplicateReview
    existing = CandidateDuplicateReview.objects.filter(
        existing_candidate=existing_candidate,
        new_mobile=new_mobile,
        new_email=new_email or None,
        review_status=DuplicateReview.PENDING,
    ).first()
    if existing is not None:
        return existing, False
    review = CandidateDuplicateReview.objects.create(
        existing_candidate=existing_candidate,
        new_candidate_name=new_candidate_name,
        new_mobile=new_mobile,
        new_email=new_email,
        detection_reason=detection_reason,
        submitted_payload=submitted_payload,
        review_status=DuplicateReview.PENDING,
        created_by=user,
        created_on=timezone.now(),
    )
    return review, True


# ---------------------------------------------------------------------------
# Candidate Profile Verification & Update (edit the MASTER profile)
# ---------------------------------------------------------------------------
class DuplicateConflict(Exception):
    """A profile edit to mobile/email collides with a DIFFERENT candidate. The
    caller (view) creates the possible-duplicate review OUTSIDE this service's
    transaction and returns 409 — the edit is not saved (duplicate workflow
    preserved)."""
    def __init__(self, *, existing, editing, new_candidate_name, new_mobile, new_email):
        self.existing = existing
        self.editing = editing
        self.new_candidate_name = new_candidate_name
        self.new_mobile = new_mobile
        self.new_email = new_email


# (attr, human label, kind) for the field-level audit. kind: scalar|fk|bool.
_PROFILE_FIELDS = [
    ("candidate_name", "Full Name", "scalar"),
    ("email", "Email", "scalar"),
    ("mobile", "Mobile Number", "scalar"),
    ("current_location", "Current Location", "fk"),
    ("preferred_location", "Preferred Location", "fk"),
    ("notice_period", "Notice Period", "fk"),
    ("work_mode", "Work Mode", "fk"),
    ("source", "Source", "fk"),
    ("current_company", "Current Company", "scalar"),
    ("current_designation", "Current Designation", "scalar"),
    ("highest_qualification", "Education", "scalar"),
    ("certifications", "Certifications", "scalar"),
    ("additional_notes", "Additional Notes", "scalar"),
    ("exp_min", "Total Experience (min)", "scalar"),
    ("exp_max", "Total Experience (max)", "scalar"),
    ("relevant_exp", "Relevant Experience", "scalar"),
    ("current_ctc_lpa", "Current CTC", "scalar"),
    ("expected_ctc_lpa", "Expected CTC", "scalar"),
    ("is_willing_to_relocate", "Willing to Relocate", "bool"),
]


def _fk_label(obj):
    if obj is None:
        return ""
    for a in ("np_name", "work_mode_name", "source_name", "city", "status_name"):
        if hasattr(obj, a):
            return str(getattr(obj, a))
    return str(obj)


def _disp(val, kind):
    if val is None:
        return ""
    if kind == "fk":
        return _fk_label(val)
    if kind == "bool":
        return "Yes" if val else "No"
    return str(val)


@transaction.atomic
def verify_and_update_candidate(*, candidate, validated_data, user, source="Recruiter Manual Update"):
    """Update the single MASTER candidate profile (visible across all requirements),
    with a full field-level audit, timeline entry, and verification stamp. Identity
    changes (mobile/email) re-run the EXISTING duplicate detection — a collision
    with another candidate raises DuplicateConflict (change not saved). Returns
    {candidate, changed_fields, verified}."""
    data = dict(validated_data)
    verified = data.pop("verified", True)
    skill_ids = data.pop("skill_ids", None)
    now = timezone.now()
    new_mobile = data.get("mobile", candidate.mobile)
    new_email = data.get("email", candidate.email)

    # --- Duplicate re-check on identity change (reuse existing services) ------
    other = None
    if "mobile" in data and data["mobile"] and data["mobile"] != candidate.mobile:
        other = CandidateMaster.objects.filter(mobile=data["mobile"]).exclude(cv_id=candidate.cv_id).first()
    if other is None and "email" in data and data["email"] and \
            (data["email"] or "").strip().lower() != (candidate.email or "").strip().lower():
        other = CandidateMaster.objects.filter(email__iexact=data["email"]).exclude(cv_id=candidate.cv_id).first()
    if other is not None:
        # Raise BEFORE any write (and before creating the review) so this atomic
        # rolls back cleanly; the view creates the review outside this transaction.
        raise DuplicateConflict(
            existing=other, editing=candidate,
            new_candidate_name=data.get("candidate_name", candidate.candidate_name),
            new_mobile=new_mobile, new_email=new_email,
        )

    # --- Diff + apply scalar/fk fields --------------------------------------
    changes = []  # (label, old_disp, new_disp)
    for attr, label, kind in _PROFILE_FIELDS:
        if attr not in data:
            continue
        old_disp = _disp(getattr(candidate, attr), kind)
        setattr(candidate, attr, data[attr])
        new_disp = _disp(getattr(candidate, attr), kind)
        if old_disp != new_disp:
            changes.append((label, old_disp, new_disp))

    # --- Skills (compare id sets; reuse tag_skills) -------------------------
    if skill_ids is not None:
        old_ids = set(CandidateSkill.objects.filter(candidate=candidate).values_list("skill_id", flat=True))
        new_ids = {s.skill_id for s in skill_ids}
        if old_ids != new_ids:
            def _names(ids):
                return ", ".join(sorted(SkillMaster.objects.filter(skill_id__in=ids).values_list("skill_name", flat=True)))
            old_disp, new_disp = _names(old_ids), _names(new_ids)
            CandidateSkill.objects.filter(candidate=candidate).delete()
            tag_skills(candidate, new_ids)
            changes.append(("Skills", old_disp, new_disp))

    # Reconcile: once a real Location is set, drop the raw import fallback text
    # so the candidate stops showing as "unmapped".
    if data.get("current_location") is not None and candidate.current_location_text:
        candidate.current_location_text = None

    # --- Verification stamp + save ------------------------------------------
    if verified:
        candidate.profile_verified = True
        candidate.profile_verified_by = user
        candidate.profile_verified_on = now
    candidate.updated_by = user
    candidate.updated_on = now
    candidate.save()

    # --- Field-level audit (append-only) + timeline summary ------------------
    from admin_module.models import CandidateProfileAudit
    for label, old_disp, new_disp in changes:
        CandidateProfileAudit.objects.create(
            candidate=candidate, field_name=label, old_value=old_disp, new_value=new_disp,
            source=source, changed_by=user, changed_on=now,
        )
    if changes or verified:
        changed_labels = ", ".join(l for l, _, _ in changes) or "no field changes"
        verb = "verified & updated" if verified else "updated"
        CandidateInteraction.objects.create(
            candidate=candidate, req=None, interaction_type=InteractionType.STATUS_CHANGE,
            comment=f"Candidate profile {verb} — {changed_labels}.",
            created_by=user, created_on=now,
        )
    logger.info("Profile %s for %s: %d field(s) changed by user %s",
                "verified+updated" if verified else "updated", candidate.cv_serial,
                len(changes), getattr(user, "user_id", None))
    return {"candidate": candidate, "changed_fields": [l for l, _, _ in changes], "verified": verified}


# ---------------------------------------------------------------------------
# Verify & Update — the single recruiter decision (replaces standalone Review)
# ---------------------------------------------------------------------------
DECISION_SHORTLIST = "SHORTLIST"
DECISION_NOT_SUITABLE = "NOT_SUITABLE"
DECISION_FAKE = "FAKE"
DECISION_BLACKLIST = "BLACKLIST"
DECISION_SAVE = "SAVE"
VERIFY_DECISIONS = (DECISION_SHORTLIST, DECISION_NOT_SUITABLE, DECISION_FAKE,
                    DECISION_BLACKLIST, DECISION_SAVE)
_DECISION_NEEDS_REQUIREMENT = (DECISION_SHORTLIST, DECISION_NOT_SUITABLE)


class DecisionError(Exception):
    """An invalid Verify & Update decision (e.g. Shortlist without a requirement)."""


def _set_candidate_global(candidate, code, user, reason=None):
    """Set the candidate's GLOBAL status directly (Fake / Blacklist / Talent Pool)
    with a timeline note — used when there's no application to close."""
    now = timezone.now()
    candidate.candidate_status = _candidate_status(code)
    candidate.last_status_changed_on = now
    candidate.updated_by = user
    candidate.updated_on = now
    candidate.save(update_fields=["candidate_status", "last_status_changed_on", "updated_by", "updated_on"])
    label = code.replace("_", " ").title()
    note = f"Marked {label}." + (f" Reason: {reason}" if reason else "")
    _log_candidate(candidate, note, user)


@transaction.atomic
def apply_candidate_decision(*, candidate, decision, user, requirement=None, reason=None,
                             move_to_talent_pool=False):
    """The ONE recruiter decision after Verify & Update, made from a requirement's
    Review Pool. Each decision RESOLVES the pre-pipeline review association; ONLY
    Shortlist also creates a jd_cv_mapping (pipeline entry). Per the approved
    workflow:
      Shortlist    → jd_cv_mapping + resolve review (SHORTLISTED); candidate → Talent Pool
      Talent Pool  → candidate → Talent Pool + resolve review (TALENT_POOL); no mapping
      Not Suitable → resolve review (NOT_SUITABLE) ONLY; no mapping, no global change
      Fake/Blacklist → global status + resolve ALL active reviews; no mapping
    Returns a dict describing what happened (`mapping` is None unless Shortlist)."""
    if decision not in VERIFY_DECISIONS:
        raise DecisionError(f"Unknown decision '{decision}'.")
    if decision in _DECISION_NEEDS_REQUIREMENT and requirement is None:
        raise DecisionError(f"A requirement is required to {decision.replace('_', ' ').title()}.")

    from pipeline.services import enter_pipeline

    if decision == DECISION_SHORTLIST:
        mapping = enter_pipeline(requirement=requirement, candidate=candidate, user=user, comments=reason)
        resolve_review(candidate=candidate, requirement=requirement,
                       resolution=ReviewResolution.SHORTLISTED, user=user)
        return {"decision": decision, "mapping": mapping}

    if decision == DECISION_NOT_SUITABLE:
        # Resolve the review association ONLY — the candidate never enters the
        # pipeline, so NO jd_cv_mapping is created and the global status is unchanged.
        resolve_review(candidate=candidate, requirement=requirement,
                       resolution=ReviewResolution.NOT_SUITABLE, user=user)
        if reason:
            _log_candidate(candidate, f"Not Suitable for {requirement.req_tracker_no}. {reason}", user)
        return {"decision": decision, "mapping": None}

    if decision in (DECISION_FAKE, DECISION_BLACKLIST):
        code = CandidateStatus.FAKE if decision == DECISION_FAKE else CandidateStatus.BLACKLISTED
        _set_candidate_global(candidate, code, user, reason)
        resolve_all_reviews(candidate=candidate,
                            resolution=(ReviewResolution.FAKE if decision == DECISION_FAKE
                                        else ReviewResolution.BLACKLISTED), user=user)
        return {"decision": decision, "candidate": candidate, "mapping": None}

    # DECISION_SAVE (Talent Pool): keep in the central pool; resolve this requirement's
    # review only (candidate stays available to be tagged to other requirements).
    _set_candidate_global(candidate, CandidateStatus.SAVED, user, reason)
    resolve_review(candidate=candidate, requirement=requirement,
                   resolution=ReviewResolution.TALENT_POOL, user=user)
    return {"decision": decision, "candidate": candidate, "mapping": None}


# ---------------------------------------------------------------------------
# Pre-pipeline Review Pool — explicit candidate↔requirement "under review" tags
# (candidate_requirement_review). Separate from jd_cv_mapping (= entered pipeline).
# ---------------------------------------------------------------------------
def _review_model():
    from admin_module.models import CandidateRequirementReview
    return CandidateRequirementReview


def _requirement_open_for_review(requirement) -> bool:
    from core.constants import ReqStatus
    from requirements.services import requirement_is_expired
    if getattr(requirement, "recruitment_ended", False):
        return False
    if requirement_is_expired(requirement):
        return False
    code = requirement.req_status.status_code if requirement.req_status_id else None
    return code in ReqStatus.WORKABLE


def _resolve_review_row(review, resolution, user):
    now = timezone.now()
    review.status = ReviewStatus.RESOLVED
    review.resolution = resolution
    review.resolved_by = user
    review.resolved_on = now
    review.updated_on = now
    review.save(update_fields=["status", "resolution", "resolved_by", "resolved_on", "updated_on"])


@transaction.atomic
def tag_candidate_for_review(*, candidate, requirement, user):
    """Explicitly put a candidate UNDER REVIEW for a requirement (adds them to its
    Review Pool). Creates — or reactivates — the single ACTIVE association for the
    pair. Idempotent. Never creates a jd_cv_mapping. Raises DecisionError if the
    candidate isn't usable or the requirement isn't open for new candidates."""
    current = candidate.candidate_status.status_code if candidate.candidate_status_id else None
    if current in (CandidateStatus.FAKE, CandidateStatus.BLACKLISTED):
        raise DecisionError("This candidate cannot be added to a review pool.")
    if not _requirement_open_for_review(requirement):
        raise DecisionError("This requirement is not open for new candidates.")

    now = timezone.now()
    review, created = _review_model().objects.get_or_create(
        candidate=candidate, req=requirement,
        defaults={"status": ReviewStatus.ACTIVE, "tagged_by": user, "tagged_on": now,
                  "created_on": now},
    )
    if not created and review.status != ReviewStatus.ACTIVE:
        review.status = ReviewStatus.ACTIVE
        review.resolution = None
        review.tagged_by = user
        review.tagged_on = now
        review.resolved_by = None
        review.resolved_on = None
        review.updated_on = now
        review.save()
    if created or review.status == ReviewStatus.ACTIVE:
        _log_candidate(candidate, f"Added to the review pool for {requirement.req_tracker_no}.", user)
    return review


@transaction.atomic
def untag_candidate_review(*, candidate, requirement, user):
    """Remove a candidate from a requirement's Review Pool (resolve as UNTAGGED)."""
    review = _review_model().objects.filter(
        candidate=candidate, req=requirement, status=ReviewStatus.ACTIVE).first()
    if review is None:
        return None
    _resolve_review_row(review, ReviewResolution.UNTAGGED, user)
    _log_candidate(candidate, f"Removed from the review pool for {requirement.req_tracker_no}.", user)
    return review


def resolve_review(*, candidate, requirement, resolution, user):
    """Resolve the ACTIVE review for one (candidate, requirement), if present."""
    if requirement is None:
        return None
    review = _review_model().objects.filter(
        candidate=candidate, req=requirement, status=ReviewStatus.ACTIVE).first()
    if review is not None:
        _resolve_review_row(review, resolution, user)
    return review


def resolve_all_reviews(*, candidate, resolution, user):
    """Resolve every ACTIVE review for a candidate (Fake/Blacklist → drop from all pools)."""
    for review in _review_model().objects.filter(candidate=candidate, status=ReviewStatus.ACTIVE):
        _resolve_review_row(review, resolution, user)


def resolve_reviews_for_requirement(*, requirement, resolution, user):
    """Resolve every ACTIVE review for a requirement (used when it stops recruiting)."""
    count = 0
    for review in _review_model().objects.filter(req=requirement, status=ReviewStatus.ACTIVE):
        _resolve_review_row(review, resolution, user)
        count += 1
    return count


# ---------------------------------------------------------------------------
# Excel bulk import (mentor-approved Naukri profile-export template)
# ---------------------------------------------------------------------------
# The template's data lives in the "Candidate Details" sheet; the header row is
# auto-detected (it is NOT row 1 — Naukri prefixes decorative title rows), the
# "Candidate insights" analytics sheet + blank/decorative rows are ignored.

# Downloadable sample template (clean header on row 1; same columns as the
# mentor template — the parser auto-detects the header wherever it sits).
BULK_TEMPLATE_HEADERS = [
    "Candidate Name", "Resume Title", "Contact No.", "Email", "Work Exp",
    "Annual Salary", "Current Location", "Preferred Location", "Current Employer",
    "Designation", "U.G. Course", "P. G. Course", "Post P. G. Course",
    "Age/Date of Birth", "Postal Address",
    "Comment 1", "Comment 2", "Comment 3", "Comment 4", "Comment 5",
]
BULK_TEMPLATE_EXAMPLE = [
    "Arjun Sharma", "React Native Developer | 5 yrs", "9900100001", "arjun@example.com",
    "5Y 6 M", "INR 12.0 L", "Bangalore", "Bangalore,Pune,Remote", "Infosys",
    "Senior React Native Developer", "B.Tech/B.E.", "MCA", "",
    "30 y (15 Jun 1995)", "12 MG Road, Bangalore",
    "Immediate joiner", "", "", "", "",
]

# Row status codes surfaced in preview + import (independent of candidate status).
ROW_VALID, ROW_INVALID, ROW_DUPLICATE, ROW_UPDATE = "VALID", "INVALID", "DUPLICATE", "UPDATE"


def _clean(value):
    return str(value).strip() if value is not None else ""


def _norm_header(s):
    """Normalize a header/label for matching: lower-case, punctuation → single
    spaces (so 'P. G. Course' → 'p g course', 'Contact No.' → 'contact no')."""
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


# Normalized header → canonical column key. Deterministic (no fuzzy matching, to
# avoid mis-mapping columns like "alternate email"); add explicit variants here.
_HEADER_MAP = {
    "candidate name": "candidate_name", "name": "candidate_name", "full name": "candidate_name",
    "candidate": "candidate_name", "candidate full name": "candidate_name",
    "resume title": "resume_title", "profile title": "resume_title", "headline": "resume_title",
    "contact no": "mobile", "contact number": "mobile", "mobile": "mobile", "phone": "mobile",
    "phone no": "mobile", "mobile number": "mobile", "mobile no": "mobile", "phone number": "mobile",
    "contact": "mobile", "contact number mobile": "mobile",
    "email": "email", "email id": "email", "email address": "email", "e mail": "email", "emailid": "email",
    "work exp": "work_exp", "experience": "work_exp", "total experience": "work_exp",
    "total work experience": "work_exp", "work experience": "work_exp", "exp": "work_exp",
    "annual salary": "annual_salary", "current ctc": "annual_salary", "salary": "annual_salary",
    "ctc": "annual_salary", "current salary": "annual_salary", "annual ctc": "annual_salary",
    "current location": "current_location", "location": "current_location", "current city": "current_location",
    "preferred location": "preferred_location", "preferred locations": "preferred_location",
    "preferred city": "preferred_location",
    "current employer": "current_company", "current company": "current_company",
    "employer": "current_company", "company": "current_company", "organisation": "current_company",
    "organization": "current_company",
    "designation": "current_designation", "current designation": "current_designation", "job title": "current_designation",
    "role": "current_designation",
    "u g course": "ug_course", "ug course": "ug_course", "under graduation": "ug_course", "graduation": "ug_course",
    "p g course": "pg_course", "pg course": "pg_course", "post graduation": "pg_course",
    "post p g course": "ppg_course", "post pg course": "ppg_course", "doctorate": "ppg_course",
    "age date of birth": "age_dob", "date of birth": "age_dob", "dob": "age_dob", "age": "age_dob",
    "age dob": "age_dob", "birth date": "age_dob",
    "postal address": "postal_address", "address": "postal_address", "location address": "postal_address",
}
_REQUIRED_HEADER_KEYS = {"candidate_name", "mobile", "email"}

# Curated city alias map (normalized variant → canonical spelling). Only helps
# when the canonical name exists in location_master; NO auto-creation of rows.
_CITY_ALIASES = {
    "bengaluru": "Bangalore", "blr": "Bangalore",
    "bombay": "Mumbai",
    "new delhi": "Delhi", "delhi ncr": "Delhi", "ncr": "Delhi",
    "gurugram": "Gurugram", "gurgaon": "Gurugram",
    "calcutta": "Kolkata",
    "trivandrum": "Thiruvananthapuram",
    "madras": "Chennai",
    "pune": "Pune", "hyderabad": "Hyderabad", "chennai": "Chennai", "kochi": "Kochi",
}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _parse_experience(raw):
    """'7Y 7 M' / '6Y 5 M' / '5' → total years as a float (1 dp), or None."""
    if raw is None or str(raw).strip() == "":
        return None
    s = str(raw).lower()
    ym, mm = re.search(r"(\d+(?:\.\d+)?)\s*y", s), re.search(r"(\d+(?:\.\d+)?)\s*m", s)
    if ym or mm:
        years = float(ym.group(1)) if ym else 0.0
        months = float(mm.group(1)) if mm else 0.0
        return round(years + months / 12.0, 1)
    n = re.search(r"(\d+(?:\.\d+)?)", s)
    return round(float(n.group(1)), 1) if n else None


def _parse_salary_lpa(raw):
    """'INR 7.2 L' → 7.2; 'USD ...' / '0.0 L' / blank → None. Returns (value|None, warning|None)."""
    if raw is None or str(raw).strip() == "":
        return None, None
    s = str(raw).strip()
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None, f"Annual Salary '{s}' not understood — left blank"
    val = float(m.group(1))
    if "USD" in s.upper():
        return None, f"Annual Salary '{s}' not in INR — left blank"
    if val == 0.0:
        return None, None  # Naukri '0.0 L' = undisclosed
    if val > 99999.99:
        return None, f"Annual Salary '{s}' out of range — left blank"
    return round(val, 2), None


def _parse_age_dob(raw):
    """'32 y\\n(09 Sep 1993)' → (age:int|None, dob:date|None, warning|None)."""
    if raw is None or str(raw).strip() == "":
        return None, None, None
    s = str(raw)
    age = None
    am = re.search(r"(\d{1,3})\s*y", s.lower())
    if am:
        a = int(am.group(1))
        age = a if 14 <= a <= 100 else None
    dob = None
    warn = None
    dm = re.search(r"(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})", s)
    if dm:
        token = re.sub(r"\s+", " ", dm.group(1)).strip()
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                dob = datetime.strptime(token, fmt).date()
                break
            except ValueError:
                continue
    # DOB sanity (Feature 5f): drop implausible dates, but keep the imported age
    # snapshot. A future or absurdly-old DOB is data noise, not a hard error.
    if dob is not None:
        today = timezone.now().date()
        years = (today - dob).days / 365.25
        if dob > today:
            warn = f"Date of Birth '{dob:%d %b %Y}' is in the future — left blank"
            dob = None
        elif not (14 <= years <= 100):
            warn = f"Date of Birth '{dob:%d %b %Y}' is implausible (age ~{years:.0f}) — left blank"
            dob = None
        elif age is not None and abs(years - age) > 2:
            warn = f"Imported Age ({age}) doesn't match Date of Birth ({dob:%d %b %Y}) — both kept as imported"
    if warn is None and s.strip() and age is None and dob is None:
        warn = f"Age/Date of Birth '{s.strip()}' not understood — left blank"
    return age, dob, warn


def _normalize_mobile_token(token):
    """A single token → 10-digit Indian mobile (strips +91 / leading 0), or None."""
    digits = re.sub(r"\D", "", token or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def _clean_mobile(raw):
    """First valid 10-digit mobile from a cell. Naukri sometimes packs TWO numbers
    into one cell (newline/comma separated) — we take the first valid one.
    Returns (mobile|None, had_multiple: bool)."""
    s = str(raw or "").strip()
    if not s:
        return None, False
    tokens = [t for t in re.split(r"[\s,;/|]+", s) if t]
    valid = [m for m in (_normalize_mobile_token(t) for t in tokens) if m]
    if valid:
        return valid[0], len(tokens) > 1
    # Fall back to the whole string (handles a single number with stray symbols).
    return _normalize_mobile_token(s), len(tokens) > 1


def _pick_qualification(ug, pg, ppg):
    """Highest present qualification by level (Post-PG > PG > UG), Title-cased, ≤80."""
    for v in (ppg, pg, ug):
        c = _clean(v)
        if c:
            return c.title()[:80]
    return None


def _normalize_city(value):
    """Canonical form for case-insensitive location matching: Unicode NFKC-
    normalize, then trim and collapse internal whitespace. So 'Gurugram ',
    'Gurugram' (with a non-breaking space) and 'Gurugram' all compare equal to
    the Location Master city 'Gurugram'."""
    s = unicodedata.normalize("NFKC", str(value if value is not None else ""))
    return re.sub(r"\s+", " ", s).strip()


def _split_location(text):
    """Split a free-text location into (city, state, country) on commas —
    e.g. 'Gurugram, Haryana, India'. Each part is whitespace/Unicode-normalized;
    absent parts are None. A bare 'Gurugram' → ('Gurugram', None, None)."""
    parts = [_normalize_city(p) for p in str(text or "").split(",")]
    city = parts[0] if parts else ""
    state = parts[1] if len(parts) > 1 and parts[1] else None
    country = parts[2] if len(parts) > 2 and parts[2] else None
    return city, state, country


def _pick_unique_location(candidates, state=None, country=None):
    """From active Location Master rows sharing a (normalized) city, return the
    single unambiguous match, else None. When the import carries a state and/or
    country, narrow by those first; auto-map ONLY when exactly one row remains.
    Zero or multiple matches → None (kept unmapped for the admin to resolve),
    which prevents guessing between same-named cities in different states."""
    pool = candidates
    if state:
        s = _normalize_city(state).lower()
        pool = [l for l in pool if _normalize_city(l.state).lower() == s]
    if country:
        c = _normalize_city(country).lower()
        pool = [l for l in pool if _normalize_city(l.country).lower() == c]
    return pool[0] if len(pool) == 1 else None


def _location_cache():
    """{normalized-city: [active LocationMaster, …]} — loaded once per import so
    lookups don't hit the DB per row. Keyed by normalized city (there can be
    several rows for one city name across states/countries)."""
    cache = {}
    for loc in LocationMaster.objects.filter(is_active=True):
        cache.setdefault(_normalize_city(loc.city).lower(), []).append(loc)
    return cache


def _resolve_location(raw, loc_cache=None):
    """(LocationMaster|None, original_text). Normalizes the imported location
    (trim, collapse spaces, NFKC) and resolves to a single active Location Master
    row via case-insensitive matching — using state/country too when the text
    supplies them. Tries the city AS IMPORTED first, so a name that IS in the
    master (e.g. 'Gurugram') is never rewritten away by the alias map; the alias
    canonical (e.g. 'Bengaluru' → 'Bangalore') is only a fallback when the literal
    name isn't in the master. Never auto-maps an ambiguous city; never creates a
    row. Uses `loc_cache` when provided, else builds one (a single query)."""
    cleaned = _clean(raw)
    if not cleaned:
        return None, ""
    city, state, country = _split_location(cleaned)
    if not city:
        return None, cleaned
    if loc_cache is None:
        loc_cache = _location_cache()
    # Literal city first, then the alias canonical (if different) as a fallback —
    # never let the alias override a city that already exists in the master.
    keys = [_normalize_city(city).lower()]
    alias = _CITY_ALIASES.get(_norm_header(city))
    if alias:
        alias_key = _normalize_city(alias).lower()
        if alias_key not in keys:
            keys.append(alias_key)
    for key in keys:
        match = _pick_unique_location(loc_cache.get(key, []), state, country)
        if match is not None:
            return match, cleaned
    return None, cleaned


def _cell(row, idx):
    return row[idx] if idx is not None and idx < len(row) else None


class BulkParseError(Exception):
    """The uploaded file can't be opened as an .xlsx (corrupt / empty / wrong
    format / password-protected). Surfaced as a clean 400, never a 500."""


def _load_candidate_sheet(file):
    """Pick the 'Candidate Details' sheet (fallback: first/active sheet).
    Raises BulkParseError if the workbook can't be opened."""
    import openpyxl
    try:
        wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 — any load failure → a clean 400
        raise BulkParseError(
            "Could not read the file — please upload a valid .xlsx exported from the template."
        ) from exc
    for ws in wb.worksheets:
        if _norm_header(ws.title) == "candidate details":
            return ws
    return wb.active


def _detect_header(ws, scan=25):
    """Find the header row by scanning for one containing the required labels.
    Returns (excel_row|None, {canonical_key: col_index}, [comment_col_indexes])."""
    for r, row in enumerate(ws.iter_rows(min_row=1, max_row=scan, values_only=True), start=1):
        cols, comment_idxs = {}, []
        for i, cell in enumerate(row or ()):
            key = _norm_header(cell)
            if not key:
                continue
            if key.startswith("comment"):
                comment_idxs.append(i)
            elif key in _HEADER_MAP:
                cols.setdefault(_HEADER_MAP[key], i)
        if _REQUIRED_HEADER_KEYS.issubset(cols.keys()):
            return r, cols, comment_idxs
    return None, {}, []


def _parse_candidate_row(cols, comment_idxs, row, loc_cache=None):
    """Map one data row → (candidate kwargs, errors, warnings). Collects ALL
    validation errors (never stops at the first)."""
    data, errors, warnings, notes = {}, [], [], []

    name = _clean(_cell(row, cols.get("candidate_name")))
    if not name:
        errors.append("Candidate Name is required")
    else:
        if len(name) > 100:
            warnings.append("Candidate Name truncated to 100 characters")
        data["candidate_name"] = name[:100]

    mobile_raw = _clean(_cell(row, cols.get("mobile")))
    if not mobile_raw:
        errors.append("Contact No. is required")
    else:
        mobile, had_multiple = _clean_mobile(mobile_raw)
        if not mobile:
            errors.append(f"Contact No. '{mobile_raw}' is not a valid 10-digit mobile")
        else:
            data["mobile"] = mobile
            if had_multiple:
                warnings.append(f"Multiple contact numbers found — used {mobile}")

    email = _clean(_cell(row, cols.get("email"))).lower()
    if not email:
        errors.append("Email is required")
    elif not _EMAIL_RE.match(email):
        errors.append(f"Email '{email}' is not a valid email address")
    else:
        data["email"] = email

    if "work_exp" in cols:
        raw = _cell(row, cols["work_exp"])
        exp = _parse_experience(raw)
        if exp is not None:
            data["exp_min"] = data["exp_max"] = exp
        elif _clean(raw):
            warnings.append(f"Work Exp '{_clean(raw)}' not understood — left blank")

    if "annual_salary" in cols:
        val, note = _parse_salary_lpa(_cell(row, cols["annual_salary"]))
        if val is not None:
            data["current_ctc_lpa"] = val
        if note:
            warnings.append(note)

    if "current_company" in cols:
        c = _clean(_cell(row, cols["current_company"]))
        if c:
            if len(c) > 100:
                warnings.append("Current Employer truncated to 100 characters")
            data["current_company"] = c[:100]
    if "current_designation" in cols:
        c = _clean(_cell(row, cols["current_designation"]))
        if c:
            if len(c) > 120:
                warnings.append("Designation truncated to 120 characters")
            data["current_designation"] = c[:120]

    q = _pick_qualification(_cell(row, cols.get("ug_course")), _cell(row, cols.get("pg_course")),
                            _cell(row, cols.get("ppg_course")))
    if q:
        data["highest_qualification"] = q

    if "current_location" in cols:
        obj, text = _resolve_location(_cell(row, cols["current_location"]), loc_cache)
        if obj:
            data["current_location"] = obj
        elif text:
            data["current_location_text"] = text[:150]
            warnings.append(
                f"Current Location '{text}' not found in Location Master — kept as text. "
                f"Map it to an existing city or add it to Location Master before import to link it."
            )

    if "preferred_location" in cols:
        raw = _clean(_cell(row, cols["preferred_location"]))
        parts = [p.strip() for p in raw.split(",") if p.strip()] if raw else []
        if parts:
            obj, _ = _resolve_location(parts[0], loc_cache)
            if obj:
                data["preferred_location"] = obj
            else:
                warnings.append(f"Preferred Location '{parts[0]}' not found in Location Master — kept in notes.")
                notes.append(f"Preferred location: {parts[0]}")
            if len(parts) > 1:
                notes.append("Other preferred locations: " + ", ".join(parts[1:]))

    if "age_dob" in cols:
        age, dob, warn = _parse_age_dob(_cell(row, cols["age_dob"]))
        if age is not None:
            data["age_at_import"] = age
        if dob is not None:
            data["date_of_birth"] = dob
        if warn:
            warnings.append(warn)

    if "postal_address" in cols:
        addr = _clean(_cell(row, cols["postal_address"]))
        if addr:
            if len(addr) > 255:
                warnings.append("Postal Address truncated to 255 characters")
            data["postal_address"] = addr[:255]

    if "resume_title" in cols:
        rt = _clean(_cell(row, cols["resume_title"]))
        if rt:
            notes.insert(0, f"Resume title: {rt}")

    for n, idx in enumerate(comment_idxs, start=1):
        c = _clean(_cell(row, idx))
        if c:
            notes.append(f"Comment {n}: {c}")

    if notes:
        data["additional_notes"] = "\n".join(notes)
    data["is_willing_to_relocate"] = False
    return data, errors, warnings


def _parse_bulk_file(file, max_rows=None):
    """Parse the uploaded workbook once. Returns (header_row, cols, comment_idxs,
    parsed_rows). Skips decorative/empty rows; flags in-file duplicate mobiles /
    emails. Resolves locations against a one-time cache (no per-row query). Stops
    one row past `max_rows` when given, so the caller can reject oversized files
    without parsing the whole sheet."""
    ws = _load_candidate_sheet(file)
    header_row, cols, comment_idxs = _detect_header(ws)
    if header_row is None:
        return None, {}, [], []

    loc_cache = _location_cache()
    parsed, seen_mobiles, seen_emails = [], {}, {}
    for excel_row, row in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1):
        if row is None or all(c is None or _clean(c) == "" for c in row):
            continue  # skip blank / decorative rows
        data, errors, warnings = _parse_candidate_row(cols, comment_idxs, row, loc_cache)
        mob = data.get("mobile")
        if mob:
            if mob in seen_mobiles:
                errors.append(f"Duplicate Contact No. within the file (also in row {seen_mobiles[mob]})")
            else:
                seen_mobiles[mob] = excel_row
        eml = data.get("email")
        if eml:
            if eml in seen_emails:
                errors.append(f"Duplicate Email within the file (also in row {seen_emails[eml]})")
            else:
                seen_emails[eml] = excel_row
        parsed.append({
            "excel_row": excel_row, "data": data, "errors": errors, "warnings": warnings,
            "name": data.get("candidate_name") or _clean(_cell(row, cols.get("candidate_name"))),
            "mobile": data.get("mobile") or _clean(_cell(row, cols.get("mobile"))),
            "email": data.get("email") or _clean(_cell(row, cols.get("email"))),
        })
        if max_rows is not None and len(parsed) > max_rows:
            break  # stop early; the caller detects the overflow and rejects
    return header_row, cols, comment_idxs, parsed


# Row cap for a single upload (Feature 4). File-size cap lives in the view.
BULK_MAX_ROWS = getattr(settings, "BULK_MAX_ROWS", 5000)


def _build_existing_index(parsed):
    """Load the EXISTING candidates that a file's mobiles/emails could clash with
    — two bounded queries (scoped to the file's values), not one per row. Returns
    {"by_mobile": {mobile: {...}}, "by_email": {email_lower: {...}}}. This mirrors
    detect_duplicate's inputs so classification runs in-memory; the DB uniqueness
    constraints + upsert_candidate remain the authoritative write path."""
    file_mobiles = {p["data"]["mobile"] for p in parsed if p["data"].get("mobile")}
    file_emails = {p["data"]["email"] for p in parsed if p["data"].get("email")}
    by_mobile, by_email = {}, {}
    if file_mobiles:
        for cv_id, cv_serial, mobile, email in (CandidateMaster.objects
                .filter(mobile__in=file_mobiles)
                .values_list("cv_id", "cv_serial", "mobile", "email")):
            by_mobile[mobile] = {"cv_id": cv_id, "cv_serial": cv_serial, "email": (email or "").strip().lower()}
    if file_emails:
        for cv_id, cv_serial, el in (CandidateMaster.objects
                .annotate(_el=Lower("email"))
                .filter(_el__in=file_emails)
                .values_list("cv_id", "cv_serial", "_el")):
            by_email[el] = {"cv_id": cv_id, "cv_serial": cv_serial}
    return {"by_mobile": by_mobile, "by_email": by_email}


def _classify_row(p, index):
    """Given a parsed row + the pre-loaded existing-candidate `index`, return
    (status, duplicate_info|None) WITHOUT writing — same rules as detect_duplicate
    (no mobile → create; same mobile+email → update; same mobile, diff email →
    possible duplicate) plus the email-conflict guard (a new candidate whose email
    already belongs to a DIFFERENT candidate is INVALID). All in-memory. May append
    to p["errors"]."""
    if p["errors"]:
        return ROW_INVALID, None
    mobile = p["data"].get("mobile")
    email = (p["data"].get("email") or "").strip().lower()
    m = index["by_mobile"].get(mobile) if mobile else None
    if m is None:
        # No mobile match → a create. If the email is already taken, it's a
        # different person (email is UNIQUE) → conflict, not a create.
        e = index["by_email"].get(email) if email else None
        if e is not None:
            p["errors"].append(
                f"Email already used by {e['cv_serial']} (a different candidate) — resolve before import"
            )
            return ROW_INVALID, None
        return ROW_VALID, None
    match = {"existing_cv_serial": m["cv_serial"], "existing_cv_id": m["cv_id"]}
    if m["email"] == email:  # same mobile + same email → update THIS existing candidate
        return ROW_UPDATE, match
    return ROW_DUPLICATE, match  # same mobile, different email → possible duplicate


def _duplicate_file_batch(file_hash, exclude_batch_id=None):
    """The most recent COMPLETED batch imported from the same file bytes (by
    SHA-256), or None. Powers a non-blocking 'already uploaded' warning."""
    if not file_hash:
        return None
    from admin_module.models import BulkImportBatch
    qs = BulkImportBatch.objects.filter(file_hash=file_hash, status="COMPLETED")
    if exclude_batch_id:
        qs = qs.exclude(batch_id=exclude_batch_id)
    b = qs.order_by("-batch_id").first()
    if b is None:
        return None
    return {"batch_id": b.batch_id, "file_name": b.file_name,
            "created_on": b.created_on.isoformat() if b.created_on else None}


def preview_candidates_excel(*, file, user=None) -> dict:
    """Parse + validate + classify every row (no candidate writes) and return the
    per-row status, Excel row numbers, and all errors/warnings for the Import
    Preview + error report. Also flags if this exact file was already imported
    (non-blocking). When `user` is given (the API flow), a reusable DRAFT batch is
    created so import can CONFIRM this exact validated dataset without re-uploading
    or re-parsing (Feature 5a); its id is returned as `batch_id`."""
    import hashlib, io
    raw = file.read() if hasattr(file, "read") else file
    if isinstance(raw, str):  # a path was passed (e.g. tests) — read its bytes
        with open(raw, "rb") as fh:
            raw = fh.read()
    file_hash = hashlib.sha256(raw).hexdigest()
    try:
        header_row, cols, comment_idxs, parsed = _parse_bulk_file(io.BytesIO(raw), max_rows=BULK_MAX_ROWS)
    except BulkParseError as exc:
        return {"ok": False, "error": str(exc), "rows": [], "summary": {}}
    if header_row is None:
        return {"ok": False,
                "error": "Could not find the candidate header row (needs Candidate Name, Contact No., Email). "
                         "Use the sample template or the mentor-approved Naukri export.",
                "rows": [], "summary": {}}
    if len(parsed) > BULK_MAX_ROWS:
        return {"ok": False,
                "error": f"File exceeds the {BULK_MAX_ROWS}-row limit. Split it into smaller files.",
                "rows": [], "summary": {}}

    index = _build_existing_index(parsed)
    rows_out = []
    summary = {"total": len(parsed), "valid": 0, "update": 0, "duplicate": 0, "invalid": 0, "warnings": 0}
    for p in parsed:
        status_, dup = _classify_row(p, index)
        p["status"] = status_  # reused when persisting the draft
        summary[{ROW_VALID: "valid", ROW_UPDATE: "update", ROW_DUPLICATE: "duplicate", ROW_INVALID: "invalid"}[status_]] += 1
        if p["warnings"]:
            summary["warnings"] += 1
        rows_out.append({
            "excel_row": p["excel_row"], "name": p["name"], "mobile": p["mobile"], "email": p["email"],
            "status": status_, "errors": p["errors"], "warnings": p["warnings"], "duplicate": dup,
        })
    draft = _create_draft_batch(user=user, file=file, file_hash=file_hash, header_row=header_row, parsed=parsed) if user else None
    return {"ok": True, "batch_id": (draft.batch_id if draft else None),
            "header_row": header_row, "summary": summary, "rows": rows_out,
            "duplicate_file": _duplicate_file_batch(file_hash)}


def _serialize_row_data(data):
    """JSON-safe form of a parsed row's candidate kwargs for a DRAFT batch:
    FK objects → *_id, date → ISO string, everything else already primitive."""
    out = {}
    for k, v in data.items():
        if k in ("current_location", "preferred_location"):
            out[k + "_id"] = v.location_id if v is not None else None
        elif k == "date_of_birth":
            out[k] = v.isoformat() if v else None
        else:
            out[k] = v
    return out


def _deserialize_row_data(payload, loc_by_id=None):
    """Reconstruct candidate kwargs from a serialized draft payload (*_id → FK,
    ISO → date). Uses `loc_by_id` to avoid a per-row location query when given."""
    data = {}
    for k, v in payload.items():
        if k in ("current_location_id", "preferred_location_id"):
            if v is not None:
                loc = loc_by_id.get(v) if loc_by_id is not None else LocationMaster.objects.filter(location_id=v).first()
                if loc is not None:
                    data[k[:-3]] = loc  # strip "_id"
        elif k == "date_of_birth":
            if v:
                data[k] = datetime.strptime(v, "%Y-%m-%d").date()
        else:
            data[k] = v
    return data


# Persist running counts every N processed rows so an interrupted import still
# reports progress (row_report + COMPLETED are written only at the very end).
PROGRESS_FLUSH_EVERY = getattr(settings, "BULK_PROGRESS_FLUSH_EVERY", 50)


def _execute_import(*, batch, prepared, user, requirement, source, duplicate_file=None, classify_index=None):
    """Shared per-row import loop for BOTH the direct-file and draft-confirm paths.
    `prepared` is a list of rows: {excel_row, name, mobile, email, status, errors,
    warnings, data}. When `classify_index` is given (direct path), each row is
    classified inside the guarded loop; otherwise the row's pre-set status (from a
    confirmed draft) is used. INVALID rows are skipped; the rest are upserted (the
    DB uniqueness + upsert_candidate remain the authoritative write path).
    Running counts are checkpointed every PROGRESS_FLUSH_EVERY rows so History
    reflects progress even if the process is killed mid-import. Finalizes the batch
    COMPLETED, or FAILED (re-raising) on an unexpected error."""
    report = {"ok": True, "batch_id": batch.batch_id, "header_row": batch.header_row,
              "created": 0, "updated": 0, "possible_duplicates": [], "skipped": [],
              "warnings": [], "rows": [], "duplicate_file": duplicate_file}
    count_fields = ["created_count", "updated_count", "duplicate_count", "skipped_count"]

    def _record_row(p, status_, errors=None):
        report["rows"].append({
            "excel_row": p["excel_row"], "name": p["name"], "mobile": p["mobile"], "email": p["email"],
            "status": status_, "errors": errors or [], "warnings": p.get("warnings") or [],
        })

    def _apply_counts():
        batch.created_count = report["created"]
        batch.updated_count = report["updated"]
        batch.duplicate_count = len(report["possible_duplicates"])
        batch.skipped_count = len(report["skipped"])

    # Record the total upfront so History shows "N of total" even mid-run.
    batch.total_rows = len(prepared)
    batch.save(update_fields=["total_rows"])

    try:
        for i, p in enumerate(prepared, start=1):
            excel_row = p["excel_row"]
            if classify_index is not None:  # direct path — classify now (inside the guard)
                p["status"] = _classify_row(p, classify_index)[0]
            if p["status"] == ROW_INVALID:
                report["skipped"].append({"row": excel_row, "errors": p.get("errors") or []})
                _record_row(p, ROW_INVALID, p.get("errors") or [])
            else:
                data = dict(p["data"])
                if source is not None:
                    data["source"] = source
                if p.get("warnings"):
                    report["warnings"].append({"row": excel_row, "messages": p["warnings"]})
                try:
                    result = upsert_candidate(data=data, user=user, requirement=requirement)
                    action = result["action"]
                    if action == CREATED:
                        cand = result["candidate"]           # stamp batch on NEW rows (rollback anchor)
                        cand.import_batch = batch
                        cand.save(update_fields=["import_batch"])
                        report["created"] += 1
                        _record_row(p, "CREATED")
                    elif action == UPDATED:
                        report["updated"] += 1
                        _record_row(p, "UPDATED")
                    else:  # POSSIBLE_DUPLICATE → Admin review queue (deduped)
                        existing_cand = result["candidate"]
                        record_possible_duplicate(
                            existing_candidate=existing_cand,
                            new_candidate_name=data.get("candidate_name"),
                            new_mobile=data.get("mobile"),
                            new_email=data.get("email"),
                            detection_reason=f"Bulk upload (batch {batch.batch_uid}, row {excel_row}) — same mobile, different email",
                            submitted_payload={
                                "source": "bulk_upload", "batch": batch.batch_uid, "batch_id": batch.batch_id, "row": excel_row,
                                "uploaded_by": getattr(user, "user_id", None),
                                "candidate_name": data.get("candidate_name"),
                                "mobile": data.get("mobile"), "email": data.get("email"),
                                "current_company": data.get("current_company"),
                            },
                            user=user,
                        )
                        report["possible_duplicates"].append(
                            {"row": excel_row, "mobile": data.get("mobile"), "existing_cv_serial": existing_cand.cv_serial})
                        _record_row(p, ROW_DUPLICATE)
                except Exception as exc:  # noqa: BLE001 — report per-row, keep going
                    report["skipped"].append({"row": excel_row, "errors": [str(exc)]})
                    _record_row(p, "ERROR", [str(exc)])
            if i % PROGRESS_FLUSH_EVERY == 0:  # periodic progress checkpoint
                _apply_counts()
                batch.save(update_fields=count_fields)

        _apply_counts()
        batch.row_report = report["rows"]
        batch.status = "COMPLETED"
        batch.completed_on = timezone.now()
        batch.save()
    except Exception as exc:  # noqa: BLE001 — never leave the batch PENDING
        batch.status = "FAILED"
        batch.error_message = str(exc)[:2000]
        batch.completed_on = timezone.now()
        _apply_counts()  # persist progress made before the failure
        try:
            batch.save(update_fields=["status", "error_message", "completed_on"] + count_fields)
        except Exception:  # noqa: BLE001 — best-effort; don't mask the original error
            logger.exception("Could not mark batch %s FAILED", batch.batch_id)
        logger.exception("Bulk import batch %s failed", batch.batch_id)
        raise

    logger.info(
        "Bulk import by user %s (batch %s / id %s): +%d created, %d updated, %d possible-dupes, %d skipped",
        getattr(user, "user_id", None), batch.batch_uid, batch.batch_id, report["created"], report["updated"],
        len(report["possible_duplicates"]), len(report["skipped"]),
    )
    return report


def import_candidates_excel(*, file, user, requirement=None, source=None) -> dict:
    """Direct import from an uploaded file (legacy / fallback path — the UI now
    previews then confirms a draft, see confirm_import_batch). Parses, classifies,
    creates a PENDING batch, and runs the shared import loop."""
    import uuid, hashlib, io
    from admin_module.models import BulkImportBatch
    batch_uid = uuid.uuid4().hex[:12]

    raw = file.read() if hasattr(file, "read") else file
    if isinstance(raw, str):  # a path was passed (e.g. tests) — read its bytes
        with open(raw, "rb") as fh:
            raw = fh.read()
    file_hash = hashlib.sha256(raw).hexdigest()

    try:
        header_row, cols, comment_idxs, parsed = _parse_bulk_file(io.BytesIO(raw), max_rows=BULK_MAX_ROWS)
    except BulkParseError as exc:
        return {"ok": False, "error": str(exc),
                "created": 0, "updated": 0, "possible_duplicates": [], "skipped": [], "warnings": [], "rows": []}
    if header_row is None:
        return {"ok": False,
                "error": "Could not find the candidate header row. Use the sample template.",
                "created": 0, "updated": 0, "possible_duplicates": [], "skipped": [], "warnings": [], "rows": []}
    if len(parsed) > BULK_MAX_ROWS:
        return {"ok": False,
                "error": f"File exceeds the {BULK_MAX_ROWS}-row limit. Split it into smaller files.",
                "created": 0, "updated": 0, "possible_duplicates": [], "skipped": [], "warnings": [], "rows": []}

    index = _build_existing_index(parsed)
    batch = BulkImportBatch.objects.create(
        batch_uid=batch_uid, uploaded_by=user,
        file_name=(getattr(file, "name", None) or None), file_hash=file_hash,
        source=source, requirement=requirement, header_row=header_row,
        status="PENDING", created_on=timezone.now(),
    )
    # Classify inside the guarded loop (a classify/parse failure marks the batch
    # FAILED rather than leaving it PENDING).
    return _execute_import(batch=batch, prepared=parsed, user=user, requirement=requirement, source=source,
                           classify_index=index,
                           duplicate_file=_duplicate_file_batch(file_hash, exclude_batch_id=batch.batch_id))


# ---------------------------------------------------------------------------
# Draft → confirm flow (Feature 5a) — import operates on the SAME validated data
# ---------------------------------------------------------------------------
DRAFT_TTL_HOURS = getattr(settings, "BULK_DRAFT_TTL_HOURS", 24)


def _create_draft_batch(*, user, file, file_hash, header_row, parsed):
    """Persist the validated preview as a DRAFT batch so import can confirm this
    exact dataset without re-parsing. Supersedes a prior DRAFT for the same
    user+file (re-previews don't pile up). Returns the batch."""
    import uuid
    from admin_module.models import BulkImportBatch
    # Supersede earlier drafts of the same file by the same user.
    BulkImportBatch.objects.filter(uploaded_by=user, file_hash=file_hash, status="DRAFT").delete()
    draft_rows = [{
        "excel_row": p["excel_row"], "name": p["name"], "mobile": p["mobile"], "email": p["email"],
        "status": p["status"], "errors": p["errors"], "warnings": p["warnings"],
        # Only importable rows carry the serialized candidate payload.
        "payload": (_serialize_row_data(p["data"]) if p["status"] != ROW_INVALID else None),
    } for p in parsed]
    return BulkImportBatch.objects.create(
        batch_uid=uuid.uuid4().hex[:12], uploaded_by=user,
        file_name=(getattr(file, "name", None) or None), file_hash=file_hash,
        header_row=header_row, total_rows=len(parsed), status="DRAFT",
        row_report=draft_rows, created_on=timezone.now(),
    )


def confirm_import_batch(*, batch, user, source=None, requirement=None) -> dict:
    """Confirm a DRAFT batch: import the exact validated rows captured at preview
    (no file, no re-parse). Reconstructs each row's candidate kwargs from the
    stored payload and runs the shared import loop; the DB uniqueness + upsert
    remain authoritative, so a row that became a duplicate since preview is still
    handled correctly. `source`/`requirement` are chosen now, at confirm.

    NOT wrapped in one transaction — each row upserts independently (partial
    success), matching the direct path. The DRAFT→PENDING move is an atomic
    conditional claim so a concurrent / double confirm can't import twice."""
    from admin_module.models import BulkImportBatch
    claimed = (BulkImportBatch.objects
               .filter(batch_id=batch.batch_id, status="DRAFT")
               .update(status="PENDING", source=source, requirement=requirement))
    if not claimed:
        return {"ok": False, "error": "This draft was already used — re-run the preview.",
                "created": 0, "updated": 0, "possible_duplicates": [], "skipped": [], "warnings": [], "rows": []}
    batch.refresh_from_db()  # reflect the claim (status / source / requirement)

    loc_by_id = {loc.location_id: loc for loc in LocationMaster.objects.all()}
    prepared = []
    for r in (batch.row_report or []):
        prepared.append({
            "excel_row": r.get("excel_row"), "name": r.get("name"), "mobile": r.get("mobile"),
            "email": r.get("email"), "status": r.get("status"),
            "errors": r.get("errors") or [], "warnings": r.get("warnings") or [],
            "data": _deserialize_row_data(r["payload"], loc_by_id) if r.get("payload") else {},
        })
    return _execute_import(batch=batch, prepared=prepared, user=user, requirement=requirement, source=source,
                           duplicate_file=_duplicate_file_batch(batch.file_hash, exclude_batch_id=batch.batch_id))


def purge_stale_draft_batches(older_than_hours=DRAFT_TTL_HOURS):
    """Delete DRAFT batches older than the TTL (they created no candidates, so a
    hard delete is safe). Returns the count. Runs in the daily maintenance job."""
    import datetime as _dt
    from admin_module.models import BulkImportBatch
    cutoff = timezone.now() - _dt.timedelta(hours=older_than_hours)
    stale = BulkImportBatch.objects.filter(status="DRAFT", created_on__lt=cutoff)
    count = stale.count()
    if count:
        stale.delete()
        logger.info("Purged %d stale DRAFT import batch(es)", count)
    return count


# ---------------------------------------------------------------------------
# Import-batch rollback (soft delete of candidates this batch CREATED)
# ---------------------------------------------------------------------------
@transaction.atomic
def rollback_import_batch(*, batch, user) -> dict:
    """Reverse ONLY the candidates this batch CREATED and that are still untouched
    (global status NEW_CV and NOT in any requirement pipeline) by soft-deleting
    them (is_active=False). Candidates the batch merely UPDATED are NEVER reversed
    — an update has no pre-import snapshot to restore — and neither are created
    candidates that have since been worked; both are reported as kept. Marks the
    batch ROLLED_BACK. Returns {"removed": [...cv_serials], "kept": [{cv_serial,
    reason}], "updated_not_reversed": <count>, counts}.

    Atomic + guarded: only a COMPLETED batch can be rolled back, and the
    soft-deletes + terminal status flip commit together (a crash mid-loop can't
    leave some candidates deleted while the batch still reads COMPLETED)."""
    if batch.status != "COMPLETED":
        from rest_framework.exceptions import ValidationError
        raise ValidationError(
            {"detail": [f"Only a completed import can be rolled back (this batch is {batch.status})."]})
    created = CandidateMaster.objects.filter(import_batch=batch, is_active=True)
    mapped_ids = set(
        JdCvMapping.objects.filter(candidate__import_batch=batch).values_list("candidate_id", flat=True)
    )
    removed, kept, now = [], [], timezone.now()
    for c in created:
        status_code = c.candidate_status.status_code if c.candidate_status_id else None
        if c.cv_id in mapped_ids:
            kept.append({"cv_serial": c.cv_serial, "reason": "in a requirement pipeline"})
            continue
        if status_code != CandidateStatus.NEW_CV:
            kept.append({"cv_serial": c.cv_serial, "reason": f"status is {status_code} (worked)"})
            continue
        c.is_active = False
        c.updated_by = user
        c.updated_on = now
        c.save(update_fields=["is_active", "updated_by", "updated_on"])
        removed.append(c.cv_serial)

    batch.status = "ROLLED_BACK"
    batch.completed_on = now
    batch.save(update_fields=["status", "completed_on"])
    logger.info("Batch %s rolled back by user %s: %d removed, %d kept",
                batch.batch_id, getattr(user, "user_id", None), len(removed), len(kept))
    return {"removed": removed, "kept": kept,
            "removed_count": len(removed), "kept_count": len(kept),
            # Candidates this batch UPDATED are intentionally NOT reversed.
            "updated_not_reversed": batch.updated_count}


# ---------------------------------------------------------------------------
# Recovery — never leave a batch stuck in PENDING
# ---------------------------------------------------------------------------
STALE_IMPORT_MINUTES = 30  # a PENDING batch older than this is presumed crashed


def fail_stale_import_batches(older_than_minutes=STALE_IMPORT_MINUTES):
    """Recovery sweep for PENDING batches whose process died before finalizing
    (server crash / kill) and therefore couldn't self-mark FAILED. Marks any
    PENDING batch created more than `older_than_minutes` ago as FAILED. Only ever
    touches still-PENDING rows, so it's safe/idempotent. Returns the count."""
    import datetime as _dt
    from admin_module.models import BulkImportBatch
    cutoff = timezone.now() - _dt.timedelta(minutes=older_than_minutes)
    stale = BulkImportBatch.objects.filter(status="PENDING", created_on__lt=cutoff)
    count = stale.count()
    if count:
        stale.update(
            status="FAILED",
            error_message="Marked FAILED by recovery — import did not complete (stale PENDING).",
            completed_on=timezone.now(),
        )
        logger.warning("Recovery: marked %d stale PENDING import batch(es) FAILED", count)
    return count


# ---------------------------------------------------------------------------
# Location reconciliation — link import "kept as text" locations to the master
# ---------------------------------------------------------------------------
def unmapped_location_summary():
    """Distinct current_location_text values still unmapped (Location FK is NULL),
    with candidate counts and a SUGGESTED Location Master match (alias map +
    case-insensitive). Never creates a master row."""
    from django.db.models import Count
    rows = (
        CandidateMaster.objects
        .filter(current_location__isnull=True, current_location_text__isnull=False)
        .exclude(current_location_text="")
        .values("current_location_text")
        .annotate(count=Count("cv_id"))
        .order_by("-count", "current_location_text")
    )
    loc_cache = _location_cache()
    out = []
    for r in rows:
        text = r["current_location_text"]
        obj, _ = _resolve_location(text, loc_cache)
        out.append({
            "text": text,
            "count": r["count"],
            "suggested_location_id": obj.location_id if obj else None,
            "suggested_city": (f"{obj.city}, {obj.state}" if obj else None),
        })
    return out


@transaction.atomic
def reconcile_location(*, text, location, user):
    """Map every still-unmapped candidate whose current_location_text == `text` to
    `location` (set the FK, clear the text). Only touches rows with a NULL FK, so
    it never overrides a manually-set location. Returns the number reconciled."""
    qs = CandidateMaster.objects.filter(current_location__isnull=True, current_location_text=text)
    n = qs.count()
    if n:
        qs.update(current_location=location, current_location_text=None,
                  updated_by=user, updated_on=timezone.now())
        logger.info("Reconciled %d candidate(s): location text '%s' -> %s (user %s)",
                    n, text, location.city, getattr(user, "user_id", None))
    return n


# ---------------------------------------------------------------------------
# Candidate lifecycle automation (Reject-Hold / Joined retention)
# ---------------------------------------------------------------------------
REJECT_HOLD_THRESHOLD = 2       # active rejections that trigger a hold
REJECT_HOLD_MONTHS = 6          # cool-off window
JOINED_RETENTION_MONTHS = 24    # a joined candidate returns to the pool after 2 years

# Application outcomes that return a candidate to the Talent Pool WITHOUT counting
# as a formal rejection.
_TALENT_POOL_OUTCOMES = {
    ApplicationStatus.DROPPED, ApplicationStatus.NO_RESPONSE,
    ApplicationStatus.WITHDRAWN, ApplicationStatus.NOT_SUITABLE,
    ApplicationStatus.OFFER_DECLINED,
    # System requirement-closure outcomes: when a requirement reaches an
    # irreversible terminal state (or an expired partial-filled requirement ends
    # recruitment), its remaining candidates are freed back to the Talent Pool.
    ApplicationStatus.REQ_CLOSE_FILLED, ApplicationStatus.REQ_POSITIONS_WITHDRAWN,
    ApplicationStatus.REQ_CLOSE_LOST,
}


def _add_months(d, months):
    """Month-accurate date offset (no external deps)."""
    import calendar
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


def _candidate_status(code):
    return CandidateStatusMaster.objects.get(status_code=code)


def _log_candidate(candidate, comment, user):
    """Append a candidate-level status-change event to the timeline (history)."""
    CandidateInteraction.objects.create(
        candidate=candidate, req=None, interaction_type=InteractionType.STATUS_CHANGE,
        comment=comment, created_by=user, created_on=timezone.now(),
    )


@transaction.atomic
def apply_application_outcome(*, candidate, outcome, user, move_to_talent_pool=False):
    """SINGLE source of candidate GLOBAL-status automation, driven by an
    application's outcome. The application keeps its own (per-requirement) outcome;
    this only moves the candidate's global disposition:
      Joined              → Joined (+joined_date)                         [automatic]
      Fake / Blacklisted  → Fake / Blacklisted                           [automatic]
      Rejected            → active_rejection_count += 1; at the 2nd active
                            rejection → Reject Hold (+dates)              [automatic]
      Non-hired closing outcomes (No Response / Dropped / Not Suitable /
        Offer Declined / Withdrawn, and single Rejections) → **Talent Pool ONLY IF
        the recruiter chose it** (move_to_talent_pool); otherwise unchanged.
    Hard dispositions (Fake/Blacklisted) and an already-Joined candidate are never
    overridden. Every change is appended to the candidate timeline."""
    current = candidate.candidate_status.status_code if candidate.candidate_status_id else None
    if current in (CandidateStatus.FAKE, CandidateStatus.BLACKLISTED):
        return candidate
    if current == CandidateStatus.JOINED and outcome != ApplicationStatus.JOINED:
        return candidate

    now = timezone.now()
    today = now.date()
    fields = ["last_status_changed_on", "updated_by", "updated_on"]
    note = None

    def _set_status(code):
        candidate.candidate_status = _candidate_status(code)
        fields.append("candidate_status")

    if outcome == ApplicationStatus.JOINED:
        _set_status(CandidateStatus.JOINED)
        candidate.joined_date = today
        fields.append("joined_date")
        note = "Joined — status set to Joined."
    elif outcome == CandidateStatus.FAKE:
        _set_status(CandidateStatus.FAKE)
        note = "Marked Fake."
    elif outcome == CandidateStatus.BLACKLISTED:
        _set_status(CandidateStatus.BLACKLISTED)
        note = "Marked Blacklisted."
    elif outcome == ApplicationStatus.REJECTED:
        # Atomic DB-side increment (not read-modify-write): the UPDATE takes a
        # row lock, so two concurrent rejections of the same candidate both
        # count — a lost update here would silently defeat the Reject-Hold
        # cool-off. Re-read the committed value to decide the threshold.
        from django.db.models import F
        CandidateMaster.objects.filter(pk=candidate.pk).update(
            active_rejection_count=F("active_rejection_count") + 1)
        candidate.refresh_from_db(fields=["active_rejection_count"])
        n = candidate.active_rejection_count
        if n >= REJECT_HOLD_THRESHOLD:
            _set_status(CandidateStatus.REJECT_HOLD)
            candidate.reject_hold_start = today
            candidate.reject_hold_until = _add_months(today, REJECT_HOLD_MONTHS)
            fields += ["reject_hold_start", "reject_hold_until"]
            note = f"Rejected (rejection #{n}) — placed on Reject Hold until {candidate.reject_hold_until}."
        elif move_to_talent_pool:
            _set_status(CandidateStatus.SAVED)
            note = f"Rejected (rejection #{n}) — moved to Talent Pool."
        else:
            note = f"Rejected (rejection #{n})."  # global status unchanged; counter recorded
    elif outcome in _TALENT_POOL_OUTCOMES:
        # Return to the Talent Pool, but never silently cancel an active Reject-Hold
        # cool-off (a system requirement-closure must not release a held candidate).
        if move_to_talent_pool and current != CandidateStatus.REJECT_HOLD:
            _set_status(CandidateStatus.SAVED)
            note = f"{outcome.replace('_', ' ').title()} — moved to Talent Pool."
        else:
            return candidate  # keep current global status (incl. an active Reject-Hold)
    else:
        return candidate  # non-terminal / advancing → candidate status unchanged

    candidate.last_status_changed_on = now
    candidate.updated_by = user
    candidate.updated_on = now
    candidate.save(update_fields=list(dict.fromkeys(fields)))
    if note:
        _log_candidate(candidate, note, user)
    return candidate


def run_lifecycle_maintenance(as_of=None):
    """Daily job: return candidates whose Reject-Hold has elapsed (6 months) or
    who Joined over 2 years ago back to the Talent Pool. Resetting the rejection
    counter does NOT erase history. Idempotent per day. Returns a summary."""
    today = as_of or timezone.now().date()
    now = timezone.now()
    saved = _candidate_status(CandidateStatus.SAVED)
    released_holds = released_joins = 0

    for cand in CandidateMaster.objects.filter(
        candidate_status__status_code=CandidateStatus.REJECT_HOLD,
        reject_hold_until__isnull=False, reject_hold_until__lte=today,
    ):
        cand.candidate_status = saved
        cand.active_rejection_count = 0
        cand.reject_hold_start = None
        cand.reject_hold_until = None
        cand.last_status_changed_on = now
        cand.updated_on = now
        cand.save(update_fields=["candidate_status", "active_rejection_count",
                                 "reject_hold_start", "reject_hold_until",
                                 "last_status_changed_on", "updated_on"])
        _log_candidate(cand, "Reject Hold elapsed — returned to Talent Pool (rejection count reset).", None)
        released_holds += 1

    for cand in CandidateMaster.objects.filter(
        candidate_status__status_code=CandidateStatus.JOINED, joined_date__isnull=False,
    ):
        if _add_months(cand.joined_date, JOINED_RETENTION_MONTHS) <= today:
            cand.candidate_status = saved
            cand.last_status_changed_on = now
            cand.updated_on = now
            cand.save(update_fields=["candidate_status", "last_status_changed_on", "updated_on"])
            _log_candidate(cand, "2 years since joining — returned to Talent Pool.", None)
            released_joins += 1

    # Recover batches stuck PENDING from a crashed run, and purge expired DRAFTs.
    stale_batches = fail_stale_import_batches()
    purged_drafts = purge_stale_draft_batches()

    logger.info("Candidate lifecycle maintenance: %d holds released, %d joins released, "
                "%d stale batches failed, %d stale drafts purged",
                released_holds, released_joins, stale_batches, purged_drafts)
    return {"reject_hold_released": released_holds, "joined_released": released_joins,
            "stale_import_batches_failed": stale_batches, "stale_draft_batches_purged": purged_drafts}
