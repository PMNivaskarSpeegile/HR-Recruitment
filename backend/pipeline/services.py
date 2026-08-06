"""
Pipeline domain logic (UC3+).

Owns the jd_cv_mapping lifecycle: which candidates surface for review, and what
happens to the mapping + the candidate's global status when a recruiter acts.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from admin_module.models import (
    ApplicationStatusMaster,
    CandidateInteraction,
    CandidateMaster,
    CandidateStatusMaster,
    CommunicationLog,
    EmailTemplateMaster,
    JdCvMapping,
    RequirementPosition,
    StatusChangeHistory,
)
from core.constants import (
    ApplicationStatus,
    AuditEntity,
    CandidateStatus,
    ChangeType,
    InteractionType,
    PositionStatus,
)
from core.timeutils import to_local_naive

logger = logging.getLogger("ats")

# The Review action is the initial *resume review* only — Shortlist or Not
# Suitable. Candidate-disposition actions (Fake / Save) are a different concept
# handled elsewhere and are intentionally NOT part of Review.
DECISION_SHORTLISTED = "SHORTLISTED"
DECISION_NOT_SUITABLE = "NOT_SUITABLE"
REVIEW_DECISIONS = [DECISION_SHORTLISTED, DECISION_NOT_SUITABLE]

# Each review decision sets the application stage — the SINGLE source of truth
# for the candidate's progress on this requirement.
_REVIEW = {
    DECISION_SHORTLISTED: ApplicationStatus.SHORTLISTED,
    DECISION_NOT_SUITABLE: ApplicationStatus.NOT_SUITABLE,
}


def _app_status(code):
    return ApplicationStatusMaster.objects.get(status_code=code)


def _cand_status(code):
    return CandidateStatusMaster.objects.get(status_code=code)


def _set_mapping_status(mapping, code):
    mapping.application_stage = _app_status(code)


def _set_candidate_status(candidate, code):
    candidate.candidate_status = _cand_status(code)


def _mapping_current(mapping):
    """The mapping's live pipeline status_code."""
    return mapping.application_stage.status_code if mapping.application_stage_id else None


def _log(candidate, requirement, comment, user):
    CandidateInteraction.objects.create(
        candidate=candidate, req=requirement,
        interaction_type=InteractionType.STATUS_CHANGE,
        comment=comment, created_by=user, created_on=timezone.now(),
    )


# A candidate is "usable" (reviewable / reusable) while their global record
# status is New_CV or Saved. Fake / Possible Duplicate are excluded.
USABLE_CANDIDATE_STATUSES = (CandidateStatus.NEW_CV, CandidateStatus.SAVED)


def new_cv_candidates_for_requirement(requirement):
    """Review Pool for a requirement: candidates EXPLICITLY tagged as "under
    review" for it (candidate_requirement_review, status ACTIVE). Membership is the
    explicit tag — NEVER skill matching — and is separate from jd_cv_mapping
    (pipeline entry). A candidate already shortlisted for this requirement (has a
    mapping) is excluded defensively; Fake/Blacklisted are excluded globally.

    Skill overlap with the requirement is kept ONLY as a ranking signal within the
    already-tagged set (`matched_skills`, best-match-first)."""
    from admin_module.models import CandidateRequirementReview
    from core.constants import ReviewStatus
    req_skill_ids = [s for s in (requirement.skill1_id, requirement.skill2_id, requirement.skill3_id) if s]
    tagged_ids = (
        CandidateRequirementReview.objects
        .filter(req=requirement, status=ReviewStatus.ACTIVE)
        .values_list("candidate_id", flat=True)
    )
    already_mapped = JdCvMapping.objects.filter(req=requirement).values_list("candidate_id", flat=True)
    return (
        CandidateMaster.objects
        .filter(cv_id__in=tagged_ids)
        .filter(candidate_status__status_code__in=USABLE_CANDIDATE_STATUSES)
        .exclude(cv_id__in=already_mapped)
        .annotate(matched_skills=Count(
            "candidateskill", filter=Q(candidateskill__skill_id__in=req_skill_ids), distinct=True
        ))
        .select_related("candidate_status", "current_location", "notice_period", "work_mode", "source", "uploaded_by")
        .prefetch_related("candidateskill_set__skill")
        .order_by("-matched_skills", "cv_id")
    )


