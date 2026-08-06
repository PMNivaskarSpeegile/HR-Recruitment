from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from .models import (
    RoleMaster,
    UserMaster,
    DomainMaster,
    CandidateStatusMaster,
    ApplicationStatusMaster,
    PositionStatusMaster,
    SkillMaster,
    ClientMaster,
    ClientManagerMaster,
    ReqStatusMaster,
    PriorityMaster,
    ReqTypeMaster,
    SourceMaster,
    LocationMaster,
    WorkModeMaster,
    NoticePeriodMaster,
    ScreeningModeMaster,
    RejectionReasonMaster,
    EmailTemplateMaster,
)

class RoleMasterSerializer(serializers.ModelSerializer):

    class Meta:
        model = RoleMaster
        fields = "__all__"


class UserMasterSerializer(serializers.ModelSerializer):
    role_code = serializers.CharField(source="role.role_code", read_only=True)
    role_name = serializers.CharField(source="role.role_name", read_only=True)

    class Meta:
        model = UserMaster
        # Never expose the password hash over the API.
        exclude = ["password_hash"]


class UserWriteSerializer(serializers.ModelSerializer):
    """Create/update users. Accepts a write-only password that is hashed.
    Password is required on create; on update it's optional (blank = keep)."""
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = UserMaster
        fields = ["user_id", "username", "full_name", "email", "mobile", "role", "is_active", "password"]

    def validate(self, attrs):
        password = attrs.get("password")
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "Password is required when creating a user."})
        # Enforce the configured AUTH_PASSWORD_VALIDATORS whenever a password is
        # supplied (create, or update with a new password). Without this the
        # validators are dead config and any weak password ("1", "password")
        # would be accepted and hashed.
        if password:
            try:
                validate_password(password, user=self.instance)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        validated_data["password_hash"] = make_password(password)
        validated_data.setdefault("is_active", True)
        validated_data["created_on"] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        if password:
            instance.password_hash = make_password(password)
        instance.updated_on = timezone.now()
        return super().update(instance, validated_data)

class DomainMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = DomainMaster
        fields = "__all__"


class CandidateStatusMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateStatusMaster
        fields = "__all__"


class ApplicationStatusMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationStatusMaster
        fields = "__all__"


class PositionStatusMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = PositionStatusMaster
        fields = "__all__"


class SkillMasterSerializer(serializers.ModelSerializer):
    # A Skill must be classified under an existing Domain. The read-only
    # domain_name comes through the FK, so a domain rename shows up everywhere
    # with no skill updates.
    domain = serializers.PrimaryKeyRelatedField(queryset=DomainMaster.objects.all(), required=True)
    domain_name = serializers.CharField(source="domain.domain_name", read_only=True)

    class Meta:
        model = SkillMaster
        fields = "__all__"

class ClientMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientMaster
        fields = "__all__"


class ClientManagerMasterSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.client_name", read_only=True)

    class Meta:
        model = ClientManagerMaster
        fields = "__all__"


class ReqStatusMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReqStatusMaster
        fields = "__all__"


class PriorityMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriorityMaster
        fields = "__all__"


class NoticePeriodMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = NoticePeriodMaster
        fields = "__all__"


class ReqTypeMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReqTypeMaster
        fields = "__all__"


class WorkModeMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkModeMaster
        fields = "__all__"


class SourceMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceMaster
        fields = "__all__"


class ScreeningModeMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScreeningModeMaster
        fields = "__all__"


class RejectionReasonMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = RejectionReasonMaster
        fields = "__all__"


class EmailTemplateMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplateMaster
        fields = "__all__"


class LocationMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationMaster
        fields = "__all__"