"""
Candidate serializers.

WriteSerializer: manual single-candidate input. Note we strip the default
unique validators on mobile/email — duplicate handling is the service's job
(§7), not a blunt "already exists" rejection.

ReadSerializer: ids + friendly display names + the candidate's tagged skills.
"""
from rest_framework import serializers

from admin_module.models import (
    BulkImportBatch,
    CandidateDuplicateReview,
    CandidateMaster,
    CandidateSkill,
    RequirementTracker,
    SkillMaster,
)
from core.constants import CandidateStatus, DuplicateReview


class CandidateStatusChangeSerializer(serializers.Serializer):
    """Manual profile-status change (Fake / Blacklisted only). A reason is
    MANDATORY and recorded on the candidate timeline for audit."""
    status_code = serializers.ChoiceField(choices=CandidateStatus.MANUAL_CHANGEABLE)
    reason = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)


class CandidateStatusClearSerializer(serializers.Serializer):
    """Admin removes a Fake / Blacklisted mark, restoring the candidate to the
    Talent Pool. Reason is optional but recorded when given."""
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class CandidateWriteSerializer(serializers.ModelSerializer):
    # Optional context: tag this candidate with the requirement's 3 skills.
    requirement = serializers.PrimaryKeyRelatedField(
        queryset=RequirementTracker.objects.all(), required=False, write_only=True
    )
    # Optional explicit skills (in addition to the requirement's).
    skill_ids = serializers.PrimaryKeyRelatedField(
        queryset=SkillMaster.objects.all(), many=True, required=False, write_only=True
    )

    class Meta:
        model = CandidateMaster
        fields = [
            "candidate_name", "mobile", "email", "exp_min", "exp_max",
            "current_location", "preferred_location", "notice_period", "work_mode",
            "current_company", "current_ctc_lpa", "expected_ctc_lpa",
            "highest_qualification", "source", "is_willing_to_relocate",
            "requirement", "skill_ids",
        ]
        extra_kwargs = {
            # Duplicate handling lives in the service; don't let DRF reject first.
            "mobile": {"validators": []},
            "email": {"validators": []},
            # Model BooleanField has no default — make it optional, default False.
            "is_willing_to_relocate": {"required": False, "default": False},
        }

    def validate(self, attrs):
        exp_min, exp_max = attrs.get("exp_min"), attrs.get("exp_max")
        if exp_min is not None and exp_max is not None and exp_max < exp_min:
            raise serializers.ValidationError({"exp_max": "exp_max must be >= exp_min."})
        return attrs


class CandidateProfileUpdateSerializer(serializers.ModelSerializer):
    """Verify & Update the MASTER candidate profile (recruiter, during screening).
    Non-system fields only. Identity changes (mobile/email) are re-checked against
    duplicate detection in the service. `verified` stamps the profile verified.
    Instantiate with partial=True — every field is optional for a verify-update."""
    skill_ids = serializers.PrimaryKeyRelatedField(
        queryset=SkillMaster.objects.all(), many=True, required=False,
    )
    verified = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = CandidateMaster
        fields = [
            "candidate_name", "mobile", "email", "exp_min", "exp_max", "relevant_exp",
            "current_location", "preferred_location", "notice_period", "work_mode",
            "current_company", "current_designation", "current_ctc_lpa", "expected_ctc_lpa",
            "highest_qualification", "certifications", "additional_notes",
            # DOB / postal address are editable; age_at_import is an import snapshot
            # (read-only — never recalculated or hand-edited).
            "date_of_birth", "postal_address",
            "source", "is_willing_to_relocate", "skill_ids", "verified",
        ]
        extra_kwargs = {
            # Duplicate handling lives in the service; don't let DRF reject first.
            "mobile": {"validators": []},
            "email": {"validators": []},
        }

    def validate(self, attrs):
        exp_min, exp_max = attrs.get("exp_min"), attrs.get("exp_max")
        if exp_min is not None and exp_max is not None and exp_max < exp_min:
            raise serializers.ValidationError({"exp_max": "exp_max must be >= exp_min."})
        return attrs


class VerifyDecisionSerializer(serializers.Serializer):
    """The one recruiter decision made alongside Verify & Update (replaces the
    standalone Review). SHORTLIST / NOT_SUITABLE need a requirement; FAKE /
    BLACKLIST / SAVE are global. `move_to_talent_pool` answers the "Move candidate
    to Talent Pool?" prompt for a non-hired close."""
    decision = serializers.ChoiceField(
        choices=["SHORTLIST", "NOT_SUITABLE", "FAKE", "BLACKLIST", "SAVE"],
        required=False, allow_null=True,
    )
    requirement = serializers.PrimaryKeyRelatedField(
        queryset=RequirementTracker.objects.all(), required=False, allow_null=True,
    )
    move_to_talent_pool = serializers.BooleanField(required=False, default=False)
    decision_reason = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)


