# """
# Role-aware dashboard aggregations (read-only).

# Returns a single payload tailored to the caller's role so the frontend can
# render its whole bento grid from one request. Pure ORM aggregation — no writes.
# """
# from datetime import timedelta

# from django.db.models import Count, Max, Q
# from django.utils import timezone

# from core.constants import (
#     ApplicationStatus, CandidateStatus, DuplicateReview, PositionStatus, ReqStatus,
#     ReviewStatus, Roles,
# )

# from .models import (
#     ActivityLog,
#     CandidateDuplicateReview,
#     CandidateMaster,
#     CandidateRequirementReview,
#     JdCvMapping,
#     RequirementPosition,
#     RequirementTracker,
#     UserMaster,
# )

# # A requirement is "active" (still being worked) unless it's in a terminal state.
# # (Expiry is a derived overlay, not a stored status — see ReqStatus.TERMINAL.)
# TERMINAL_REQ_STATUSES = set(ReqStatus.TERMINAL)
# # An application is "in pipeline" while it's in flight (not a terminal outcome).
# ACTIVE_PIPELINE_STATUSES = {
#     ApplicationStatus.SHORTLISTED, ApplicationStatus.JD_EMAIL_SENT,
#     ApplicationStatus.SCREENING_SCHEDULED, ApplicationStatus.OK_TO_PROCEED,
#     ApplicationStatus.OFFERED, ApplicationStatus.AWAITING_JOINING,
# }
# # A requirement with open seats and no activity for this many days is "stalled".
# STALE_DAYS = 14


# def _kpi(key, label, value, hint=None):
#     item = {"key": key, "label": label, "value": value or 0}
#     if hint:
#         item["hint"] = hint
#     return item


# def _status_breakdown(qs, status_field, pk_field):
#     rows = qs.values(status_field).annotate(count=Count(pk_field)).order_by("-count")
#     return [{"status": r[status_field] or "Unknown", "count": r["count"]} for r in rows]


# def _open_positions(reqs_qs):
#     """Real-time open seats for a (role-scoped) RequirementTracker qs — counts
#     requirement_position rows whose OWN seat status is Open, the same source of
#     truth as the Admin dashboard's top-level `open_positions` KPI. Previously
#     summed the cached positions_open/positions_filled rollup on
#     requirement_tracker instead, which can silently drift out of sync with the
#     real per-seat status (see Dashboard_Testing_Guide.md, Finding #1)."""
#     return RequirementPosition.objects.filter(
#         req__in=reqs_qs, position_status__status_code=PositionStatus.OPEN
#     ).count()


# def _position_totals(positions_qs):
#     """Total seats + filled seats over a (role-scoped) RequirementPosition qs, in
#     ONE aggregate query. Returns (total, filled)."""
#     agg = positions_qs.aggregate(
#         total=Count("position_id"),
#         filled=Count("position_id", filter=Q(position_status__status_code=PositionStatus.FILLED)),
#     )
#     return agg["total"] or 0, agg["filled"] or 0


# # The recruitment pipeline chart — the STAGES (candidate position) in flow order,
# # rendered from EXISTING application-stage data (zero-filled). Matches the Pipeline
# # board exactly: applications begin at Shortlisted. Pre-pipeline "New CV"
# # candidates (awaiting resume review) are reported by a SEPARATE KPI, not here.
# # Outcomes (Joined, Rejected, Offer Declined, Withdrawn, …) are excluded — they
# # remain in candidate history, reports and analytics.
# _PIPELINE_STAGES = [
#     (ApplicationStatus.SHORTLISTED, "Shortlisted"),
#     (ApplicationStatus.JD_EMAIL_SENT, "JD Email Sent"),
#     (ApplicationStatus.SCREENING_SCHEDULED, "Screening Scheduled"),
#     (ApplicationStatus.OK_TO_PROCEED, "OK to Proceed"),
#     (ApplicationStatus.OFFERED, "Offer Released"),
#     (ApplicationStatus.AWAITING_JOINING, "Awaiting Joining"),
# ]


# def _pipeline_stages(mappings_qs):
#     """Count a (role-scoped) mappings qs per application stage and return the full
#     pipeline flow in canonical order (0-filled), in ONE query. Excludes closed
#     applications (is_closed=True) — a candidate who has already Joined or been
#     Rejected stays parked at their last STAGE value forever otherwise, silently
#     inflating that stage's count (see Dashboard_Testing_Guide.md, Finding #2)."""
#     counts = dict(
#         mappings_qs.filter(is_closed=False)
#         .values_list("application_stage__status_code")
#         .annotate(c=Count("mapping_id"))
#         .values_list("application_stage__status_code", "c")
#     )
#     return [{"status": label, "count": counts.get(code, 0)} for code, label in _PIPELINE_STAGES]


