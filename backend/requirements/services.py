"""
Business logic for requirements (UC1).

Kept separate from views/serializers so the rules live in one testable place
(SOLID — single responsibility). The view validates input; the service decides
*how* a requirement is created.
"""
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from admin_module.models import RequirementTracker, ReqStatusMaster
from core.constants import ApplicationStatus, AuditEntity, ChangeType, ReqStatus, Roles

logger = logging.getLogger("ats")

_TRACKER_PREFIX = "REQ"
_JD_PREFIX = "JD"
_MAX_RETRIES = 3


class RequirementStatusError(Exception):
    """An illegal (or unauthorised) requirement status transition."""


# Manual status changes a Hiring Manager may perform (Admins are excluded — see
# the view permissions). Everything else is event-driven (create→New,
# assign→Assigned, first candidate link→Open) or system-derived from the
# positions rollup (Partial/Close Filled). Recruiters may not change status.
#   All ACTIVE states (Assigned / Open / Partial Filled) → Hold (pause) | Cancel.
#     A recruiter assignment does not transfer ownership — the HM keeps full
#     lifecycle control across every active state, not just Open.
#   Hold  → Open (resume)  | Cancel
#   Cancelled / Close Lost → Open (reopen — restores the requirement; positions,
#     candidates and history are untouched by a cancel, so nothing is lost)
#   Cancelled / Closed Lost are EXPLICIT Hiring-Manager actions (mandatory
#   reason). Reopen is supported for Cancelled only; Closed Lost is terminal.
MANUAL_REQ_TRANSITIONS = {
    ReqStatus.ASSIGNED: {ReqStatus.HOLD, ReqStatus.CANCELLED, ReqStatus.CLOSE_LOST},
    ReqStatus.OPEN: {ReqStatus.HOLD, ReqStatus.CANCELLED, ReqStatus.CLOSE_LOST},
    # A partially-filled requirement stays WORKABLE (recruiting continues). Ending
    # recruitment on the remaining seats is a separate action (see end_recruitment),
    # available once the requirement is Expired — it does not change the status.
    ReqStatus.PARTIAL_FILLED: {ReqStatus.HOLD, ReqStatus.CANCELLED, ReqStatus.CLOSE_LOST},
    ReqStatus.HOLD: {ReqStatus.OPEN, ReqStatus.CANCELLED, ReqStatus.CLOSE_LOST},
    ReqStatus.CANCELLED: {ReqStatus.OPEN},   # reopen → always Open
    # ReqStatus.CLOSE_LOST is terminal (no reopen).
}

# Transitions that require a mandatory reason (audit).
_REASON_REQUIRED = {ReqStatus.HOLD, ReqStatus.CANCELLED, ReqStatus.CLOSE_LOST}


def requirement_is_expired(requirement) -> bool:
    """Derived, read-only overlay: the Target Fill Date has passed and the
    requirement is not in a terminal state. Never a stored status — extending the
    date clears it automatically."""
    if not requirement.target_fill_date:
        return False
    code = requirement.req_status.status_code if requirement.req_status_id else None
    if code in ReqStatus.TERMINAL:
        return False
    return requirement.target_fill_date < timezone.now().date()


def _next_sequence(year: int) -> int:
    """Next running number for the given year, based on the highest existing
    Req_TrackerNo. Parsing the max (not counting rows) keeps numbers stable even
    if a record is ever removed."""
    prefix = f"{_TRACKER_PREFIX}-{year}-"
    last = (
        RequirementTracker.objects
        .filter(req_tracker_no__startswith=prefix)
        .order_by("-req_tracker_no")
        .values_list("req_tracker_no", flat=True)
        .first()
    )
    if not last:
        return 1
    try:
        return int(last.rsplit("-", 1)[-1]) + 1
    except (ValueError, IndexError):
        # Defensive: if an unexpected format slips in, fall back to a count.
        return RequirementTracker.objects.filter(req_tracker_no__startswith=prefix).count() + 1


