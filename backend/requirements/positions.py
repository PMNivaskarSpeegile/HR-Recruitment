"""
Position (seat) lifecycle + requirement-status rollup + requirement→position
cascade.

A Requirement owns N Positions; each seat has its own status. The two lifecycles
are INDEPENDENT except at the sync points the business rules define:
  * first candidate linked            → requirement New/Assigned → Open (events.py)
  * seat filled / added               → rollup: Open / Partially Filled / Filled
  * requirement Hold / Cancel         → OPEN seats → Inactive (system, audited)
  * requirement Resume / Reopen       → auto-Inactive seats → Open (system, audited)

Manual seat Hold/Cancel are never auto-touched or auto-reopened. Filled seats are
never modified by requirement actions. This module is the single write-path for
position status + the positions_open/positions_filled cache, so they can't drift.
"""
import logging

from django.db import transaction
from django.utils import timezone

from admin_module.models import (
    PositionStatusMaster,
    ReqStatusMaster,
    RequirementPosition,
    StatusChangeHistory,
)
from core.constants import AuditEntity, ChangeType, PositionSource, PositionStatus, ReqStatus

logger = logging.getLogger("ats")

# Requirement statuses a human owns — the rollup never overwrites these.
MANUAL_REQ_STATES = {ReqStatus.HOLD, ReqStatus.CANCELLED, ReqStatus.CLOSE_LOST}

# Manual seat transitions a Hiring Manager may perform. FILLED is reached ONLY
# automatically (a candidate Joining) and is terminal. INACTIVE is system-only
# (the requirement cascade) and is intentionally absent here.
MANUAL_POSITION_TRANSITIONS = {
    PositionStatus.OPEN: {PositionStatus.HOLD, PositionStatus.CANCELLED},
    PositionStatus.HOLD: {PositionStatus.OPEN, PositionStatus.CANCELLED},
    PositionStatus.CANCELLED: {PositionStatus.OPEN},  # Reopen
}

# Seat statuses that count as a live opening (for the cache + rollup math).
# Cancelled and Inactive seats are excluded; Filled/Hold/Open count.
_COUNTED = lambda code: code not in (PositionStatus.CANCELLED, PositionStatus.INACTIVE)


def _position_status(code):
    return PositionStatusMaster.objects.get(status_code=code)


def _req_status(code):
    return ReqStatusMaster.objects.get(status_code=code)


def _seat_code(seat):
    return seat.position_status.status_code if seat.position_status_id else PositionStatus.OPEN


def _log_status(entity_type, entity_id, previous, new, *, reason, change_type, user):
    """Append one row to the unified status-change audit."""
    StatusChangeHistory.objects.create(
        entity_type=entity_type, entity_id=entity_id,
        previous_status=previous, new_status=new, reason=reason,
        change_type=change_type, changed_by=user, changed_on=timezone.now(),
    )


class PositionError(Exception):
    """Business-rule violation on a position action (bad transition, over-fill,
    protected seat, …)."""


# ---------------------------------------------------------------------------
# Seat creation
# ---------------------------------------------------------------------------
def create_positions_for_requirement(requirement, user, *, count=None):
    """Create the initial seats for a requirement (idempotent — does nothing if
    seats already exist). One Open position per opening."""
    if RequirementPosition.objects.filter(req=requirement).exists():
        return []
    n = count if count is not None else (requirement.positions_open or 1)
    n = max(int(n), 1)
    open_status = _position_status(PositionStatus.OPEN)
    now = timezone.now()
    rows = [
        RequirementPosition(
            req=requirement, position_no=i, position_status=open_status,
            status_source=None, is_active=True, created_by=user, created_on=now,
        )
        for i in range(1, n + 1)
    ]
    RequirementPosition.objects.bulk_create(rows)
    logger.info("Created %d positions for requirement %s", n, requirement.req_tracker_no)
    return rows


