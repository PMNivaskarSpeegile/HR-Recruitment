"""
Screening rounds — sequential screening workflow for an application.

An application (jd_cv_mapping) can have multiple screening rounds. Business rules
(industry-standard sequential screening) are enforced here, the single write
path, so the API/UI can't bypass them:

  * No new round while one is still Scheduled (finish it first).
  * A Video screening requires a Telephonic screening completed with "Passed".
  * A repeat Telephonic is allowed only when the previous one's outcome was
    "Reschedule Required".
  * A closed application (Rejected / Not Suitable / Dropped / Withdrawn / Joined)
    accepts no further screenings.

Screening TYPES come from screening_mode_master (extensible); the two rules above
key on the built-in TELEPHONIC/VIDEO codes, so new modes simply have no special
ordering constraint. Every scheduled/completed round is written to the
application's activity timeline (candidate_interaction).
"""
import logging

from django.db import transaction
from django.utils import timezone

from admin_module.models import CandidateInteraction, Screening, ScreeningModeMaster
from core.constants import (
    ApplicationStatus,
    InteractionType,
    ScreeningMode,
    ScreeningOutcome,
    ScreeningStatus,
)
from core.timeutils import to_local_naive

logger = logging.getLogger("ats")

# Application states after which no further screening makes sense.
CLOSED_APP_STATUSES = {
    ApplicationStatus.REJECTED, ApplicationStatus.NOT_SUITABLE, ApplicationStatus.DROPPED,
    ApplicationStatus.OFFER_DECLINED, ApplicationStatus.WITHDRAWN, ApplicationStatus.JOINED,
}

_OUTCOME_LABEL = {
    ScreeningOutcome.PASSED: "Passed",
    ScreeningOutcome.FAILED: "Failed",
    ScreeningOutcome.NO_SHOW: "No Show",
    ScreeningOutcome.CANCELLED: "Cancelled",
    ScreeningOutcome.RESCHEDULE_REQUIRED: "Reschedule Required",
}


class ScreeningError(Exception):
    """A business-rule violation while scheduling/completing a screening."""


def screenings_for(mapping):
    """All rounds of an application, chronological (oldest first)."""
    return (
        Screening.objects.filter(mapping=mapping)
        .select_related("screening_mode", "created_by")
        .order_by("scheduled_at", "screening_id")
    )


def _app_status_code(mapping):
    return mapping.application_stage.status_code if mapping.application_stage_id else None


def _latest_completed_telephonic(mapping):
    return (
        Screening.objects
        .filter(mapping=mapping, status=ScreeningStatus.COMPLETED, screening_mode__mode_code=ScreeningMode.TELEPHONIC)
        .order_by("-scheduled_at", "-screening_id")
        .first()
    )


def validate_can_schedule(mapping, mode):
    """Raise ScreeningError if a round of `mode` (a ScreeningModeMaster) can't be
    scheduled on `mapping` right now."""
    if _app_status_code(mapping) in CLOSED_APP_STATUSES:
        raise ScreeningError("This application is closed — no further screenings can be scheduled.")
    if Screening.objects.filter(mapping=mapping, status=ScreeningStatus.SCHEDULED).exists():
        raise ScreeningError("Complete the current screening before scheduling another.")

    code = mode.mode_code
    if code == ScreeningMode.VIDEO:
        # The telephonic pre-screen is a prerequisite only while the Telephonic
        # mode is active in the process. With it retired (current single-round
        # video process), video schedules directly; re-activating Telephonic
        # automatically restores the gate — no code change needed.
        telephonic_active = ScreeningModeMaster.objects.filter(
            mode_code=ScreeningMode.TELEPHONIC, is_active=True,
        ).exists()
        if telephonic_active:
            passed_telephonic = Screening.objects.filter(
                mapping=mapping, status=ScreeningStatus.COMPLETED,
                outcome=ScreeningOutcome.PASSED, screening_mode__mode_code=ScreeningMode.TELEPHONIC,
            ).exists()
            if not passed_telephonic:
                raise ScreeningError("A video screening can only be scheduled after a telephonic screening is passed.")
    elif code == ScreeningMode.TELEPHONIC:
        latest = _latest_completed_telephonic(mapping)
        if latest and latest.outcome != ScreeningOutcome.RESCHEDULE_REQUIRED:
            raise ScreeningError(
                "A telephonic screening already exists — add another only when the previous outcome is 'Reschedule Required'."
            )


def _timeline(mapping, summary, user):
    """Append a screening event to the application's activity timeline."""
    CandidateInteraction.objects.create(
        candidate=mapping.candidate, req=mapping.req,
        interaction_type=InteractionType.SCREENING_FEEDBACK,
        comment=summary, created_by=user, created_on=timezone.now(),
    )