@transaction.atomic
def review_candidate(*, requirement, candidate, decision, comments, user, rejection_reason=None):
    """Apply a recruiter's initial resume-review decision (Shortlist / Not
    Suitable) by setting the application stage — the single source of truth for
    progress — Shortlist → stage 'Shortlisted'; Not Suitable → stage 'Not
    Suitable' (closed). A rejection reason applies to Not Suitable. The candidate
    stays in the pool (global status Saved) — a per-req decision never changes the
    candidate's global disposition. Returns the created/updated JdCvMapping."""
    now = timezone.now()
    stage_code = _REVIEW[decision]
    reason = rejection_reason if decision == DECISION_NOT_SUITABLE else None

    mapping, created = JdCvMapping.objects.get_or_create(
        req=requirement, candidate=candidate,
        defaults={
            "application_stage": _app_status(stage_code),
            "comments": comments, "rejection_reason": reason,
            "is_active": True, "created_by": user, "created_on": now,
        },
    )
    if not created:
        mapping.application_stage = _app_status(stage_code)
        mapping.comments = comments
        mapping.rejection_reason = reason
        mapping.updated_by = user
        mapping.updated_on = now
        mapping.save()

    # Reviewing for one requirement keeps the candidate available in the pool.
    _set_candidate_status(candidate, CandidateStatus.SAVED)
    candidate.updated_by = user
    candidate.updated_on = now
    candidate.save(update_fields=["candidate_status", "updated_by", "updated_on"])

    # Event-driven requirement status: the first candidate linked opens a
    # New/Assigned requirement (no-op once already Open / beyond).
    if created:
        from requirements.services import open_requirement_on_first_link
        open_requirement_on_first_link(requirement, user)

    verdict_label = "Shortlisted" if decision == DECISION_SHORTLISTED else "Not Suitable"
    _log(candidate, requirement, f"CV review: {verdict_label}. {comments or ''}".strip(), user)
    logger.info("Candidate %s reviewed %s on req %s", candidate.cv_serial, decision, requirement.req_tracker_no)
    return mapping


# ===========================================================================
#  UC4 — JD email templating
# ===========================================================================
#
# The email body/subject live in email_template_master (admin-editable, never
# hardcoded). ONE pair of functions — _build_jd_context + _render — powers both
# the preview and the actual send, so "what you preview is what's sent".

JD_TEMPLATE_CODE = "JD_EMAIL"


class TemplateNotConfigured(Exception):
    """Raised when the required email template is missing or inactive."""


def get_jd_template():
    """Load the active JD email template. Admins manage it via the
    email-templates master endpoint."""
    try:
        return EmailTemplateMaster.objects.get(template_code=JD_TEMPLATE_CODE, is_active=True)
    except EmailTemplateMaster.DoesNotExist:
        raise TemplateNotConfigured(
            f"No active email template '{JD_TEMPLATE_CODE}'. Ask an Admin to configure it."
        )


def _fmt_range(lo, hi, suffix=""):
    """Render a min/max pair as '3-5 yrs', '5+ yrs', or '' when both are blank."""
    if lo is None and hi is None:
        return ""
    if lo is not None and hi is not None:
        return f"{lo:g}-{hi:g}{suffix}"
    one = lo if lo is not None else hi
    return f"{one:g}+{suffix}" if lo is not None else f"up to {one:g}{suffix}"


def _build_jd_context(requirement, *, candidate_name, sender_name):
    """Map a requirement + recipient into the placeholder values the JD template
    expects. Missing values render as '' rather than 'None'."""
    skills = [s.skill_name for s in (requirement.skill1, requirement.skill2, requirement.skill3) if s]
    loc = requirement.location
    return {
        "candidate_name": candidate_name or "Candidate",
        "role": requirement.jd_role_name or "",
        "client": requirement.client.client_name if requirement.client_id else "",
        "location": loc.city if loc else "",
        "exp": _fmt_range(requirement.exp_min, requirement.exp_max, " yrs"),
        "ctc": f"{requirement.jd_rate_lpa:g} LPA" if requirement.jd_rate_lpa is not None else "",
        "notice": requirement.np.np_name if requirement.np_id else "",
        "skills": ", ".join(skills),
        "sender": sender_name or "",
    }