@transaction.atomic
def add_positions(*, requirement, count, user):
    """HM/Admin add new seats to an ACTIVE requirement (Rule 2). New seats are
    Open; the requirement rollup then reflects the added demand (e.g. a Filled
    requirement becomes Partially Filled). Caller enforces the 'active' guard."""
    count = max(int(count or 0), 1)
    last = (
        RequirementPosition.objects.filter(req=requirement)
        .order_by("-position_no").values_list("position_no", flat=True).first()
    ) or 0
    open_status = _position_status(PositionStatus.OPEN)
    now = timezone.now()
    created = []
    for i in range(last + 1, last + 1 + count):
        seat = RequirementPosition.objects.create(
            req=requirement, position_no=i, position_status=open_status,
            status_source=None, is_active=True, created_by=user, created_on=now,
        )
        _log_status(AuditEntity.POSITION, seat.position_id, None, PositionStatus.OPEN,
                    reason="Position added", change_type=ChangeType.MANUAL, user=user)
        created.append(seat)
    recompute_requirement(requirement, user)
    logger.info("Added %d positions to requirement %s", count, requirement.req_tracker_no)
    return created


@transaction.atomic
def delete_position(*, position, user):
    """Delete a seat — only allowed if it was never Filled and carries no
    recruitment activity (no winning application). Otherwise the HM should Cancel
    it instead (Rule 11)."""
    code = _seat_code(position)
    if code == PositionStatus.FILLED or position.filled_by_mapping_id:
        raise PositionError(
            "This position has recruitment activity (it was filled) and cannot be "
            "deleted. Cancel it instead."
        )
    req = position.req
    pid = position.position_id  # capture before delete() clears the PK
    position.delete()
    _log_status(AuditEntity.POSITION, pid, code, "DELETED",
                reason="Position deleted", change_type=ChangeType.MANUAL, user=user)
    recompute_requirement(req, user)


# ---------------------------------------------------------------------------
# Requirement-status rollup (derived from seats)
# ---------------------------------------------------------------------------
def _rollup_status(requirement):
    """Compute the derived requirement status from its seats. Returns a
    status_code, or None to mean 'leave as-is'. Never returns a manual/terminal
    state — cancelling seats never auto-cancels the requirement (independence)."""
    seats = list(
        RequirementPosition.objects.filter(req=requirement).select_related("position_status")
    )
    if not seats:
        return None
    active = [_seat_code(s) for s in seats if _COUNTED(_seat_code(s))]
    total = len(active)
    if total == 0:
        return None  # all cancelled/inactive → leave requirement untouched
    filled = sum(1 for c in active if c == PositionStatus.FILLED)
    if filled == 0:
        current = requirement.req_status.status_code if requirement.req_status else None
        if current in (ReqStatus.NEW, ReqStatus.OPEN, ReqStatus.ASSIGNED):
            return current
        return ReqStatus.ASSIGNED if requirement.recruiter_id else ReqStatus.OPEN
    if filled >= total:
        return ReqStatus.CLOSE_FILLED
    return ReqStatus.PARTIAL_FILLED