# def _recent_requirements(qs, limit=5):
#     rows = (
#         qs.select_related("client", "recruiter", "req_status")
#         .annotate(
#             open_seats=Count(
#                 "requirementposition",
#                 filter=Q(requirementposition__position_status__status_code=PositionStatus.OPEN),
#                 distinct=True,
#             )
#         )
#         .order_by("-req_id")[:limit]
#     )
#     return [
#         {
#             "req_tracker_no": r.req_tracker_no,
#             "jd_role_name": r.jd_role_name,
#             # client_id is 0-eligible (Category 2 default row) — must use "is not
#             # None", not a truthy check (see Dashboard_Testing_Guide.md, id-0 bug).
#             "client_name": r.client.client_name if r.client_id is not None else None,
#             "recruiter_name": r.recruiter.full_name if r.recruiter_id is not None else None,
#             "status": r.req_status.status_name if r.req_status_id is not None else None,
#             "req_date": r.req_date.isoformat() if r.req_date else None,
#             "positions_required": r.positions_open or 0,
#             "positions_filled": r.positions_filled or 0,
#             # Real per-seat Open-status count, not the cached rollup (Finding #1).
#             "positions_open": r.open_seats,
#         }
#         for r in rows
#     ]


# def _recruiter_workload():
#     """Per-recruiter *current* load for the Admin's recruiter-monitoring view:
#     active (non-terminal) requirements they own, and candidates they're actively
#     moving through the pipeline. Heaviest load first; idle recruiters omitted."""
#     req_counts = dict(
#         RequirementTracker.objects
#         .filter(recruiter__isnull=False, is_active=True)
#         .exclude(req_status__status_code__in=TERMINAL_REQ_STATUSES)
#         .order_by().values_list("recruiter").annotate(c=Count("req_id"))
#     )
#     cand_counts = dict(
#         JdCvMapping.objects
#         .filter(req__recruiter__isnull=False, application_stage__status_code__in=ACTIVE_PIPELINE_STATUSES)
#         .order_by().values_list("req__recruiter").annotate(c=Count("candidate", distinct=True))
#     )
#     rows = [
#         {
#             "recruiter": r.full_name,
#             "requirements": req_counts.get(r.user_id, 0),
#             "candidates": cand_counts.get(r.user_id, 0),
#         }
#         for r in UserMaster.objects.filter(role__role_code=Roles.RECRUITER, is_active=True).order_by("full_name")
#     ]
#     rows = [r for r in rows if r["requirements"] or r["candidates"]]
#     rows.sort(key=lambda x: x["requirements"] + x["candidates"], reverse=True)
#     return rows


# def _recent_candidates(qs, limit=5):
#     rows = qs.select_related("candidate_status").order_by("-cv_id")[:limit]
#     return [
#         {
#             "cv_serial": c.cv_serial,
#             "candidate_name": c.candidate_name,
#             "status": c.candidate_status.status_name if c.candidate_status_id else None,
#             "created_on": c.created_on.isoformat() if c.created_on else None,
#         }
#         for c in rows
#     ]


# def _active_requirements(reqs):
#     return reqs.filter(is_active=True).exclude(req_status__status_code__in=TERMINAL_REQ_STATUSES)


# def _top_clients(active_reqs, limit=6):
#     """Clients with the most current hiring activity — active requirements and
#     the open seats across them (client monitoring). "Open seats" is the real
#     per-seat Open-status count (same source of truth as every other
#     open-positions figure on this dashboard) — previously the cached
#     positions_open/positions_filled rollup, which disagreed with the Admin
#     KPI (see Dashboard_Testing_Guide.md, Finding #1). requirements uses
#     distinct=True because joining in the open-seats count fans out the
#     requirement rows; without it "requirements" would be inflated by each
#     client's seat count."""
#     rows = (
#         active_reqs.filter(client__isnull=False)
#         .values("client__client_name")
#         .annotate(
#             requirements=Count("req_id", distinct=True),
#             open_positions=Count(
#                 "requirementposition",
#                 filter=Q(requirementposition__position_status__status_code=PositionStatus.OPEN),
#                 distinct=True,
#             ),
#         )
#         .order_by("-requirements", "-open_positions")[:limit]
#     )
#     return [
#         {"client_name": r["client__client_name"], "requirements": r["requirements"], "open_positions": r["open_positions"]}
#         for r in rows
#     ]


