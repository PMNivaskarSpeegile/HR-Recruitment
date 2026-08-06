"""
Activity feed / audit logging.

`log_activity` records a notable business event (requirement opened, candidate
joined, requirement closed, …) into `activity_log`. It's best-effort: an audit
write must never break the business action that triggered it, so failures are
logged and swallowed.

Activity types are stable codes the dashboard maps to icons — keep them in sync
with the frontend `ActivityItem` union.
"""
import logging

from django.utils import timezone

logger = logging.getLogger("ats")


class ActivityType:
    REQUIREMENT_CREATED = "requirement_created"
    REQUIREMENT_ASSIGNED = "requirement_assigned"
    REQUIREMENT_CLOSED = "requirement_closed"
    CANDIDATE_ADDED = "candidate_added"
    CANDIDATE_JOINED = "candidate_joined"


def log_activity(activity_type, summary, *, req=None, candidate=None, actor=None):
    """Best-effort append to the activity feed. Never raises."""
    try:
        from admin_module.models import ActivityLog
        ActivityLog.objects.create(
            activity_type=activity_type,
            summary=summary,
            req=req,
            candidate=candidate,
            actor=actor,
            created_on=timezone.now(),
        )
    except Exception:  # noqa: BLE001 - auditing must not break the action
        logger.exception("Failed to record activity: %s", activity_type)