@transaction.atomic
def schedule_screening(*, mapping, mode, scheduled_at, interviewer, notes, user):
    """Create a screening round after enforcing the sequential rules."""
    scheduled_at = to_local_naive(scheduled_at)
    if scheduled_at and scheduled_at <= timezone.now():
        raise ScreeningError("Screening must be scheduled for a future date and time.")
    validate_can_schedule(mapping, mode)
    now = timezone.now()
    screening = Screening.objects.create(
        mapping=mapping, screening_mode=mode, status=ScreeningStatus.SCHEDULED,
        scheduled_at=scheduled_at, interviewer=(interviewer or None), notes=(notes or None),
        is_active=True, created_by=user, created_on=now, updated_by=user, updated_on=now,
    )
    # Mirror the scheduled round onto the mapping's denormalized fields so the
    # pipeline board can show the screening TYPE + time (the board reads these).
    mapping.screening_datetime = scheduled_at
    mapping.screening_mode = mode
    fields = ["screening_datetime", "screening_mode", "updated_by", "updated_on"]
    # "Schedule Screening" is a recruiter action: scheduling the first round moves
    # the application from JD Email Sent into the Screening Scheduled stage.
    # (Rescheduling — already Screening Scheduled — leaves the stage unchanged.)
    if _app_status_code(mapping) == ApplicationStatus.JD_EMAIL_SENT:
        from pipeline.services import _app_status
        mapping.application_stage = _app_status(ApplicationStatus.SCREENING_SCHEDULED)
        fields.append("application_stage")
    mapping.updated_by = user
    mapping.updated_on = now
    mapping.save(update_fields=fields)

    when = scheduled_at.strftime("%d %b %Y %H:%M") if scheduled_at else "TBD"
    _timeline(mapping, f"{mode.mode_name} screening scheduled ({when})", user)
    logger.info("Screening %s scheduled for mapping %s", screening.screening_id, mapping.mapping_id)
    return screening


@transaction.atomic
def reschedule_screening_round(*, screening, new_datetime, user):
    """Move a still-SCHEDULED screening round to a new date/time. The new time
    must be in the future (down to the minute)."""
    if screening.status != ScreeningStatus.SCHEDULED:
        raise ScreeningError("Only a scheduled screening can be rescheduled.")
    new_datetime = to_local_naive(new_datetime)
    if not new_datetime or new_datetime <= timezone.now():
        raise ScreeningError("Screening must be rescheduled to a future date and time.")
    screening.scheduled_at = new_datetime
    screening.updated_by = user
    screening.updated_on = timezone.now()
    screening.save(update_fields=["scheduled_at", "updated_by", "updated_on"])
    # Keep the mapping's denormalized screening fields in sync (board display).
    mapping = screening.mapping
    mapping.screening_datetime = new_datetime
    mapping.screening_mode = screening.screening_mode
    mapping.updated_by = user
    mapping.updated_on = timezone.now()
    mapping.save(update_fields=["screening_datetime", "screening_mode", "updated_by", "updated_on"])
    when = new_datetime.strftime("%d %b %Y %H:%M")
    _timeline(screening.mapping, f"{screening.screening_mode.mode_name} screening rescheduled to {when}", user)
    logger.info("Screening %s rescheduled for mapping %s", screening.screening_id, screening.mapping_id)
    return screening


@transaction.atomic
def complete_screening(*, screening, outcome, notes, user):
    """Record a round's outcome."""
    if screening.status == ScreeningStatus.COMPLETED:
        raise ScreeningError("This screening is already completed.")
    if outcome not in ScreeningOutcome.ALL:
        raise ScreeningError("Choose a valid screening outcome.")
    now = timezone.now()
    screening.status = ScreeningStatus.COMPLETED
    screening.outcome = outcome
    if notes:
        screening.notes = notes
    screening.updated_by = user
    screening.updated_on = now
    screening.save(update_fields=["status", "outcome", "notes", "updated_by", "updated_on"])

    _timeline(screening.mapping, f"{screening.screening_mode.mode_name} screening — {_OUTCOME_LABEL.get(outcome, outcome)}", user)
    logger.info("Screening %s completed (%s)", screening.screening_id, outcome)

    # Passing the screening is what advances the application from Screening
    # Scheduled to OK to Proceed. The board's Screening-Scheduled outcome menu
    # intentionally offers no manual "OK to Proceed" — the recruiter advances by
    # recording a Passed interview here. Routed through the centralized engine so
    # stage / latest_outcome / audit stay consistent.
    mapping = screening.mapping
    if outcome == ScreeningOutcome.PASSED and not mapping.is_closed \
            and _app_status_code(mapping) == ApplicationStatus.SCREENING_SCHEDULED:
        from pipeline.services import record_outcome
        record_outcome(mapping=mapping, outcome=ApplicationStatus.PASSED, user=user)

    return screening