# def _stalled_requirements(reqs, now, limit=6):
#     """Active requirements with open seats that have seen no movement (neither the
#     requirement nor any of its applications updated) for STALE_DAYS+ days — the
#     Admin's 'needs attention' list."""
#     threshold = now - timedelta(days=STALE_DAYS)
#     qs = (
#         _active_requirements(reqs)
#         .annotate(
#             # Real per-seat Open-status count, not the cached rollup (Finding #1).
#             # distinct=True guards against fan-out from the jdcvmapping join below.
#             open_seats=Count(
#                 "requirementposition",
#                 filter=Q(requirementposition__position_status__status_code=PositionStatus.OPEN),
#                 distinct=True,
#             ),
#             last_activity=Max("jdcvmapping__updated_on"),
#         )
#         .filter(open_seats__gt=0)
#         .select_related("client", "recruiter", "req_status")
#     )
#     rows = []
#     for r in qs:
#         last = max([d for d in (r.last_activity, r.updated_on, r.created_on) if d], default=None)
#         if last is None or last > threshold:
#             continue
#         rows.append({
#             "req_tracker_no": r.req_tracker_no,
#             "jd_role_name": r.jd_role_name,
#             "client_name": r.client.client_name if r.client_id is not None else None,
#             "recruiter_name": r.recruiter.full_name if r.recruiter_id is not None else None,
#             "status": r.req_status.status_name if r.req_status_id is not None else None,
#             "open_positions": r.open_seats,
#             "idle_days": (now - last).days,
#         })
#     rows.sort(key=lambda x: x["idle_days"], reverse=True)
#     return rows[:limit]


# def _admin_tasks(active_reqs, now):
#     """Genuine Admin oversight to-dos (ownership + user administration) — not
#     recruiter-owned work. Always returned (a zero count reads as 'all clear')."""
#     hold_threshold = now - timedelta(days=30)
#     no_recruiter = active_reqs.filter(recruiter__isnull=True).count()
#     no_hiring_mgr = active_reqs.filter(hiring_mgr__isnull=True).count()
#     inactive_users = UserMaster.objects.filter(is_active=False).count()
#     long_holds = (
#         RequirementTracker.objects
#         .filter(req_status__status_code=ReqStatus.HOLD)
#         .filter(Q(updated_on__lt=hold_threshold) | Q(updated_on__isnull=True, created_on__lt=hold_threshold))
#         .count()
#     )
#     # Possible-duplicate candidates awaiting review (PENDING only — reviewed/merged/
#     # dismissed are excluded). Deep-links to the Duplicate Review screen.
#     pending_duplicates = CandidateDuplicateReview.objects.filter(
#         review_status=DuplicateReview.PENDING
#     ).count()
#     return [
#         {"key": "requirements_without_recruiter", "label": "Requirements without a recruiter", "count": no_recruiter},
#         {"key": "requirements_without_hiring_manager", "label": "Requirements without a hiring manager", "count": no_hiring_mgr},
#         {"key": "possible_duplicate_review", "label": "Possible duplicates to review", "count": pending_duplicates},
#         {"key": "requirements_on_hold_30d", "label": "On hold over 30 days", "count": long_holds},
#         {"key": "inactive_users", "label": "Inactive users", "count": inactive_users},
#     ]


# def _recent_activity(limit=8):
#     """The cross-entity audit feed (activity_log) — newest first."""
#     rows = ActivityLog.objects.order_by("-created_on", "-activity_id")[:limit]
#     return [
#         {
#             "type": a.activity_type,
#             "title": a.summary,
#             "ref": a.req.req_tracker_no if a.req_id else None,
#             "when": a.created_on.isoformat() if a.created_on else None,
#         }
#         for a in rows
#     ]


# def build_dashboard(user):
#     role = user.role.role_code

#     if role == Roles.ADMIN:
#         now = timezone.now()
#         month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
#         reqs = RequirementTracker.objects.all()
#         active_reqs = _active_requirements(reqs)
#         workload = _recruiter_workload()

#         active_requirements = active_reqs.count()
#         open_positions = RequirementPosition.objects.filter(
#             position_status__status_code=PositionStatus.OPEN
#         ).count()
#         # is_closed=False excludes candidates who already Joined or were
#         # Rejected/etc. but are still parked at their last active-looking stage
#         # value (see Dashboard_Testing_Guide.md, Finding #2).
#         in_pipeline = (
#             JdCvMapping.objects
#             .filter(application_stage__status_code__in=ACTIVE_PIPELINE_STATUSES, is_closed=False)
#             .values("candidate").distinct().count()
#         )
#         joined_this_month = JdCvMapping.objects.filter(joined_date__gte=month_start.date()).count()
#         active_clients = active_reqs.filter(client__isnull=False).values("client").distinct().count()
#         total_positions, filled_positions = _position_totals(RequirementPosition.objects.all())
#         # Admin sees the WHOLE recruitable candidate database (not scoped to review
#         # pools) — every candidate not in a non-recruitable status.
#         candidates_available = CandidateMaster.objects.exclude(
#             candidate_status__status_code__in=CandidateStatus.DB_DEFAULT_HIDDEN
#         ).count()