class CandidateReadSerializer(serializers.ModelSerializer):
    candidate_status_name = serializers.SerializerMethodField()
    candidate_status_code = serializers.SerializerMethodField()
    skill_ids = serializers.SerializerMethodField()
    profile_verified_by_name = serializers.SerializerMethodField()
    current_location_name = serializers.SerializerMethodField()
    notice_period_name = serializers.SerializerMethodField()
    work_mode_name = serializers.SerializerMethodField()
    source_name = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()
    skill_names = serializers.SerializerMethodField()

    class Meta:
        model = CandidateMaster
        fields = "__all__"

    def get_candidate_status_name(self, obj):
        return obj.candidate_status.status_name if obj.candidate_status_id is not None else None

    def get_candidate_status_code(self, obj):
        return obj.candidate_status.status_code if obj.candidate_status_id is not None else None

    def get_current_location_name(self, obj):
        return f"{obj.current_location.city}, {obj.current_location.state}" if obj.current_location_id is not None else None

    def get_notice_period_name(self, obj):
        return obj.notice_period.np_name if obj.notice_period_id is not None else None

    def get_work_mode_name(self, obj):
        return obj.work_mode.work_mode_name if obj.work_mode_id is not None else None

    def get_source_name(self, obj):
        return obj.source.source_name if obj.source_id is not None else None

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.full_name if obj.uploaded_by_id is not None else None

    def get_skill_names(self, obj):
        # Uses prefetched candidateskill_set to avoid N+1 (see viewset queryset).
        return [cs.skill.skill_name for cs in obj.candidateskill_set.all()]

    def get_skill_ids(self, obj):
        return [cs.skill_id for cs in obj.candidateskill_set.all()]

    def get_profile_verified_by_name(self, obj):
        return obj.profile_verified_by.full_name if obj.profile_verified_by_id is not None else None


class DuplicateReviewSerializer(serializers.ModelSerializer):
    """Read payload for the Admin Duplicate Review page — the submitted (new)
    details, the existing record it clashed with, and the full audit trail."""
    existing_candidate_detail = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CandidateDuplicateReview
        fields = [
            "review_id", "existing_candidate", "existing_candidate_detail",
            "new_candidate_name", "new_mobile", "new_email",
            "detection_reason", "review_status", "resolution", "notes",
            "created_by", "created_by_name", "created_on",
            "resolved_by", "resolved_by_name", "resolved_on",
        ]

    def get_existing_candidate_detail(self, obj):
        c = obj.existing_candidate
        if not c:
            return None
        return {
            "cv_id": c.cv_id, "cv_serial": c.cv_serial, "candidate_name": c.candidate_name,
            "mobile": c.mobile, "email": c.email, "current_company": c.current_company,
            "candidate_status_name": c.candidate_status.status_name if c.candidate_status_id is not None else None,
            "candidate_status_code": c.candidate_status.status_code if c.candidate_status_id is not None else None,
        }

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by_id is not None else None

    def get_resolved_by_name(self, obj):
        return obj.resolved_by.full_name if obj.resolved_by_id is not None else None


class DuplicateReviewCreateSerializer(serializers.ModelSerializer):
    """Recruiter submits a detected duplicate for Admin review."""
    class Meta:
        model = CandidateDuplicateReview
        fields = ["existing_candidate", "new_candidate_name", "new_mobile",
                  "new_email", "detection_reason", "submitted_payload"]


class DuplicateReviewResolveSerializer(serializers.Serializer):
    """Admin resolution. `name`/`mobile`/`email` are applied to the EXISTING
    candidate for MERGED (adopt the submitted person's details — same person) and
    CORRECTED (fix a data-entry error). Ignored for KEPT_SEPARATE."""
    resolution = serializers.ChoiceField(choices=DuplicateReview.RESOLUTIONS)
    notes = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    mobile = serializers.CharField(required=False, allow_blank=True)
    email = serializers.CharField(required=False, allow_blank=True)


class BulkImportBatchListSerializer(serializers.ModelSerializer):
    """Import-history list row (summary only — excludes the heavy row_report)."""
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)
    source_name = serializers.CharField(source="source.source_name", read_only=True)
    requirement_tracker_no = serializers.CharField(source="requirement.req_tracker_no", read_only=True)

    class Meta:
        model = BulkImportBatch
        fields = [
            "batch_id", "batch_uid", "uploaded_by", "uploaded_by_name", "file_name",
            "source", "source_name", "requirement", "requirement_tracker_no",
            "header_row", "total_rows", "created_count", "updated_count",
            "duplicate_count", "skipped_count", "status", "created_on", "completed_on",
        ]


class BulkImportBatchDetailSerializer(BulkImportBatchListSerializer):
    """Detail view — adds the full per-row report + file hash."""
    class Meta(BulkImportBatchListSerializer.Meta):
        fields = BulkImportBatchListSerializer.Meta.fields + ["file_hash", "row_report", "error_message"]