def _render(text, ctx):
    """Substitute {placeholder} tokens. Unknown placeholders are left intact so a
    template typo is visible rather than crashing the send."""
    out = text or ""
    for key, value in ctx.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def render_jd_email(template, requirement, *, candidate_name, sender_name):
    """Return the rendered (subject, body) for one recipient."""
    ctx = _build_jd_context(requirement, candidate_name=candidate_name, sender_name=sender_name)
    return _render(template.subject, ctx), _render(template.body, ctx)


def preview_jd_emails(*, requirement, mapping_ids, user):
    """UC4 — render (without sending) the JD email for each SHORTLISTED mapping so
    the recruiter sees exactly what will go out. Returns the template plus a
    per-recipient list."""
    template = get_jd_template()
    sender_name = getattr(user, "full_name", "") or getattr(user, "username", "")
    mappings = mappings_for_requirement(requirement, status_code=ApplicationStatus.SHORTLISTED).filter(
        mapping_id__in=mapping_ids
    )
    items = []
    for m in mappings:
        subject, body = render_jd_email(
            template, requirement, candidate_name=m.candidate.candidate_name, sender_name=sender_name
        )
        items.append({
            "mapping_id": m.mapping_id,
            "candidate_name": m.candidate.candidate_name,
            "recipient": m.candidate.email,
            "subject": subject,
            "body": body,
        })
    return {
        "template_id": template.template_id,
        "template_code": template.template_code,
        "subject_template": template.subject,
        "body_template": template.body,
        "recipients": items,
    }


def communications_for_requirement(requirement):
    """The JD email tracker: every send attempt logged for a requirement,
    newest first."""
    return (
        CommunicationLog.objects
        .filter(req=requirement)
        .select_related("candidate", "sent_by")
        .order_by("-sent_on", "-comm_id")
    )


# ===========================================================================
#  UC4 / UC5 — post-shortlist pipeline: the centralized Stage × Outcome engine
# ===========================================================================
#
# STAGE and OUTCOME are independent. jd_cv_mapping.application_stage holds the
# STAGE (where the candidate is); latest_outcome holds the last recorded OUTCOME;
# is_closed marks a terminal (closing) outcome. This module is the SINGLE place
# that mutates pipeline state — views/verify/back-compat all route through it.
#
# Effect of each outcome, keyed by the stage it's recorded at:
#   (ADVANCE, next_stage)             → move to next_stage, record the outcome
#   (CLOSE,   candidate_outcome|None) → close the application, record the outcome,
#                                       and drive the candidate's GLOBAL status
A = ApplicationStatus
ADVANCE, CLOSE = "ADVANCE", "CLOSE"

STAGE_OUTCOMES = {
    A.JD_EMAIL_SENT: {
        # Only "Drop" is a manual close here; a candidate who doesn't respond is
        # dropped (no separate No Response outcome at this stage — see diagram).
        A.DROPPED: (CLOSE, A.DROPPED),
    },
    A.SCREENING_SCHEDULED: {
        A.PASSED: (ADVANCE, A.OK_TO_PROCEED),
        A.REJECTED: (CLOSE, A.REJECTED),
        A.NO_RESPONSE: (CLOSE, A.NO_RESPONSE),
        A.DROPPED: (CLOSE, A.DROPPED),
        A.FAKE: (CLOSE, A.FAKE),
        A.BLACKLISTED: (CLOSE, A.BLACKLISTED),
    },
    A.OK_TO_PROCEED: {
        # Client Interview Outcome: advance via Release Offer, or close.
        # Blacklisted is not offered here (candidate-integrity flag lives at the
        # earlier candidate-validation / screening stages — see diagram).
        A.REJECTED: (CLOSE, A.REJECTED),
        A.DROPPED: (CLOSE, A.DROPPED),
        A.FAKE: (CLOSE, A.FAKE),
    },
    A.OFFERED: {
        A.OFFER_ACCEPTED: (ADVANCE, A.AWAITING_JOINING),
        A.OFFER_DECLINED: (CLOSE, A.OFFER_DECLINED),
    },
    A.AWAITING_JOINING: {
        A.JOINED: (CLOSE, A.JOINED),
        A.WITHDRAWN: (CLOSE, A.WITHDRAWN),
    },
}