def generate_identifiers(year: int, seq: int):
    """Build the two human-readable identifiers from a sequence number."""
    return (
        f"{_TRACKER_PREFIX}-{year}-{seq:03d}",   # REQ-2026-001
        f"{_JD_PREFIX}-{year}-{seq:05d}",         # JD-2026-00001
    )


def create_requirement(*, validated_data: dict, user) -> RequirementTracker:
    """Create a requirement with auto-generated tracking numbers.

    Concurrency: with up to 4 users a collision is unlikely, but the unique
    constraint on req_tracker_no is the real guarantee — if two creates race to
    the same number, one fails and we simply retry with the next number.
    """
    # Default lifecycle status to "New" unless the caller chose one.
    if not validated_data.get("req_status"):
        validated_data["req_status"] = ReqStatusMaster.objects.get(status_code=ReqStatus.NEW)
    validated_data.setdefault("positions_filled", 0)
    validated_data.setdefault("is_active", True)  # model field has no default; DB column is NOT NULL
    # req_date is the system creation date (DB column is NOT NULL) — set it here,
    # never from user input. The user's "Required by" deadline is target_fill_date.
    validated_data.setdefault("req_date", timezone.now().date())

    # When a Hiring Manager creates a requirement, they own it by default.
    if not validated_data.get("hiring_mgr") and getattr(getattr(user, "role", None), "role_code", None) == Roles.HIRING_MANAGER:
        validated_data["hiring_mgr"] = user

    year = timezone.now().year
    last_error = None

    for attempt in range(1, _MAX_RETRIES + 1):
        seq = _next_sequence(year)
        req_tracker_no, jd_serial_number = generate_identifiers(year, seq)
        try:
            with transaction.atomic():
                obj = RequirementTracker.objects.create(
                    req_tracker_no=req_tracker_no,
                    jd_serial_number=jd_serial_number,
                    created_by=user,
                    created_on=timezone.now(),
                    **validated_data,
                )
                # Materialise one Open seat per opening (see POSITION_REDESIGN).
                from requirements.positions import create_positions_for_requirement
                create_positions_for_requirement(obj, user)
            logger.info("Requirement created: %s by user %s", req_tracker_no, getattr(user, "user_id", None))
            from core.activity import ActivityType, log_activity
            client_name = getattr(getattr(obj, "client", None), "client_name", None)
            log_activity(
                ActivityType.REQUIREMENT_CREATED,
                f"Requirement opened: {obj.jd_role_name}" + (f" · {client_name}" if client_name else ""),
                req=obj, actor=user,
            )
            return obj
        except IntegrityError as exc:
            last_error = exc
            logger.warning("Req number collision on %s (attempt %d) — retrying", req_tracker_no, attempt)

    logger.error("Failed to generate a unique requirement number after %d attempts", _MAX_RETRIES)
    raise last_error


def assign_requirement(*, requirement: RequirementTracker, recruiter, user) -> RequirementTracker:
    """UC1 Step 2 — assign the requirement to a recruiter and move it to
    'Assigned', recording the assignment date and who made the change."""
    requirement.recruiter = recruiter
    requirement.req_status = ReqStatusMaster.objects.get(status_code=ReqStatus.ASSIGNED)
    requirement.assigned_date = timezone.now().date()
    requirement.updated_by = user
    requirement.updated_on = timezone.now()
    requirement.save(
        update_fields=["recruiter", "req_status", "assigned_date", "updated_by", "updated_on"]
    )
    logger.info(
        "Requirement %s assigned to recruiter %s by %s",
        requirement.req_tracker_no, getattr(recruiter, "user_id", None), getattr(user, "user_id", None),
    )
    from core.activity import ActivityType, log_activity
    log_activity(
        ActivityType.REQUIREMENT_ASSIGNED,
        f"{recruiter.full_name} assigned to {requirement.req_tracker_no} · {requirement.jd_role_name}",
        req=requirement, actor=user,
    )
    return requirement


