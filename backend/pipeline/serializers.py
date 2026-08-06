import re

from rest_framework import serializers

from admin_module.models import (
    CandidateMaster,
    CommunicationLog,
    JdCvMapping,
    RejectionReasonMaster,
    RequirementTracker,
    Screening,
    ScreeningModeMaster,
)

from candidates.serializers import CandidateReadSerializer
from core.constants import ScreeningOutcome
from .services import REVIEW_DECISIONS, TRANSITION_TARGETS


class ReviewPoolCandidateSerializer(CandidateReadSerializer):
    """Candidate read view for a requirement's review pool, plus a skill-match
    score against the selected requirement: `matched_skills` (annotated on the
    queryset) / `required_skills` (from context) and a rounded `skill_match_pct`."""
    matched_skills = serializers.IntegerField(read_only=True, default=0)
    required_skills = serializers.SerializerMethodField()
    skill_match_pct = serializers.SerializerMethodField()

    class Meta(CandidateReadSerializer.Meta):
        pass

    def get_required_skills(self, obj):
        return self.context.get("required_skills", 0)

    def get_skill_match_pct(self, obj):
        required = self.context.get("required_skills", 0)
        matched = getattr(obj, "matched_skills", 0) or 0
        return round(matched / required * 100) if required else 0


class ReviewInputSerializer(serializers.Serializer):
    """Input for UC3 review action."""
    requirement = serializers.PrimaryKeyRelatedField(queryset=RequirementTracker.objects.all())
    candidate = serializers.PrimaryKeyRelatedField(queryset=CandidateMaster.objects.all())
    decision = serializers.ChoiceField(choices=REVIEW_DECISIONS)
    rejection_reason = serializers.PrimaryKeyRelatedField(
        queryset=RejectionReasonMaster.objects.all(), required=False, allow_null=True
    )
    comments = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class SendJdInputSerializer(serializers.Serializer):
    """Input for UC4 send-JD action and the preview that precedes it."""
    requirement = serializers.PrimaryKeyRelatedField(queryset=RequirementTracker.objects.all())
    mapping_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


class TransitionInputSerializer(serializers.Serializer):
    """Input for UC5 pipeline transitions (state-machine enforced in service)."""
    requirement = serializers.PrimaryKeyRelatedField(queryset=RequirementTracker.objects.all())
    mapping_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    to_status = serializers.ChoiceField(choices=TRANSITION_TARGETS)
    comments = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    screening_datetime = serializers.DateTimeField(required=False, allow_null=True)
    screening_mode = serializers.PrimaryKeyRelatedField(
        queryset=ScreeningModeMaster.objects.all(), required=False, allow_null=True
    )
    rejection_reason = serializers.PrimaryKeyRelatedField(
        queryset=RejectionReasonMaster.objects.all(), required=False, allow_null=True
    )


class JdCvMappingSerializer(serializers.ModelSerializer):
    """Read view of a pipeline (jd_cv_mapping) row with friendly fields."""
    candidate_name = serializers.CharField(source="candidate.candidate_name", read_only=True)
    cv_serial = serializers.CharField(source="candidate.cv_serial", read_only=True)
    mobile = serializers.CharField(source="candidate.mobile", read_only=True)
    email = serializers.CharField(source="candidate.email", read_only=True)
    # STAGE and OUTCOME are independent: application_stage = current stage;
    # latest_outcome = last recorded disposition; is_closed = terminal.
    application_stage_name = serializers.SerializerMethodField()
    application_stage_code = serializers.SerializerMethodField()
    latest_outcome_name = serializers.SerializerMethodField()
    latest_outcome_code = serializers.SerializerMethodField()
    req_tracker_no = serializers.CharField(source="req.req_tracker_no", read_only=True)
    recruiter_name = serializers.SerializerMethodField()
    screening_mode_name = serializers.SerializerMethodField()
    rejection_reason_name = serializers.SerializerMethodField()

    class Meta:
        model = JdCvMapping
        fields = [
            "mapping_id", "req", "req_tracker_no", "recruiter_name", "candidate", "cv_serial",
            "candidate_name", "mobile", "email", "application_stage",
            "application_stage_name", "application_stage_code",
            "latest_outcome", "latest_outcome_name", "latest_outcome_code",
            "is_closed", "closed_on",
            "screening_mode", "screening_mode_name",
            "screening_datetime", "rejection_reason", "rejection_reason_name",
            "comments", "created_on", "updated_on",
        ]

    def get_application_stage_name(self, obj):
        return obj.application_stage.status_name if obj.application_stage_id else None

    def get_application_stage_code(self, obj):
        return obj.application_stage.status_code if obj.application_stage_id else None

    def get_latest_outcome_name(self, obj):
        return obj.latest_outcome.status_name if obj.latest_outcome_id else None

    def get_latest_outcome_code(self, obj):
        return obj.latest_outcome.status_code if obj.latest_outcome_id else None

    def get_recruiter_name(self, obj):
        return obj.req.recruiter.full_name if obj.req_id and obj.req.recruiter_id else None

    def get_screening_mode_name(self, obj):
        return obj.screening_mode.mode_name if obj.screening_mode_id else None

    def get_rejection_reason_name(self, obj):
        return obj.rejection_reason.reason_name if obj.rejection_reason_id else None