# Advancing ACTIONS (buttons with side-effects) — (from_stage, to_stage).
SEND_JD, SCHEDULE_SCREENING, RELEASE_OFFER = "SEND_JD", "SCHEDULE_SCREENING", "RELEASE_OFFER"
STAGE_ACTIONS = {
    SEND_JD: (A.SHORTLISTED, A.JD_EMAIL_SENT),
    SCHEDULE_SCREENING: (A.JD_EMAIL_SENT, A.SCREENING_SCHEDULED),
    RELEASE_OFFER: (A.OK_TO_PROCEED, A.OFFERED),
}

# Non-hired closing outcomes eligible for the "Move to Talent Pool?" prompt.
TALENT_POOL_PROMPT_OUTCOMES = set(A.TALENT_POOL_PROMPT_OUTCOMES)


class PipelineError(Exception):
    """An illegal pipeline transition / outcome action."""


def mappings_for_requirement(requirement, status_code=None):
    qs = (
        JdCvMapping.objects
        .filter(req=requirement)
        .select_related("candidate", "application_stage", "latest_outcome", "req")
        .order_by("mapping_id")
    )
    if status_code:
        qs = qs.filter(application_stage__status_code=status_code)
    return qs


def _audit_application(mapping, prev_stage, new_stage, outcome, user, reason, change_type):
    """Append one row to the unified status-change audit for the application."""
    StatusChangeHistory.objects.create(
        entity_type=AuditEntity.APPLICATION, entity_id=mapping.mapping_id,
        previous_status=prev_stage,
        new_status=(outcome or new_stage),
        reason=reason, change_type=change_type, changed_by=user, changed_on=timezone.now(),
    )


def _consume_open_position(requirement, mapping, user):
    """On JOIN, mark one Open seat Filled (linked to the winning application).
    Returns the seat, or None if the requirement has no Open seat left."""
    # Lock the open seat we pick (skip_locked so two concurrent JOINs grab two
    # DIFFERENT seats rather than both reading the same one as OPEN). Runs inside
    # record_outcome's atomic block. Without the lock, two simultaneous joins on
    # a single-seat requirement both pass the over-fill guard and double-fill it.
    seat = (
        RequirementPosition.objects
        .select_for_update(skip_locked=True)
        .filter(req=requirement, position_status__status_code=PositionStatus.OPEN)
        .order_by("position_no")
        .first()
    )
    if not seat:
        return None
    from requirements.positions import set_position_status
    set_position_status(position=seat, to_status_code=PositionStatus.FILLED, user=user,
                        filled_by_mapping=mapping, change_type=ChangeType.AUTO,
                        reason="Candidate joined")
    return seat


@transaction.atomic
def record_outcome(*, mapping, outcome, user, reason=None, rejection_reason=None,
                   move_to_talent_pool=False):
    """THE single write-path for recording a stage OUTCOME on an application.

    Advancing outcomes (Passed → OK to Proceed, Offer Accepted → Awaiting Joining)
    move the stage; closing outcomes (No Response, Rejected, Dropped, Fake,
    Blacklist, Offer Declined, Withdrawn, Joined) close the application and drive
    the candidate's GLOBAL status. Talent Pool is opt-in for non-hired closes
    (move_to_talent_pool). Joined consumes one Open seat (over-fill safe). Raises
    PipelineError on an invalid stage/outcome combination."""
    if mapping.is_closed:
        raise PipelineError("This application is already closed.")
    stage = _mapping_current(mapping)
    allowed = STAGE_OUTCOMES.get(stage, {})
    if outcome not in allowed:
        raise PipelineError(f"'{outcome}' is not a valid outcome at stage '{stage or '—'}'.")

    kind, target = allowed[outcome]
    now = timezone.now()
    seat = None

    if kind == CLOSE and outcome == A.JOINED:
        seat = _consume_open_position(mapping.req, mapping, user)
        if seat is None:
            raise PipelineError("No open position available to fill.")
        mapping.joined_date = now.date()

    if kind == ADVANCE:
        _set_mapping_status(mapping, target)
        mapping.latest_outcome = _app_status(outcome)
    else:  # CLOSE
        mapping.latest_outcome = _app_status(outcome)
        mapping.is_closed = True
        mapping.closed_on = now
        mapping.closed_by = user

    if reason:
        mapping.comments = reason
    if rejection_reason is not None:
        mapping.rejection_reason = rejection_reason
    mapping.updated_by = user
    mapping.updated_on = now
    mapping.save()

    # Candidate GLOBAL-status automation for closing outcomes only.
    if kind == CLOSE and target:
        from candidates.services import apply_application_outcome
        apply_application_outcome(candidate=mapping.candidate, outcome=target,
                                  user=user, move_to_talent_pool=move_to_talent_pool)

    _audit_application(mapping, stage, _mapping_current(mapping), outcome, user, reason, ChangeType.MANUAL)
    note = f"Outcome recorded at {stage}: {outcome}."
    if seat is not None:
        note = f"{note} (filled position #{seat.position_no})"
    _log(mapping.candidate, mapping.req, note, user)
    if outcome == A.JOINED:
        from core.activity import ActivityType, log_activity
        log_activity(
            ActivityType.CANDIDATE_JOINED,
            f"{mapping.candidate.candidate_name} joined · {mapping.req.req_tracker_no} ({mapping.req.jd_role_name})",
            req=mapping.req, candidate=mapping.candidate, actor=user,
        )
    return mapping