def open_requirement_on_first_link(requirement, user):
    """Event-driven transition: the first candidate linked to a New/Assigned
    requirement moves it to Open. A no-op for any other status (Hold, Partial
    Filled, terminal states, …) — those are left exactly as they are. Called
    whenever a candidate is mapped to the requirement (idempotent: later links
    find it already Open and change nothing)."""
    current = requirement.req_status.status_code if requirement.req_status else None
    if current in (ReqStatus.NEW, ReqStatus.ASSIGNED):
        requirement.req_status = ReqStatusMaster.objects.get(status_code=ReqStatus.OPEN)
        requirement.updated_by = user
        requirement.updated_on = timezone.now()
        requirement.save(update_fields=["req_status", "updated_by", "updated_on"])
        logger.info("Requirement %s → Open (first candidate linked)", requirement.req_tracker_no)
    return requirement


@transaction.atomic
def change_requirement_status(*, requirement, to_status, user, reason=None):
    """Manual Hiring-Manager transition — the guarded set-status path.

    Allowed: Open↔Hold; Cancel / Close-Lost from any active state or Hold; Reopen
    (Cancelled → Open only — Close Lost is terminal). Cancelled and Closed Lost are
    explicit HM decisions with a MANDATORY reason (never auto-derived). Every change
    cascades to the seats (Rules 4–7) and is audited. All other targets (New/Assigned/
    Open-on-link/Partial/Close Filled) are event/rollup-driven and rejected here."""
    from requirements.positions import (
        _log_status, cascade_on_cancel, cascade_on_hold, cascade_on_reopen, cascade_on_resume,
    )
    from core.constants import AuditEntity, ChangeType

    current = requirement.req_status.status_code if requirement.req_status else None
    if to_status not in MANUAL_REQ_TRANSITIONS.get(current, set()):
        raise RequirementStatusError(
            f"Status cannot be changed from '{current or '—'}' to '{to_status}'."
        )
    reason = (reason or "").strip() or None
    if to_status in _REASON_REQUIRED and not reason:
        raise RequirementStatusError("A reason is required for Hold, Cancelled and Closed Lost.")

    requirement.req_status = ReqStatusMaster.objects.get(status_code=to_status)
    requirement.updated_by = user
    requirement.updated_on = timezone.now()
    requirement.save(update_fields=["req_status", "updated_by", "updated_on"])
    _log_status(AuditEntity.REQUIREMENT, requirement.req_id, current, to_status,
                reason=reason, change_type=ChangeType.MANUAL, user=user)
    logger.info(
        "Requirement %s status → %s (manual by user %s)",
        requirement.req_tracker_no, to_status, getattr(user, "user_id", None),
    )

    # Seat cascade per the business rules.
    if to_status == ReqStatus.HOLD:
        cascade_on_hold(requirement, user, reason=reason)
    elif to_status in (ReqStatus.CANCELLED, ReqStatus.CLOSE_LOST):
        cascade_on_cancel(requirement, user, reason=reason)
    elif to_status == ReqStatus.OPEN:
        # Resume from Hold reopens only Hold-inactivated seats; reopen from
        # Cancelled reopens all system-inactivated seats.
        (cascade_on_resume if current == ReqStatus.HOLD else cascade_on_reopen)(
            requirement, user, reason=reason
        )

    # Closed Lost is irreversible → free every remaining active application back to
    # the Talent Pool. Cancelled is deliberately excluded: it is reopenable, so its
    # pipeline is preserved and restored by cascade_on_reopen. (Close Filled is the
    # rollup's job — see requirements.positions.recompute_requirement.)
    if to_status == ReqStatus.CLOSE_LOST:
        from pipeline.services import close_remaining_applications
        from candidates.services import resolve_reviews_for_requirement
        from core.constants import ReviewResolution
        close_remaining_applications(
            requirement=requirement, outcome=ApplicationStatus.REQ_CLOSE_LOST,
            user=user, reason=reason,
        )
        # Irreversible closure → empty the pre-pipeline Review Pool too.
        resolve_reviews_for_requirement(
            requirement=requirement, resolution=ReviewResolution.REQ_CLOSED, user=user)

    if to_status in (ReqStatus.CLOSE_LOST, ReqStatus.CANCELLED):
        from core.activity import ActivityType, log_activity
        verb = "closed as Lost" if to_status == ReqStatus.CLOSE_LOST else "cancelled"
        log_activity(
            ActivityType.REQUIREMENT_CLOSED,
            f"Requirement {verb}: {requirement.req_tracker_no} · {requirement.jd_role_name}",
            req=requirement, actor=user,
        )
    requirement.refresh_from_db()
    return requirement