#         return {
#             "role": role,
#             "kpis": [
#                 _kpi("active_requirements", "Active Requirements", active_requirements),
#                 _kpi("total_positions", "Total Positions", total_positions),
#                 _kpi("total_filled_positions", "Filled Positions", filled_positions),
#                 _kpi("open_positions", "Open Positions", open_positions),
#                 _kpi("in_pipeline", "In Pipeline", in_pipeline, hint="candidates"),
#                 _kpi("candidates_available", "Candidates Available", candidates_available, hint="recruitable"),
#                 _kpi("joined_this_month", "Joined This Month", joined_this_month),
#                 _kpi("active_recruiters", "Active Recruiters", len(workload)),
#                 _kpi("active_clients", "Active Clients", active_clients),
#             ],
#             "requirement_status": _status_breakdown(reqs, "req_status__status_name", "req_id"),
#             "pipeline_stages": _pipeline_stages(JdCvMapping.objects.all()),
#             "recruiter_workload": workload,
#             "top_clients": _top_clients(active_reqs),
#             "admin_tasks": _admin_tasks(active_reqs, now),
#             "stalled_requirements": _stalled_requirements(reqs, now),
#             "recent_requirements": _recent_requirements(reqs),
#             "recent_activity": _recent_activity(),
#         }

#     if role == Roles.HIRING_MANAGER:
#         reqs = RequirementTracker.objects.filter(hiring_mgr=user)
#         mappings = JdCvMapping.objects.filter(req__hiring_mgr=user)
#         total_positions, filled_positions = _position_totals(
#             RequirementPosition.objects.filter(req__hiring_mgr=user)
#         )
#         return {
#             "role": role,
#             "kpis": [
#                 _kpi("my_requirements", "My Requirements", reqs.count()),
#                 _kpi("total_positions", "Total Positions", total_positions),
#                 _kpi("total_filled_positions", "Filled Positions", filled_positions),
#                 _kpi("open_positions", "Open Positions", _open_positions(reqs.filter(is_active=True))),
#                 # Excludes already-closed applications (Finding #2) — same fix as
#                 # Admin's in_pipeline KPI and _pipeline_stages() above.
#                 _kpi("in_pipeline", "Candidates in Pipeline", mappings.filter(is_closed=False).count()),
#             ],
#             "requirement_status": _status_breakdown(reqs, "req_status__status_name", "req_id"),
#             "pipeline_stages": _pipeline_stages(mappings),
#             "recent_requirements": _recent_requirements(reqs),
#         }

#     # Recruiter
#     reqs = RequirementTracker.objects.filter(recruiter=user)
#     mappings = JdCvMapping.objects.filter(req__recruiter=user)
#     # "Candidates Available" = candidates genuinely available for THIS recruiter to
#     # process: those under active review (Review Pool) for their assigned
#     # requirements, excluding non-recruitable statuses (Reject-Hold / Joined / Fake
#     # / Blacklisted). Not "who uploaded them" — uploads are often bulk/admin-sourced.
#     review_cv_ids = (
#         CandidateRequirementReview.objects
#         .filter(req__recruiter=user, status=ReviewStatus.ACTIVE)
#         .values_list("candidate_id", flat=True)
#     )
#     recruitable = (
#         CandidateMaster.objects
#         .filter(cv_id__in=review_cv_ids)
#         .exclude(candidate_status__status_code__in=CandidateStatus.DB_DEFAULT_HIDDEN)
#         .distinct()
#     )
#     total_positions, filled_positions = _position_totals(
#         RequirementPosition.objects.filter(req__recruiter=user)
#     )
#     now = timezone.now()
#     upcoming_qs = (
#         mappings.filter(screening_datetime__gte=now)
#         .select_related("candidate", "req", "application_stage")
#         .order_by("screening_datetime")[:5]
#     )
#     return {
#         "role": role,
#         "kpis": [
#             _kpi("assigned_requirements", "Assigned Requirements", reqs.count()),
#             _kpi("total_positions", "Total Positions", total_positions),
#             _kpi("total_filled_positions", "Filled Positions", filled_positions),
#             _kpi("candidates_available", "Candidates Available", recruitable.count(), hint="recruitable"),
#             # Excludes already-closed applications (Finding #2) — same fix as the
#             # Admin and HM in_pipeline KPIs above.
#             _kpi("in_pipeline", "In Pipeline", mappings.filter(is_closed=False).count()),
#             _kpi("upcoming_screenings", "Upcoming Screenings", mappings.filter(screening_datetime__gte=now).count()),
#         ],
#         "pipeline_stages": _pipeline_stages(mappings),
#         "upcoming_screenings": [
#             {
#                 "candidate_name": m.candidate.candidate_name,
#                 "req_tracker_no": m.req.req_tracker_no,
#                 "screening_datetime": m.screening_datetime.isoformat() if m.screening_datetime else None,
#                 "status": m.application_stage.status_name if m.application_stage_id else None,
#             }
#             for m in upcoming_qs
#         ],
#         "recent_candidates": _recent_candidates(recruitable),
#     }