def recompute_requirement(requirement, user):
    """Refresh the requirement's derived status + positions cache from its seats.
    Manual states (Hold/Cancelled/Close Lost) keep their status (cache only)."""
    seats = list(RequirementPosition.objects.filter(req=requirement).select_related("position_status"))
    active = [s for s in seats if _COUNTED(_seat_code(s))]
    filled = sum(1 for s in active if _seat_code(s) == PositionStatus.FILLED)

    fields = []
    if requirement.positions_open != len(active):
        requirement.positions_open = len(active)
        fields.append("positions_open")
    if requirement.positions_filled != filled:
        requirement.positions_filled = filled
        fields.append("positions_filled")

    current = requirement.req_status.status_code if requirement.req_status else None
    newly_closed = False
    # A permanent End-Recruitment decision FREEZES the calculated status (it stays
    # Partial Filled by design), so withdrawing the open seats to Inactive never
    # rolls the requirement to Close Filled. The flag — not seat metadata — is the
    # source of truth. Manual states (Hold/Cancel/Close Lost) freeze as before.
    if current not in MANUAL_REQ_STATES and not requirement.recruitment_ended:
        target = _rollup_status(requirement)
        if target and target != current:
            requirement.req_status = _req_status(target)
            fields.append("req_status")
            newly_closed = target == ReqStatus.CLOSE_FILLED
            _log_status(AuditEntity.REQUIREMENT, requirement.req_id, current, target,
                        reason="Auto rollup from positions", change_type=ChangeType.AUTO, user=user)

    if fields:
        requirement.updated_by = user
        requirement.updated_on = timezone.now()
        fields += ["updated_by", "updated_on"]
        requirement.save(update_fields=fields)
        if newly_closed:
            from core.activity import ActivityType, log_activity
            log_activity(
                ActivityType.REQUIREMENT_CLOSED,
                f"Requirement filled: {requirement.req_tracker_no} · {requirement.jd_role_name}",
                req=requirement, actor=user,
            )
            # All seats filled → free every remaining active application (the
            # candidates who didn't win a seat) back to the Talent Pool. The
            # seat-winning applications are excluded inside close_remaining_applications,
            # so the just-joined candidate that triggered this fill is untouched.
            from core.constants import ApplicationStatus, ReviewResolution
            from pipeline.services import close_remaining_applications
            from candidates.services import resolve_reviews_for_requirement
            close_remaining_applications(
                requirement=requirement, outcome=ApplicationStatus.REQ_CLOSE_FILLED,
                user=user, reason="Requirement filled — remaining applications closed.",
            )
            # Filled → also clear its pre-pipeline Review Pool.
            resolve_reviews_for_requirement(
                requirement=requirement, resolution=ReviewResolution.REQ_CLOSED, user=user)
    return requirement


# ---------------------------------------------------------------------------
# Seat status writer (single write-path) + manual transition guard
# ---------------------------------------------------------------------------
@transaction.atomic
def set_position_status(*, position, to_status_code, user, filled_by_mapping=None,
                        source=None, reason=None, change_type=ChangeType.MANUAL, recompute=True):
    """Change one seat's status (the single write-path), stamp its source, record
    the audit row, then optionally recompute the requirement. `filled_by_mapping`
    records the winning application on FILLED."""
    valid = {PositionStatus.OPEN, PositionStatus.IN_PROGRESS, PositionStatus.FILLED,
             PositionStatus.CANCELLED, PositionStatus.HOLD, PositionStatus.INACTIVE}
    if to_status_code not in valid:
        raise PositionError(f"Unknown position status '{to_status_code}'.")

    previous = _seat_code(position)
    position.position_status = _position_status(to_status_code)
    position.status_source = source
    fields = ["position_status", "status_source"]
    if to_status_code == PositionStatus.FILLED:
        position.filled_by_mapping = filled_by_mapping
        fields.append("filled_by_mapping")
    elif filled_by_mapping is None and position.filled_by_mapping_id:
        position.filled_by_mapping = None
        fields.append("filled_by_mapping")
    position.updated_by = user
    position.updated_on = timezone.now()
    fields += ["updated_by", "updated_on"]
    position.save(update_fields=fields)

    _log_status(AuditEntity.POSITION, position.position_id, previous, to_status_code,
                reason=reason, change_type=change_type, user=user)
    if recompute:
        recompute_requirement(position.req, user)
    return position


@transaction.atomic
def change_position_status(*, position, to_status_code, user, reason=None):
    """MANUAL (Hiring-Manager) seat transition. Enforces the allowed manual
    transitions (Open↔Hold, Open/Hold→Cancelled, Cancelled→Open). A manual Filled
    or Inactive is rejected — Filled happens only on Join; Inactive is set only by
    the requirement cascade. Stamps the seat as MANUAL so the cascade never
    auto-reopens it."""
    if to_status_code in (PositionStatus.INACTIVE, PositionStatus.FILLED):
        raise PositionError(f"'{to_status_code}' cannot be set manually.")
    current = _seat_code(position)
    if to_status_code not in MANUAL_POSITION_TRANSITIONS.get(current, set()):
        raise PositionError(
            f"Position status cannot be changed from '{current}' to '{to_status_code}'."
        )
    return set_position_status(
        position=position, to_status_code=to_status_code, user=user,
        source=PositionSource.MANUAL, reason=reason, change_type=ChangeType.MANUAL,
    )