@transaction.atomic
def advance_stage(*, mapping, action, user, screening_datetime=None, screening_mode=None, reason=None):
    """Advance a stage via a side-effecting ACTION (Send JD / Schedule Screening /
    Release Offer). Schedule Screening requires a FUTURE datetime. Clears the
    latest_outcome (fresh stage)."""
    if action not in STAGE_ACTIONS:
        raise PipelineError(f"Unknown action '{action}'.")
    src, dst = STAGE_ACTIONS[action]
    if mapping.is_closed or _mapping_current(mapping) != src:
        raise PipelineError(f"'{action}' is not allowed from stage '{_mapping_current(mapping) or '—'}'.")
    if action == SCHEDULE_SCREENING:
        if not screening_datetime:
            raise PipelineError("A screening date and time is required.")
        screening_datetime = to_local_naive(screening_datetime)
        if screening_datetime <= timezone.now():
            raise PipelineError("Screening must be scheduled for a future date and time.")
        mapping.screening_datetime = screening_datetime
        if screening_mode is not None:
            mapping.screening_mode = screening_mode

    _set_mapping_status(mapping, dst)
    mapping.latest_outcome = None
    if reason:
        mapping.comments = reason
    mapping.updated_by = user
    mapping.updated_on = timezone.now()
    mapping.save()
    _audit_application(mapping, src, dst, None, user, reason, ChangeType.MANUAL)
    _log(mapping.candidate, mapping.req, f"{src} -> {dst}. {reason or ''}".strip(), user)
    return mapping


@transaction.atomic
def reschedule_screening(*, mapping, new_datetime, user, screening_mode=None):
    """Reschedule a scheduled screening (stage unchanged). The new time must be in
    the future."""
    if mapping.is_closed or _mapping_current(mapping) != A.SCREENING_SCHEDULED:
        raise PipelineError("Only a scheduled screening can be rescheduled.")
    new_datetime = to_local_naive(new_datetime)
    if not new_datetime or new_datetime <= timezone.now():
        raise PipelineError("Screening must be rescheduled to a future date and time.")
    mapping.screening_datetime = new_datetime
    if screening_mode is not None:
        mapping.screening_mode = screening_mode
    mapping.updated_by = user
    mapping.updated_on = timezone.now()
    mapping.save()
    _audit_application(mapping, A.SCREENING_SCHEDULED, A.SCREENING_SCHEDULED, "RESCHEDULED", user, None, ChangeType.MANUAL)
    _log(mapping.candidate, mapping.req, f"Screening rescheduled to {new_datetime:%d %b %Y %H:%M}", user)
    return mapping