class OutcomeInputSerializer(serializers.Serializer):
    """Record a stage OUTCOME on an application (the centralized engine)."""
    mapping = serializers.PrimaryKeyRelatedField(queryset=JdCvMapping.objects.all())
    outcome = serializers.CharField()
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    rejection_reason = serializers.PrimaryKeyRelatedField(
        queryset=RejectionReasonMaster.objects.all(), required=False, allow_null=True)
    move_to_talent_pool = serializers.BooleanField(required=False, default=False)


class AdvanceInputSerializer(serializers.Serializer):
    """Advance a stage via an ACTION (Send JD / Schedule Screening / Release Offer)."""
    mapping = serializers.PrimaryKeyRelatedField(queryset=JdCvMapping.objects.all())
    action = serializers.ChoiceField(choices=["SEND_JD", "SCHEDULE_SCREENING", "RELEASE_OFFER"])
    screening_datetime = serializers.DateTimeField(required=False, allow_null=True)
    screening_mode = serializers.PrimaryKeyRelatedField(
        queryset=ScreeningModeMaster.objects.all(), required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class RescheduleInputSerializer(serializers.Serializer):
    """Reschedule a scheduled screening (future datetime enforced in the service)."""
    mapping = serializers.PrimaryKeyRelatedField(queryset=JdCvMapping.objects.all())
    scheduled_at = serializers.DateTimeField()
    screening_mode = serializers.PrimaryKeyRelatedField(
        queryset=ScreeningModeMaster.objects.all(), required=False, allow_null=True)


class CommunicationLogSerializer(serializers.ModelSerializer):
    """Read view for the JD email tracker."""
    candidate_name = serializers.CharField(source="candidate.candidate_name", read_only=True)
    sent_by_name = serializers.CharField(source="sent_by.full_name", read_only=True)

    class Meta:
        model = CommunicationLog
        fields = [
            "comm_id", "candidate", "candidate_name", "channel", "recipient",
            "subject", "body", "status", "error_message", "sent_by", "sent_by_name",
            "sent_on",
        ]


class ScreeningSerializer(serializers.ModelSerializer):
    """Read view of one screening round (for the Screening History)."""
    screening_mode_name = serializers.CharField(source="screening_mode.mode_name", read_only=True)
    screening_mode_code = serializers.CharField(source="screening_mode.mode_code", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = Screening
        fields = [
            "screening_id", "mapping", "screening_mode", "screening_mode_name",
            "screening_mode_code", "status", "outcome", "scheduled_at",
            "interviewer", "notes", "created_by_name", "created_on",
        ]


class ScreeningScheduleInputSerializer(serializers.Serializer):
    """Input for scheduling (adding) a screening round."""
    mapping = serializers.PrimaryKeyRelatedField(queryset=JdCvMapping.objects.all())
    screening_mode = serializers.PrimaryKeyRelatedField(queryset=ScreeningModeMaster.objects.all())
    scheduled_at = serializers.DateTimeField()
    # Interviewer is mandatory: letters and single spaces only, stored Title Case.
    interviewer = serializers.CharField(required=True, allow_blank=False)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_interviewer(self, value):
        name = " ".join((value or "").split())  # trim + collapse inner whitespace
        if not name:
            raise serializers.ValidationError("Interviewer is required.")
        if not re.fullmatch(r"[A-Za-z ]+", name):
            raise serializers.ValidationError("Interviewer name may contain letters and spaces only.")
        return name.title()


class ScreeningCompleteInputSerializer(serializers.Serializer):
    """Input for recording a screening round's outcome."""
    outcome = serializers.ChoiceField(choices=ScreeningOutcome.ALL)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ScreeningRescheduleInputSerializer(serializers.Serializer):
    """Input for rescheduling a scheduled screening round (future datetime
    enforced in the service)."""
    scheduled_at = serializers.DateTimeField()