# ---------------------------------------------------------------------------
# Requirement → position cascade (system-only, audited)
# ---------------------------------------------------------------------------
def cascade_on_hold(requirement, user, *, reason=None):
    """Requirement put on Hold → every OPEN seat becomes Inactive (AUTO_REQ_HOLD).
    Manual Hold/Cancelled and Filled seats are left exactly as they are (Rule 4/8)."""
    _inactivate_open(requirement, PositionSource.AUTO_REQ_HOLD, user, reason)
    recompute_requirement(requirement, user)


def cascade_on_cancel(requirement, user, *, reason=None):
    """Requirement Cancelled / Closed Lost → every OPEN seat becomes Inactive
    (AUTO_REQ_CANCEL). Seats already auto-Inactive from a prior Hold are re-tagged
    AUTO_REQ_CANCEL so a reopen restores them. Manual + Filled seats untouched
    (Rule 6/8)."""
    _inactivate_open(requirement, PositionSource.AUTO_REQ_CANCEL, user, reason)
    # Re-tag hold-auto-inactive seats to the cancel source (Hold state not preserved).
    (RequirementPosition.objects
        .filter(req=requirement, status_source=PositionSource.AUTO_REQ_HOLD)
        .update(status_source=PositionSource.AUTO_REQ_CANCEL, updated_by=user, updated_on=timezone.now()))
    recompute_requirement(requirement, user)


def cascade_on_resume(requirement, user, *, reason=None):
    """Requirement resumed from Hold → only seats made Inactive BY the Hold
    (AUTO_REQ_HOLD) return to Open (Rule 5)."""
    _reopen_auto(requirement, {PositionSource.AUTO_REQ_HOLD}, user, reason)
    recompute_requirement(requirement, user)


def cascade_on_reopen(requirement, user, *, reason=None):
    """Cancelled requirement reopened → all system-Inactivated seats return to
    Open (Rule 7; a reopened requirement always comes back Open)."""
    _reopen_auto(requirement, set(PositionSource.AUTO), user, reason)
    recompute_requirement(requirement, user)


def cascade_on_end_recruitment(requirement, user, *, reason=None):
    """Permanent End Recruitment → withdraw every remaining OPEN seat to Inactive
    (source AUTO_END_RECRUITMENT, for seat history/reporting). Filled / Held /
    Cancelled seats are untouched. The caller must have set
    requirement.recruitment_ended = True first, so the recompute here freezes the
    status (stays Partial Filled) instead of rolling to Close Filled."""
    _inactivate_open(requirement, PositionSource.AUTO_END_RECRUITMENT, user, reason)
    recompute_requirement(requirement, user)


def _inactivate_open(requirement, source, user, reason):
    open_seats = (
        RequirementPosition.objects.filter(req=requirement)
        .select_related("position_status")
    )
    for seat in open_seats:
        if _seat_code(seat) == PositionStatus.OPEN:
            set_position_status(
                position=seat, to_status_code=PositionStatus.INACTIVE, user=user,
                source=source, reason=reason, change_type=ChangeType.AUTO, recompute=False,
            )


def _reopen_auto(requirement, sources, user, reason):
    seats = (
        RequirementPosition.objects.filter(req=requirement, status_source__in=list(sources))
        .select_related("position_status")
    )
    for seat in seats:
        if _seat_code(seat) == PositionStatus.INACTIVE:
            set_position_status(
                position=seat, to_status_code=PositionStatus.OPEN, user=user,
                source=None, reason=reason, change_type=ChangeType.AUTO, recompute=False,
            )