"""
Role-aware dashboard aggregations (read-only).

Returns a single payload tailored to the caller's role so the frontend can
render its whole bento grid from one request. Pure ORM aggregation — no writes.
"""
from datetime import timedelta

from django.db.models import Count, Max, Q
from django.utils import timezone

from core.constants import (
    ApplicationStatus, CandidateStatus, DuplicateReview, PositionStatus, ReqStatus,
    ReviewStatus, Roles,
)

from .models import (
    ActivityLog,
    CandidateDuplicateReview,
    CandidateMaster,
    CandidateRequirementReview,
    JdCvMapping,
    RequirementPosition,
    RequirementTracker,
    UserMaster,
)

# A requirement is "active" (still being worked) unless it's in a terminal state.
# (Expiry is a derived overlay, not a stored status — see ReqStatus.TERMINAL.)
TERMINAL_REQ_STATUSES = set(ReqStatus.TERMINAL)
# An application is "in pipeline" while it's in flight (not a terminal outcome).
ACTIVE_PIPELINE_STATUSES = {
    ApplicationStatus.SHORTLISTED, ApplicationStatus.JD_EMAIL_SENT,
    ApplicationStatus.SCREENING_SCHEDULED, ApplicationStatus.OK_TO_PROCEED,
    ApplicationStatus.OFFERED, ApplicationStatus.AWAITING_JOINING,
}
# A requirement with open seats and no activity for this many days is "stalled".
STALE_DAYS = 14


def _kpi(key, label, value, hint=None):
    item = {"key": key, "label": label, "value": value or 0}
    if hint:
        item["hint"] = hint
    return item


def _status_breakdown(qs, status_field, pk_field):
    rows = qs.values(status_field).annotate(count=Count(pk_field)).order_by("-count")
    return [{"status": r[status_field] or "Unknown", "count": r["count"]} for r in rows]


def _open_positions(reqs_qs):
    """Real-time open seats for a (role-scoped) RequirementTracker qs — counts
    requirement_position rows whose OWN seat status is Open, the same source of
    truth as the Admin dashboard's top-level `open_positions` KPI. Previously
    summed the cached positions_open/positions_filled rollup on
    requirement_tracker instead, which can silently drift out of sync with the
    real per-seat status (see Dashboard_Testing_Guide.md, Finding #1)."""
    return RequirementPosition.objects.filter(
        req__in=reqs_qs, position_status__status_code=PositionStatus.OPEN
    ).count()


def _position_totals(positions_qs):
    """Total seats + filled seats over a (role-scoped) RequirementPosition qs, in
    ONE aggregate query. Returns (total, filled)."""
    agg = positions_qs.aggregate(
        total=Count("position_id"),
        filled=Count("position_id", filter=Q(position_status__status_code=PositionStatus.FILLED)),
    )
    return agg["total"] or 0, agg["filled"] or 0


# The recruitment pipeline chart — the STAGES (candidate position) in flow order,
# rendered from EXISTING application-stage data (zero-filled). Matches the Pipeline
# board exactly: applications begin at Shortlisted. Pre-pipeline "New CV"
# candidates (awaiting resume review) are reported by a SEPARATE KPI, not here.
# Outcomes (Joined, Rejected, Offer Declined, Withdrawn, …) are excluded — they
# remain in candidate history, reports and analytics.
_PIPELINE_STAGES = [
    (ApplicationStatus.SHORTLISTED, "Shortlisted"),
    (ApplicationStatus.JD_EMAIL_SENT, "JD Email Sent"),
    (ApplicationStatus.SCREENING_SCHEDULED, "Screening Scheduled"),
    (ApplicationStatus.OK_TO_PROCEED, "OK to Proceed"),
    (ApplicationStatus.OFFERED, "Offer Released"),
    (ApplicationStatus.AWAITING_JOINING, "Awaiting Joining"),
]


def _pipeline_stages(mappings_qs):
    """Count a (role-scoped) mappings qs per application stage and return the full
    pipeline flow in canonical order (0-filled), in ONE query. Excludes closed
    applications (is_closed=True) — a candidate who has already Joined or been
    Rejected stays parked at their last STAGE value forever otherwise, silently
    inflating that stage's count (see Dashboard_Testing_Guide.md, Finding #2)."""
    counts = dict(
        mappings_qs.filter(is_closed=False)
        .values_list("application_stage__status_code")
        .annotate(c=Count("mapping_id"))
        .values_list("application_stage__status_code", "c")
    )
    return [{"status": label, "count": counts.get(code, 0)} for code, label in _PIPELINE_STAGES]