@transaction.atomic
def end_recruitment(*, requirement, user, reason=None):
    """Permanent Hiring-Manager decision to stop recruiting the remaining seats of
    an EXPIRED, partially-filled requirement. Persists the decision on the
    requirement (recruitment_ended / _on / _by), withdraws the remaining OPEN seats
    to Inactive (Filled/Held/Cancelled untouched), and closes every remaining
    active application as REQ_POSITIONS_WITHDRAWN — returning eligible candidates
    to the Talent Pool via the shared close path. The requirement KEEPS its status
    (Partial Filled) + Expired indicator; the flag freezes the rollup so the
    withdrawn seats never roll it to Close Filled.

    Preconditions: status is PARTIAL_FILLED and the requirement is Expired.
    Idempotent: a second call (already ended) is a no-op. Raises
    RequirementStatusError if the preconditions aren't met."""
    current = requirement.req_status.status_code if requirement.req_status else None

    if requirement.recruitment_ended:
        return {"closed": 0, "requirement": requirement, "already_ended": True}

    if current != ReqStatus.PARTIAL_FILLED:
        raise RequirementStatusError(
            "End Recruitment is only available for a Partially Filled requirement."
        )
    if not requirement_is_expired(requirement):
        raise RequirementStatusError(
            "End Recruitment is only available once the requirement has expired "
            "(extend the Target Fill Date to keep recruiting instead)."
        )

    from pipeline.services import close_remaining_applications
    from requirements.positions import _log_status, cascade_on_end_recruitment

    # 1) Persist the business decision FIRST so the rollup freeze is in effect
    #    before any seat change recomputes the status.
    now = timezone.now()
    requirement.recruitment_ended = True
    requirement.recruitment_ended_on = now
    requirement.recruitment_ended_by = user
    requirement.updated_by = user
    requirement.updated_on = now
    requirement.save(update_fields=[
        "recruitment_ended", "recruitment_ended_on", "recruitment_ended_by",
        "updated_by", "updated_on",
    ])

    # 2) Withdraw remaining OPEN seats → Inactive (status frozen by the flag).
    cascade_on_end_recruitment(requirement, user, reason=reason)

    # 3) Close remaining active applications (shared path) → Talent Pool.
    closed = close_remaining_applications(
        requirement=requirement, outcome=ApplicationStatus.REQ_POSITIONS_WITHDRAWN,
        user=user, reason=reason or "Recruitment ended for remaining positions.",
    )

    # 4) Clear the pre-pipeline Review Pool (candidates under review are released).
    from candidates.services import resolve_reviews_for_requirement
    from core.constants import ReviewResolution
    resolve_reviews_for_requirement(
        requirement=requirement, resolution=ReviewResolution.REQ_CLOSED, user=user)

    _log_status(AuditEntity.REQUIREMENT, requirement.req_id, current, current,
                reason=reason or "Recruitment ended (remaining positions withdrawn).",
                change_type=ChangeType.MANUAL, user=user)
    logger.info(
        "Requirement %s — recruitment ended by user %s (%d application(s) closed).",
        requirement.req_tracker_no, getattr(user, "user_id", None), closed,
    )
    from core.activity import ActivityType, log_activity
    log_activity(
        ActivityType.REQUIREMENT_CLOSED,
        f"Recruitment ended (partially filled): {requirement.req_tracker_no} · {requirement.jd_role_name}",
        req=requirement, actor=user,
    )
    requirement.refresh_from_db()
    return {"closed": closed, "requirement": requirement}