@transaction.atomic
def enter_pipeline(*, requirement, candidate, user, comments=None):
    """Shortlist entry (from Verify & Update): create — or re-open — the mapping at
    the SHORTLISTED stage and keep the candidate in the Talent Pool. Opens a
    New/Assigned requirement on the first link. This is the ONLY way a candidate
    enters the pipeline."""
    mapping, created = JdCvMapping.objects.get_or_create(
        req=requirement, candidate=candidate,
        defaults={"application_stage": _app_status(A.SHORTLISTED), "comments": comments,
                  "is_active": True, "created_by": user, "created_on": timezone.now()},
    )
    prev = None if created else _mapping_current(mapping)
    if not created:
        _set_mapping_status(mapping, A.SHORTLISTED)
        mapping.latest_outcome = None
        mapping.is_closed = False
        mapping.closed_on = None
        mapping.closed_by = None
        if comments:
            mapping.comments = comments
        mapping.updated_by = user
        mapping.updated_on = timezone.now()
        mapping.save()
    _set_candidate_status(candidate, CandidateStatus.SAVED)
    candidate.updated_by = user
    candidate.updated_on = timezone.now()
    candidate.save(update_fields=["candidate_status", "updated_by", "updated_on"])
    if created:
        from requirements.services import open_requirement_on_first_link
        open_requirement_on_first_link(requirement, user)
    _audit_application(mapping, prev, A.SHORTLISTED, None, user, comments, ChangeType.MANUAL)
    _log(candidate, requirement, "Shortlisted — entered the pipeline.", user)
    return mapping


@transaction.atomic
def close_application(*, mapping, outcome, user, reason=None, move_to_talent_pool=False,
                     change_type=ChangeType.MANUAL):
    """Force-close an application with a disposition regardless of stage — used by
    the Verify & Update decision (Not Suitable / Fake / Blacklist), which can close
    a candidate before or during the pipeline, and by the requirement-closure
    cascade (change_type=AUTO). Drives the candidate's GLOBAL status and audits +
    timelines. (In-pipeline dispositions go through record_outcome, which enforces
    the stage machine.)"""
    prev = _mapping_current(mapping)
    mapping.latest_outcome = _app_status(outcome)
    mapping.is_closed = True
    mapping.closed_on = timezone.now()
    mapping.closed_by = user
    if reason:
        mapping.comments = reason
    mapping.updated_by = user
    mapping.updated_on = timezone.now()
    mapping.save()
    from candidates.services import apply_application_outcome
    apply_application_outcome(candidate=mapping.candidate, outcome=outcome, user=user,
                             move_to_talent_pool=move_to_talent_pool)
    _audit_application(mapping, prev, prev, outcome, user, reason, change_type)
    _log(mapping.candidate, mapping.req, f"Application closed: {outcome}.", user)
    return mapping


@transaction.atomic
def close_remaining_applications(*, requirement, outcome, user, reason=None):
    """Auto-close every still-active application on a requirement with a
    system-generated (non-rejection) OUTCOME, returning each candidate to the
    Talent Pool. The single, reused write-path for every requirement-closure
    scenario:
      * CLOSE_FILLED  (rollup) → REQ_CLOSE_FILLED
      * CLOSE_LOST    (manual) → REQ_CLOSE_LOST
      * End Recruitment on an expired PARTIAL_FILLED req → REQ_POSITIONS_WITHDRAWN

    Reuses close_application (sets is_closed/closed_on/closed_by/latest_outcome,
    audit row, timeline, candidate automation). Idempotent: already-closed
    applications are skipped, and any seat-winning (Joined / in-flight join)
    application is excluded so a fill that itself triggers CLOSE_FILLED is never
    clobbered. Returns the number of applications closed."""
    winners = set(
        RequirementPosition.objects
        .filter(req=requirement, filled_by_mapping__isnull=False)
        .values_list("filled_by_mapping_id", flat=True)
    )
    default_reason = "Remaining applications closed automatically on requirement closure."
    closed = 0
    remaining = (
        JdCvMapping.objects
        .filter(req=requirement, is_closed=False)
        .exclude(mapping_id__in=winners)
        .select_related("candidate", "application_stage", "latest_outcome", "req")
    )
    for mapping in remaining:
        close_application(mapping=mapping, outcome=outcome, user=user,
                          reason=reason or default_reason, move_to_talent_pool=True,
                          change_type=ChangeType.AUTO)
        closed += 1
    if closed:
        logger.info("Requirement %s — auto-closed %d remaining application(s) as %s.",
                    requirement.req_tracker_no, closed, outcome)
    return closed