def _recent_requirements(qs, limit=5):
    rows = (
        qs.select_related("client", "recruiter", "req_status")
        .annotate(
            open_seats=Count(
                "requirementposition",
                filter=Q(requirementposition__position_status__status_code=PositionStatus.OPEN),
                distinct=True,
            )
        )
        .order_by("-req_id")[:limit]
    )
    return [
        {
            "req_tracker_no": r.req_tracker_no,
            "jd_role_name": r.jd_role_name,
            # client_id is 0-eligible (Category 2 default row) — must use "is not
            # None", not a truthy check (see Dashboard_Testing_Guide.md, id-0 bug).
            "client_name": r.client.client_name if r.client_id is not None else None,
            "recruiter_name": r.recruiter.full_name if r.recruiter_id is not None else None,
            "status": r.req_status.status_name if r.req_status_id is not None else None,
            "req_date": r.req_date.isoformat() if r.req_date else None,
            "positions_required": r.positions_open or 0,
            "positions_filled": r.positions_filled or 0,
            # Real per-seat Open-status count, not the cached rollup (Finding #1).
            "positions_open": r.open_seats,
        }
        for r in rows
    ]


def _recruiter_workload():
    """Per-recruiter *current* load for the Admin's recruiter-monitoring view:
    active (non-terminal) requirements they own, and candidates they're actively
    moving through the pipeline. Heaviest load first; idle recruiters omitted."""
    req_counts = dict(
        RequirementTracker.objects
        .filter(recruiter__isnull=False, is_active=True)
        .exclude(req_status__status_code__in=TERMINAL_REQ_STATUSES)
        .order_by().values_list("recruiter").annotate(c=Count("req_id"))
    )
    cand_counts = dict(
        JdCvMapping.objects
        .filter(req__recruiter__isnull=False, application_stage__status_code__in=ACTIVE_PIPELINE_STATUSES)
        .order_by().values_list("req__recruiter").annotate(c=Count("candidate", distinct=True))
    )
    rows = [
        {
            "recruiter": r.full_name,
            "requirements": req_counts.get(r.user_id, 0),
            "candidates": cand_counts.get(r.user_id, 0),
        }
        for r in UserMaster.objects.filter(role__role_code=Roles.RECRUITER, is_active=True).order_by("full_name")
    ]
    rows = [r for r in rows if r["requirements"] or r["candidates"]]
    rows.sort(key=lambda x: x["requirements"] + x["candidates"], reverse=True)
    return rows


def _recent_candidates(qs, limit=5):
    rows = qs.select_related("candidate_status").order_by("-cv_id")[:limit]
    return [
        {
            "cv_serial": c.cv_serial,
            "candidate_name": c.candidate_name,
            "status": c.candidate_status.status_name if c.candidate_status_id else None,
            "created_on": c.created_on.isoformat() if c.created_on else None,
        }
        for c in rows
    ]


def _active_requirements(reqs):
    return reqs.filter(is_active=True).exclude(req_status__status_code__in=TERMINAL_REQ_STATUSES)


def _top_clients(active_reqs, limit=6):
    """Clients with the most current hiring activity — active requirements and
    the open seats across them (client monitoring). "Open seats" is the real
    per-seat Open-status count (same source of truth as every other
    open-positions figure on this dashboard) — previously the cached
    positions_open/positions_filled rollup, which disagreed with the Admin
    KPI (see Dashboard_Testing_Guide.md, Finding #1). requirements uses
    distinct=True because joining in the open-seats count fans out the
    requirement rows; without it "requirements" would be inflated by each
    client's seat count."""
    rows = (
        active_reqs.filter(client__isnull=False)
        .values("client__client_name")
        .annotate(
            requirements=Count("req_id", distinct=True),
            open_positions=Count(
                "requirementposition",
                filter=Q(requirementposition__position_status__status_code=PositionStatus.OPEN),
                distinct=True,
            ),
        )
        .order_by("-requirements", "-open_positions")[:limit]
    )
    return [
        {"client_name": r["client__client_name"], "requirements": r["requirements"], "open_positions": r["open_positions"]}
        for r in rows
    ]


def _stalled_requirements(reqs, now, limit=6):
    """Active requirements with open seats that have seen no movement (neither the
    requirement nor any of its applications updated) for STALE_DAYS+ days — the
    Admin's 'needs attention' list."""
    threshold = now - timedelta(days=STALE_DAYS)
    qs = (
        _active_requirements(reqs)
        .annotate(
            # Real per-seat Open-status count, not the cached rollup (Finding #1).
            # distinct=True guards against fan-out from the jdcvmapping join below.
            open_seats=Count(
                "requirementposition",
                filter=Q(requirementposition__position_status__status_code=PositionStatus.OPEN),
                distinct=True,
            ),
            last_activity=Max("jdcvmapping__updated_on"),
        )
        .filter(open_seats__gt=0)
        .select_related("client", "recruiter", "req_status")
    )
    rows = []
    for r in qs:
        last = max([d for d in (r.last_activity, r.updated_on, r.created_on) if d], default=None)
        if last is None or last > threshold:
            continue
        rows.append({
            "req_tracker_no": r.req_tracker_no,
            "jd_role_name": r.jd_role_name,
            "client_name": r.client.client_name if r.client_id is not None else None,
            "recruiter_name": r.recruiter.full_name if r.recruiter_id is not None else None,
            "status": r.req_status.status_name if r.req_status_id is not None else None,
            "open_positions": r.open_seats,
            "idle_days": (now - last).days,
        })
    rows.sort(key=lambda x: x["idle_days"], reverse=True)
    return rows[:limit]


