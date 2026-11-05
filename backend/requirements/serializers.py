"""
Serializers for the Requirement domain.

Two of them, on purpose:
  - WriteSerializer: what the client SENDS (foreign keys by id) + validation.
  - ReadSerializer:  what the API RETURNS (ids + friendly display names).
This keeps input and output concerns separate and the payloads clean.
"""
from rest_framework import serializers

from admin_module.models import RequirementPosition, RequirementTracker, StatusChangeHistory
from core.constants import PositionSource, PositionStatus


class RequirementPositionSerializer(serializers.ModelSerializer):
    """A single seat within a requirement, with friendly status + the candidate
    (via the winning application) who filled it, if any."""
    position_status_code = serializers.CharField(source="position_status.status_code", read_only=True)
    position_status_name = serializers.CharField(source="position_status.status_name", read_only=True)
    filled_by_candidate = serializers.SerializerMethodField()
    # True when this seat was Inactivated by a requirement action (not a human) —
    # the UI shows it as system-managed / read-only.
    auto_inactive = serializers.SerializerMethodField()

    class Meta:
        model = RequirementPosition
        fields = [
            "position_id", "req", "position_no", "position_status",
            "position_status_code", "position_status_name", "status_source",
            "auto_inactive", "filled_by_mapping", "filled_by_candidate",
            "is_active", "created_on", "updated_on",
        ]

    def get_filled_by_candidate(self, obj):
        m = obj.filled_by_mapping
        return m.candidate.candidate_name if m and m.candidate_id else None

    def get_auto_inactive(self, obj):
        return obj.status_source in PositionSource.AUTO


class StatusChangeHistorySerializer(serializers.ModelSerializer):
    """Read view of the unified requirement/position status audit."""
    changed_by_name = serializers.CharField(source="changed_by.full_name", read_only=True)

    class Meta:
        model = StatusChangeHistory
        fields = [
            "history_id", "entity_type", "entity_id", "previous_status",
            "new_status", "reason", "change_type", "changed_by", "changed_by_name",
            "changed_on",
        ]


class RequirementWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequirementTracker
        fields = [
            "client", "client_mgr", "hiring_mgr", "recruiter", "req_type",
            "jd_role_name", "client_req_id", "location", "exp_min", "exp_max",
            "jd_rate_lpa", "np", "priority", "positions_open",
            "skill1", "skill2", "skill3", "assigned_date",
            # "Required by" (user business deadline) → target_fill_date. req_date is
            # the system creation date (set server-side), NOT user-writable.
            "target_fill_date", "jd_text", "comments",
        ]
        # req_status is deliberately NOT writable: the requirement status is
        # event-driven (create→New, assign→Assigned, first link→Open), derived
        # from positions (Partial/Close Filled), or set via the guarded
        # set-status action (Hold/Resume/Cancel). It can never be set by the client.
        extra_kwargs = {
            # The service defaults this, so the client need not send it.
            "hiring_mgr": {"required": False},
        }

    def validate(self, attrs):
        # Experience range sanity (mirrors the DB check constraint).
        exp_min, exp_max = attrs.get("exp_min"), attrs.get("exp_max")
        if exp_min is not None and exp_max is not None and exp_max < exp_min:
            raise serializers.ValidationError({"exp_max": "exp_max must be greater than or equal to exp_min."})

        # Doc rule: a client manager must belong to the chosen client.
        client, mgr = attrs.get("client"), attrs.get("client_mgr")
        if mgr and client and mgr.client_id != client.client_id:
            raise serializers.ValidationError(
                {"client_mgr": "The selected client manager does not belong to the selected client."}
            )

        # positions_filled cannot exceed positions_open (mirrors DB constraint).
        positions_open = attrs.get("positions_open")
        if positions_open is not None and positions_open < 1:
            raise serializers.ValidationError({"positions_open": "There must be at least 1 open position."})
        return attrs


class RequirementReadSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.client_name", read_only=True)
    req_type_name = serializers.CharField(source="req_type.req_type_name", read_only=True)
    req_status_name = serializers.CharField(source="req_status.status_name", read_only=True)
    req_status_code = serializers.CharField(source="req_status.status_code", read_only=True)

    # Nullable relations — use methods to avoid traversing a None FK.
    client_mgr_name = serializers.SerializerMethodField()
    hiring_mgr_name = serializers.SerializerMethodField()
    recruiter_name = serializers.SerializerMethodField()
    location_name = serializers.SerializerMethodField()
    priority_name = serializers.SerializerMethodField()
    skill_names = serializers.SerializerMethodField()
    # Derived Expired overlay (never a stored status) + per-seat status breakdown.
    is_expired = serializers.SerializerMethodField()
    expired_on = serializers.SerializerMethodField()
    position_counts = serializers.SerializerMethodField()
    # Permanent End-Recruitment decision (recruitment_ended / _on / _by come from
    # the model via fields="__all__"); expose the actor's display name too.
    recruitment_ended_by_name = serializers.SerializerMethodField()
    # Open (active, not-closed) applications on this requirement — used by the
    # End-Recruitment confirmation summary. Uses the list annotation when present,
    # else falls back to a direct count (single-object responses).
    active_application_count = serializers.SerializerMethodField()

    class Meta:
        model = RequirementTracker
        fields = "__all__"

    def get_client_mgr_name(self, obj):
        return obj.client_mgr.manager_name if obj.client_mgr_id is not None else None

    def get_hiring_mgr_name(self, obj):
        return obj.hiring_mgr.full_name if obj.hiring_mgr_id is not None else None

    def get_recruiter_name(self, obj):
        return obj.recruiter.full_name if obj.recruiter_id is not None else None

    def get_location_name(self, obj):
        return f"{obj.location.city}, {obj.location.state}" if obj.location_id is not None else None

    def get_priority_name(self, obj):
        return obj.priority.priority_name if obj.priority_id is not None else None

    def get_skill_names(self, obj):
        return [s.skill_name for s in (obj.skill1, obj.skill2, obj.skill3) if s]

    def get_is_expired(self, obj):
        from .services import requirement_is_expired
        return requirement_is_expired(obj)

    def get_expired_on(self, obj):
        from .services import requirement_is_expired
        return obj.target_fill_date if requirement_is_expired(obj) else None

    def get_recruitment_ended_by_name(self, obj):
        return obj.recruitment_ended_by.full_name if obj.recruitment_ended_by_id is not None else None

    def get_active_application_count(self, obj):
        val = getattr(obj, "active_application_count", None)
        if val is not None:
            return val
        from admin_module.models import JdCvMapping
        return JdCvMapping.objects.filter(req=obj, is_active=True, is_closed=False).count()

    def get_position_counts(self, obj):
        """Per-status seat breakdown for the details page. Uses the prefetched
        `requirementposition_set` (the viewset prefetches it) so the list view
        stays a fixed number of queries."""
        counts = {"total": 0, "open": 0, "filled": 0, "held": 0, "cancelled": 0, "inactive": 0}
        by_code = {
            PositionStatus.OPEN: "open", PositionStatus.FILLED: "filled",
            PositionStatus.HOLD: "held", PositionStatus.CANCELLED: "cancelled",
            PositionStatus.INACTIVE: "inactive",
        }
        for seat in obj.requirementposition_set.all():
            counts["total"] += 1
            code = seat.position_status.status_code if seat.position_status_id is not None else PositionStatus.OPEN
            key = by_code.get(code)
            if key:
                counts[key] += 1
        return counts