@transaction.atomic
def send_jd_emails(*, requirement, mapping_ids, user):
    """UC4 — email the JD to SHORTLISTED candidates and advance them to
    JD_EMAIL_SENT via the engine. A failed send does not advance the mapping."""
    template = get_jd_template()
    sender_name = getattr(user, "full_name", "") or getattr(user, "username", "")

    mappings = mappings_for_requirement(requirement).filter(mapping_id__in=mapping_ids)
    report = {"sent": 0, "failed": [], "skipped": []}

    for m in mappings:
        current = _mapping_current(m)
        if m.is_closed or current != ApplicationStatus.SHORTLISTED:
            report["skipped"].append({"mapping_id": m.mapping_id, "reason": f"not shortlisted ({current})"})
            continue

        recipient = m.candidate.email
        subject, body = render_jd_email(
            template, requirement, candidate_name=m.candidate.candidate_name, sender_name=sender_name
        )
        error = None
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
            status_str = "SENT"
        except Exception as exc:  # noqa: BLE001 - record and continue
            status_str, error = "FAILED", str(exc)

        CommunicationLog.objects.create(
            candidate=m.candidate, req=requirement, channel="EMAIL", recipient=recipient,
            subject=subject, body=body, status=status_str, error_message=error,
            sent_by=user, sent_on=timezone.now(),
        )

        if status_str == "SENT":
            advance_stage(mapping=m, action=SEND_JD, user=user, reason=f"JD email sent to {recipient}")
            report["sent"] += 1
        else:
            report["failed"].append({"mapping_id": m.mapping_id, "error": error})

    logger.info("Send-JD on %s: %d sent, %d failed, %d skipped",
                requirement.req_tracker_no, report["sent"], len(report["failed"]), len(report["skipped"]))
    return report


# Targets accepted by the generic transition endpoint (kept stable for the
# TransitionInputSerializer + backward compatibility). Each maps to an engine call.
TRANSITION_TARGETS = sorted({
    A.SCREENING_SCHEDULED, A.OK_TO_PROCEED, A.OFFERED, A.AWAITING_JOINING,
    A.JOINED, A.WITHDRAWN, A.OFFER_DECLINED, A.REJECTED, A.DROPPED,
    A.NO_RESPONSE, A.FAKE,
})

# How each legacy `to_status` maps onto the engine.
_TRANSITION_TO_ACTION = {
    A.SCREENING_SCHEDULED: SCHEDULE_SCREENING,
    A.OFFERED: RELEASE_OFFER,
}
_TRANSITION_TO_OUTCOME = {
    A.OK_TO_PROCEED: A.PASSED,
    A.AWAITING_JOINING: A.OFFER_ACCEPTED,
    A.JOINED: A.JOINED,
    A.WITHDRAWN: A.WITHDRAWN,
    A.OFFER_DECLINED: A.OFFER_DECLINED,
    A.REJECTED: A.REJECTED,
    A.DROPPED: A.DROPPED,
    A.NO_RESPONSE: A.NO_RESPONSE,
    A.FAKE: A.FAKE,
}


def transition_mappings(*, requirement, mapping_ids, to_status, comments, screening_datetime, user,
                        screening_mode=None, rejection_reason=None):
    """Backward-compatible batch transition endpoint — a thin router over the
    centralized engine (advance_stage / record_outcome). Same {updated, invalid}
    report shape as before. New code should call the engine functions directly."""
    mappings = mappings_for_requirement(requirement).filter(mapping_id__in=mapping_ids)
    report = {"updated": 0, "invalid": []}
    for m in mappings:
        try:
            if to_status in _TRANSITION_TO_ACTION:
                advance_stage(mapping=m, action=_TRANSITION_TO_ACTION[to_status], user=user,
                              screening_datetime=screening_datetime, screening_mode=screening_mode,
                              reason=comments)
            elif to_status in _TRANSITION_TO_OUTCOME:
                record_outcome(mapping=m, outcome=_TRANSITION_TO_OUTCOME[to_status], user=user,
                               reason=comments, rejection_reason=rejection_reason)
            else:
                raise PipelineError(f"Unsupported transition target '{to_status}'.")
            report["updated"] += 1
        except PipelineError as exc:
            report["invalid"].append({"mapping_id": m.mapping_id, "from": _mapping_current(m),
                                      "to": to_status, "error": str(exc)})
    logger.info("Transition on %s -> %s: %d updated, %d invalid",
                requirement.req_tracker_no, to_status, report["updated"], len(report["invalid"]))
    return report