def _admin_tasks(active_reqs, now):
    """Genuine Admin oversight to-dos (ownership + user administration) — not
    recruiter-owned work. Always returned (a zero count reads as 'all clear')."""
    hold_threshold = now - timedelta(days=30)
    no_recruiter = active_reqs.filter(recruiter__isnull=True).count()
    no_hiring_mgr = active_reqs.filter(hiring_mgr__isnull=True).count()
    inactive_users = UserMaster.objects.filter(is_active=False).count()
    long_holds = (
        RequirementTracker.objects
        .filter(req_status__status_code=ReqStatus.HOLD)
        .filter(Q(updated_on__lt=hold_threshold) | Q(updated_on__isnull=True, created_on__lt=hold_threshold))
        .count()
    )
    # Possible-duplicate candidates awaiting review (PENDING only — reviewed/merged/
    # dismissed are excluded). Deep-links to the Duplicate Review screen.
    pending_duplicates = CandidateDuplicateReview.objects.filter(
        review_status=DuplicateReview.PENDING
    ).count()
    return [
        {"key": "requirements_without_recruiter", "label": "Requirements without a recruiter", "count": no_recruiter},
        {"key": "requirements_without_hiring_manager", "label": "Requirements without a hiring manager", "count": no_hiring_mgr},
        {"key": "possible_duplicate_review", "label": "Possible duplicates to review", "count": pending_duplicates},
        {"key": "requirements_on_hold_30d", "label": "On hold over 30 days", "count": long_holds},
        {"key": "inactive_users", "label": "Inactive users", "count": inactive_users},
    ]


def _recent_activity(limit=8):
    """The cross-entity audit feed (activity_log) — newest first."""
    rows = ActivityLog.objects.order_by("-created_on", "-activity_id")[:limit]
    return [
        {
            "type": a.activity_type,
            "title": a.summary,
            "ref": a.req.req_tracker_no if a.req_id else None,
            "when": a.created_on.isoformat() if a.created_on else None,
        }
        for a in rows
    ]


def build_dashboard(user):
    role = user.role.role_code

    if role == Roles.ADMIN:
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        reqs = RequirementTracker.objects.all()
        active_reqs = _active_requirements(reqs)
        workload = _recruiter_workload()

        active_requirements = active_reqs.count()
        open_positions = RequirementPosition.objects.filter(
            position_status__status_code=PositionStatus.OPEN
        ).count()
        # is_closed=False excludes candidates who already Joined or were
        # Rejected/etc. but are still parked at their last active-looking stage
        # value (see Dashboard_Testing_Guide.md, Finding #2).
        in_pipeline = (
            JdCvMapping.objects
            .filter(application_stage__status_code__in=ACTIVE_PIPELINE_STATUSES, is_closed=False)
            .values("candidate").distinct().count()
        )
        joined_this_month = JdCvMapping.objects.filter(joined_date__gte=month_start.date()).count()
        active_clients = active_reqs.filter(client__isnull=False).values("client").distinct().count()
        total_positions, filled_positions = _position_totals(RequirementPosition.objects.all())
        # Admin sees the WHOLE recruitable candidate database (not scoped to review
        # pools) — every candidate not in a non-recruitable status.
        candidates_available = CandidateMaster.objects.exclude(
            candidate_status__status_code__in=CandidateStatus.DB_DEFAULT_HIDDEN
        ).count()

        return {
            "role": role,
            "kpis": [
                _kpi("active_requirements", "Active Requirements", active_requirements),
                _kpi("total_positions", "Total Positions", total_positions),
                _kpi("total_filled_positions", "Filled Positions", filled_positions),
                _kpi("open_positions", "Open Positions", open_positions),
                _kpi("in_pipeline", "In Pipeline", in_pipeline, hint="candidates"),
                _kpi("candidates_available", "Candidates Available", candidates_available, hint="recruitable"),
                _kpi("joined_this_month", "Joined This Month", joined_this_month),
                _kpi("active_recruiters", "Active Recruiters", len(workload)),
                _kpi("active_clients", "Active Clients", active_clients),
            ],
            "requirement_status": _status_breakdown(reqs, "req_status__status_name", "req_id"),
            "pipeline_stages": _pipeline_stages(JdCvMapping.objects.all()),
            "recruiter_workload": workload,
            "top_clients": _top_clients(active_reqs),
            "admin_tasks": _admin_tasks(active_reqs, now),
            "stalled_requirements": _stalled_requirements(reqs, now),
            "recent_requirements": _recent_requirements(reqs),
            "recent_activity": _recent_activity(),
        }

    if role == Roles.HIRING_MANAGER:
        reqs = RequirementTracker.objects.filter(hiring_mgr=user)
        mappings = JdCvMapping.objects.filter(req__hiring_mgr=user)
        total_positions, filled_positions = _position_totals(
            RequirementPosition.objects.filter(req__hiring_mgr=user)
        )
        return {
            "role": role,
            "kpis": [
                _kpi("my_requirements", "My Requirements", reqs.count()),
                _kpi("total_positions", "Total Positions", total_positions),
                _kpi("total_filled_positions", "Filled Positions", filled_positions),
                _kpi("open_positions", "Open Positions", _open_positions(reqs.filter(is_active=True))),
                # Excludes already-closed applications (Finding #2) — same fix as
                # Admin's in_pipeline KPI and _pipeline_stages() above.
                _kpi("in_pipeline", "Candidates in Pipeline", mappings.filter(is_closed=False).count()),
            ],
            "requirement_status": _status_breakdown(reqs, "req_status__status_name", "req_id"),
            "pipeline_stages": _pipeline_stages(mappings),
            "recent_requirements": _recent_requirements(reqs),
        }

    # Recruiter
    reqs = RequirementTracker.objects.filter(recruiter=user)
    mappings = JdCvMapping.objects.filter(req__recruiter=user)
    # "Candidates Available" = candidates genuinely available for THIS recruiter to
    # process: those under active review (Review Pool) for their assigned
    # requirements, excluding non-recruitable statuses (Reject-Hold / Joined / Fake
    # / Blacklisted). Not "who uploaded them" — uploads are often bulk/admin-sourced.
    review_cv_ids = (
        CandidateRequirementReview.objects
        .filter(req__recruiter=user, status=ReviewStatus.ACTIVE)
        .values_list("candidate_id", flat=True)
    )
    recruitable = (
        CandidateMaster.objects
        .filter(cv_id__in=review_cv_ids)
        .exclude(candidate_status__status_code__in=CandidateStatus.DB_DEFAULT_HIDDEN)
        .distinct()
    )
    total_positions, filled_positions = _position_totals(
        RequirementPosition.objects.filter(req__recruiter=user)
    )
    now = timezone.now()
    # "Upcoming" means still genuinely waiting on that scheduled screening: the
    # application must still actually BE at the Screening Scheduled stage, and
    # not already closed. screening_datetime is a one-way field — it gets SET
    # when a screening is booked but is never cleared as the application moves
    # on (Passed → Offered → Awaiting Joining → Joined, or Rejected), so a
    # `screening_datetime__gte=now` filter alone keeps matching that same old
    # mapping forever, long after the screening is no longer "upcoming" for
    # any real sense of the word — surfaced by a candidate who was screened,
    # progressed to Joined, and still showed up here with a stale "Awaiting
    # Joining" status label.
    upcoming_filter = Q(
        application_stage__status_code=ApplicationStatus.SCREENING_SCHEDULED,
        is_closed=False,
        screening_datetime__gte=now,
    )
    upcoming_qs = (
        mappings.filter(upcoming_filter)
        .select_related("candidate", "req", "application_stage")
        .order_by("screening_datetime")[:5]
    )
    return {
        "role": role,
        "kpis": [
            _kpi("assigned_requirements", "Assigned Requirements", reqs.count()),
            _kpi("total_positions", "Total Positions", total_positions),
            _kpi("total_filled_positions", "Filled Positions", filled_positions),
            _kpi("candidates_available", "Candidates Available", recruitable.count(), hint="recruitable"),
            # Excludes already-closed applications (Finding #2) — same fix as the
            # Admin and HM in_pipeline KPIs above.
            _kpi("in_pipeline", "In Pipeline", mappings.filter(is_closed=False).count()),
            _kpi("upcoming_screenings", "Upcoming Screenings", mappings.filter(upcoming_filter).count()),
        ],
        "pipeline_stages": _pipeline_stages(mappings),
        "upcoming_screenings": [
            {
                "candidate_name": m.candidate.candidate_name,
                "req_tracker_no": m.req.req_tracker_no,
                "screening_datetime": m.screening_datetime.isoformat() if m.screening_datetime else None,
                "status": m.application_stage.status_name if m.application_stage_id else None,
            }
            for m in upcoming_qs
        ],
        "recent_candidates": _recent_candidates(recruitable),
    }
