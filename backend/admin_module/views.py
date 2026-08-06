

# Create your views here.
from rest_framework import viewsets
from .models import (RoleMaster, UserMaster,DomainMaster,CandidateStatusMaster,ApplicationStatusMaster,
PositionStatusMaster,SkillMaster,ClientMaster,ClientManagerMaster,
ReqStatusMaster,PriorityMaster,NoticePeriodMaster,ReqTypeMaster,WorkModeMaster,
SourceMaster,LocationMaster,ScreeningModeMaster,RejectionReasonMaster,EmailTemplateMaster)


from .serializers import (RoleMasterSerializer,UserMasterSerializer,DomainMasterSerializer,
CandidateStatusMasterSerializer,ApplicationStatusMasterSerializer,PositionStatusMasterSerializer,
SkillMasterSerializer,
ClientMasterSerializer,ClientManagerMasterSerializer,ReqStatusMasterSerializer,
PriorityMasterSerializer,NoticePeriodMasterSerializer,ReqTypeMasterSerializer,WorkModeMasterSerializer,
SourceMasterSerializer,LocationMasterSerializer,ScreeningModeMasterSerializer,RejectionReasonMasterSerializer,
UserWriteSerializer,EmailTemplateMasterSerializer
)

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import filters
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from authentication.permissions import CanManageReferenceData, IsAdministrator, IsAdminOrReadOnly
from core.validation import apply_normalization, generate_code, normalize_key, rules_for, validate_formats
from .dashboard_service import build_dashboard
import logging

logger = logging.getLogger("ats")

# Friendly names for the tables that may reference a master (delete messages).
import re
# A finalised master Code: uppercase, starts with a letter, letters/digits/_ only.
_STRICT_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

_REF_LABELS = {
    "requirement_tracker": "requirements",
    "candidate_master": "candidates",
    "jd_cv_mapping": "pipeline records",
    "candidate_skill": "candidate skill tags",
    "candidate_interaction": "candidate notes",
    "communication_log": "emails",
    "cv_document": "CV documents",
    "client_manager_master": "client managers",
    "user_master": "users",
    "skill_master": "skills",
}


class MasterDataViewSet(viewsets.ModelViewSet):
    """Base for all master/reference data.

    One place enforces the whole enterprise CRUD contract for every master:
    - reads open to any authenticated user; writes Admin-only;
    - input normalisation + format validation (via core.validation);
    - case-/space-insensitive duplicate prevention (create + edit), with an
      inactive-duplicate → reactivate signal (HTTP 409);
    - soft delete (deactivate) instead of hard delete, + a /references probe;
    - optimistic locking via the `expected_updated_on` token;
    - automatic created_by/on + updated_by/on audit stamps.
    """
    permission_classes = [IsAdminOrReadOnly]

    # -- helpers ---------------------------------------------------------------
    @property
    def _model(self):
        return self.queryset.model

    @property
    def _table(self):
        return self._model._meta.db_table

    def _user(self):
        user = getattr(self.request, "user", None)
        return user if getattr(user, "is_authenticated", False) else None

    def _has_field(self, name):
        return any(f.name == name for f in self._model._meta.fields)

    def get_queryset(self):
        qs = super().get_queryset()
        # Lookups (dropdowns) pass ?is_active=true so inactive rows are hidden;
        # the admin list passes nothing and sees everything. Guarded because a
        # few masters (e.g. role_master) have no is_active column.
        if self.action == "list" and self._has_field("is_active"):
            flag = self.request.query_params.get("is_active")
            if flag is not None:
                qs = qs.filter(is_active=str(flag).lower() in ("1", "true", "yes"))
        return qs

    # -- validation / duplicate detection -------------------------------------
    def _strip_unique_validators(self, serializer):
        """Remove DRF's auto unique / unique-together validators so our
        centralised duplicate logic is the single authority (it's case- and
        space-insensitive and knows the difference between an active conflict
        and an inactive row that should be reactivated)."""
        from rest_framework.validators import UniqueValidator, UniqueTogetherValidator
        serializer.validators = [
            v for v in serializer.validators if not isinstance(v, UniqueTogetherValidator)
        ]
        for field in serializer.fields.values():
            field.validators = [v for v in getattr(field, "validators", []) if not isinstance(v, UniqueValidator)]

    def _normalize_and_validate(self, serializer):
        data = serializer.validated_data
        apply_normalization(self._table, data)
        # Required model fields that collapsed to empty after normalisation
        # (skip write-only/non-model fields like the user serializer's password).
        model_fields = {f.name: f for f in self._model._meta.fields}
        blank = [
            f for f, v in data.items()
            if isinstance(v, str) and v == "" and f in model_fields and not model_fields[f].blank
        ]
        errors = validate_formats(self._table, data, required_blank_fields=blank)
        if errors:
            raise ValidationError(errors)

    def _comparable(self, field_name, value, obj=None):
        field = self._model._meta.get_field(field_name)
        if field.is_relation:
            if obj is not None:
                return getattr(obj, field_name + "_id", None)
            return value.pk if value is not None else None
        return normalize_key(value if obj is None else getattr(obj, field_name, ""))

    def _find_duplicate(self, data, exclude_pk=None):
        """Return (conflicting_row, field) for a case-/space-insensitive match
        on any unique field or unique-together group, else (None, None)."""
        rules = rules_for(self._table)
        rows = list(self._model.objects.all())
        for field in rules.get("unique", []):
            val = data.get(field)
            if val in (None, ""):
                continue
            key = normalize_key(val)
            for obj in rows:
                if exclude_pk and obj.pk == exclude_pk:
                    continue
                if normalize_key(getattr(obj, field, "") or "") == key:
                    return obj, field
        for group in rules.get("unique_together", []):
            if any(data.get(f) in (None, "") for f in group):
                continue
            target = tuple(self._comparable(f, data.get(f)) for f in group)
            for obj in rows:
                if exclude_pk and obj.pk == exclude_pk:
                    continue
                if tuple(self._comparable(f, None, obj) for f in group) == target:
                    return obj, group[-1]
        return None, None

    def _label_for(self, obj):
        return str(obj)

    def _duplicate_response_or_raise(self, data, exclude_pk=None):
        """Raise 400 for an active duplicate; return a 409 reactivation payload
        for an inactive one; return None when there's no conflict."""
        dup, field = self._find_duplicate(data, exclude_pk)
        if not dup:
            return None
        if getattr(dup, "is_active", True):
            raise ValidationError({field or "non_field_errors": ["A record with this value already exists."]})
        return Response(
            {
                "code": "inactive_duplicate",
                "detail": f"An inactive '{self._label_for(dup)}' already exists. Reactivate it instead of creating a duplicate.",
                "record": {"id": dup.pk, "label": self._label_for(dup)},
            },
            status=status.HTTP_409_CONFLICT,
        )

    # -- auto-generated Code (permanent system identifier) --------------------
    def _resolve_code(self, data, auto):
        """On create, finalise the Code: use the admin's one-time edited value if
        they supplied one, else derive it from the display name. Either way it's
        normalised to an UPPER_SNAKE identifier and format-checked. Uniqueness is
        enforced by the standard duplicate check; after creation the code is
        frozen (see update())."""
        provided = str(data.get(auto["field"]) or "").strip()
        source = provided or data.get(auto["source"], "")
        code = generate_code(source)
        if not code:
            raise ValidationError({auto["field"]: ["A code is required."]})
        if not _STRICT_CODE_RE.match(code):
            raise ValidationError({auto["field"]: [
                "Code must start with a letter and use only A–Z, 0–9 and underscore."
            ]})
        return code

    # -- create / update / delete ---------------------------------------------
    def create(self, request, *args, **kwargs):
        # Default is_active so callers can omit it (several master tables have a
        # NOT-NULL is_active with no DB default).
        data = {k: v for k, v in request.data.items()}
        if self._has_field("is_active"):
            data.setdefault("is_active", True)
        # Code is finalised here — an admin may edit the auto-generated value once,
        # during creation; otherwise it's derived from the name. Frozen thereafter.
        auto = rules_for(self._table).get("auto_code")
        if auto:
            data[auto["field"]] = self._resolve_code(data, auto)
        serializer = self.get_serializer(data=data)
        self._strip_unique_validators(serializer)
        serializer.is_valid(raise_exception=True)
        self._normalize_and_validate(serializer)
        conflict = self._duplicate_response_or_raise(serializer.validated_data)
        if conflict is not None:
            return conflict
        extra = {}
        if self._has_field("created_by"):
            extra["created_by"] = self._user()
        if self._has_field("created_on"):
            extra["created_on"] = timezone.now()
        serializer.save(**extra)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        self._check_lock(instance, request.data.get("expected_updated_on"))
        data = {k: v for k, v in request.data.items() if k != "expected_updated_on"}
        # The Code is frozen after creation — drop any attempt to change it so a
        # rename of the display name never touches the stable identifier.
        auto = rules_for(self._table).get("auto_code")
        if auto:
            data.pop(auto["field"], None)
        serializer = self.get_serializer(instance, data=data, partial=partial)
        self._strip_unique_validators(serializer)
        serializer.is_valid(raise_exception=True)
        self._normalize_and_validate(serializer)
        conflict = self._duplicate_response_or_raise(serializer.validated_data, exclude_pk=instance.pk)
        if conflict is not None:
            return conflict
        extra = {}
        if self._has_field("updated_by"):
            extra["updated_by"] = self._user()
        if self._has_field("updated_on"):
            extra["updated_on"] = timezone.now()
        serializer.save(**extra)
        return Response(serializer.data)

    def _check_lock(self, instance, expected):
        """Optimistic locking: the edit form sends the row's last-known token
        (updated_on, or created_on if never updated). Reject if it has changed."""
        if not expected:
            return
        current = getattr(instance, "updated_on", None) or getattr(instance, "created_on", None)
        if current is None:
            return
        sent = parse_datetime(str(expected))
        if sent is None:
            return
        # Compare to the second (TIMESTAMP(0) has no microseconds).
        if current.replace(microsecond=0) != sent.replace(microsecond=0):
            raise ValidationError(
                {"detail": "This record was changed by someone else. Reload and try again.", "code": "stale"}
            )

    def destroy(self, request, *args, **kwargs):
        """Soft delete — deactivate rather than hard-delete, preserving data
        integrity. Existing references keep working; the row is hidden from new
        dropdowns. (Use /references to see what points at it.)"""
        instance = self.get_object()
        if not self._has_field("is_active"):
            return super().destroy(request, *args, **kwargs)
        instance.is_active = False
        fields = ["is_active"]
        if self._has_field("updated_on"):
            instance.updated_on = timezone.now()
            fields.append("updated_on")
        if self._has_field("updated_by"):
            instance.updated_by = self._user()
            fields.append("updated_by")
        instance.save(update_fields=fields)
        return Response({"detail": "Record deactivated.", "is_active": False}, status=status.HTTP_200_OK)

    def _reference_details(self, instance):
        """Scan reverse FKs and return [{entity, count}] for tables that point
        at this row, aggregated by referencing table."""
        counts = {}
        for rel in instance._meta.related_objects:
            try:
                n = getattr(instance, rel.get_accessor_name()).count()
            except Exception:  # noqa: BLE001
                # Fail SAFE: an uncountable relation is treated as "referenced"
                # (never as zero), so a row we couldn't fully verify is never
                # eligible for permanent delete. Logged for diagnosis.
                logger.exception("reference count failed for %s via %s",
                                 self._table, rel.get_accessor_name())
                n = 1
            if n:
                table = rel.related_model._meta.db_table
                counts[table] = counts.get(table, 0) + n
        details = [
            {"entity": _REF_LABELS.get(t, t.replace("_", " ")), "count": c}
            for t, c in sorted(counts.items(), key=lambda kv: -kv[1])
        ]
        return details

    @action(detail=True, methods=["get"])
    def references(self, request, pk=None):
        """Report which tables reference this row — lets the UI tailor the
        delete dialog (deactivate-only vs. permanent-delete-allowed)."""
        details = self._reference_details(self.get_object())
        return Response({
            "referenced": bool(details),
            "total": sum(d["count"] for d in details),
            "details": details,
        })

    @action(detail=True, methods=["delete"], url_path="permanent")
    def permanent_delete(self, request, pk=None):
        """Hard delete — only for invalid/test or unreferenced rows. Blocked
        (409) when any table references the record, so referential integrity is
        never broken. Use plain DELETE for the normal soft delete instead."""
        instance = self.get_object()
        details = self._reference_details(instance)
        if details:
            summary = ", ".join(f"{d['count']} {d['entity']}" for d in details)
            return Response(
                {
                    "code": "referenced",
                    "detail": f"Can't permanently delete: referenced by {summary}. Deactivate it instead.",
                    "details": details,
                },
                status=status.HTTP_409_CONFLICT,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RoleMasterViewSet(MasterDataViewSet):
    queryset = RoleMaster.objects.all()
    serializer_class = RoleMasterSerializer
    search_fields = ["role_name", "role_code"]
    ordering_fields = ["role_id", "role_name"]

class UserMasterViewSet(MasterDataViewSet):
    # The user directory is staff PII (email, mobile, username, role) — NOT
    # dropdown/reference data. Override the inherited read-open policy so ONLY
    # Admins can list/retrieve users; recruiters/HMs never enumerate staff. The
    # only non-admin user-picking flow (recruiter assignment) is itself
    # Admin-only, so nothing legitimate depends on non-admin read access.
    permission_classes = [IsAdministrator]
    queryset = UserMaster.objects.all().order_by("user_id")
    serializer_class = UserMasterSerializer

    search_fields = ["full_name","username","email",]

    ordering_fields = ["user_id","full_name",]

    def get_serializer_class(self):
        # Reads hide the password hash; writes accept + hash a password.
        if self.action in ("create", "update", "partial_update"):
            return UserWriteSerializer
        return UserMasterSerializer

class DomainMasterViewSet(MasterDataViewSet):
    """Skill classification data. Admin-only writes (create/edit/deactivate);
    any authenticated user may read so the Skill form can offer the dropdown.
    Hiring Managers therefore can SELECT a domain but never create/edit/delete
    one. Permanent delete is blocked while any Skill references the domain (the
    base class's /references check sees skill_master via the reverse FK), so a
    domain in use can only be deactivated."""
    queryset = DomainMaster.objects.all().order_by("domain_name")
    serializer_class = DomainMasterSerializer
    search_fields = ["domain_name"]
    ordering_fields = ["domain_id", "domain_name"]
    # Default IsAdminOrReadOnly: read = any auth, write = Admin only.


class CandidateStatusMasterViewSet(MasterDataViewSet):
    """Global candidate disposition. Admin-only writes; any auth reads."""
    queryset = CandidateStatusMaster.objects.all().order_by("candidate_status_id")
    serializer_class = CandidateStatusMasterSerializer
    search_fields = ["status_name", "status_code"]
    ordering_fields = ["candidate_status_id", "status_name"]


class ApplicationStatusMasterViewSet(MasterDataViewSet):
    """Per-(candidate, requirement) pipeline stage. Admin-only writes."""
    queryset = ApplicationStatusMaster.objects.all().order_by("application_status_id")
    serializer_class = ApplicationStatusMasterSerializer
    search_fields = ["status_name", "status_code"]
    ordering_fields = ["application_status_id", "status_name"]


class PositionStatusMasterViewSet(MasterDataViewSet):
    """Per-seat lifecycle status. Admin-only writes."""
    queryset = PositionStatusMaster.objects.all().order_by("position_status_id")
    serializer_class = PositionStatusMasterSerializer
    search_fields = ["status_name", "status_code"]
    ordering_fields = ["position_status_id", "status_name"]


class SkillMasterViewSet(MasterDataViewSet):
    queryset = SkillMaster.objects.select_related("domain").all()
    serializer_class = SkillMasterSerializer
    search_fields = ["skill_name", "domain__domain_name"]
    ordering_fields = ["skill_id", "skill_name"]
    # HM can create (inline, from the Requirement form); edit/delete stay Admin-only.
    permission_classes = [CanManageReferenceData]

class ClientMasterViewSet(MasterDataViewSet):
    queryset = ClientMaster.objects.all()
    serializer_class = ClientMasterSerializer
    search_fields = ["client_name", "client_code"]
    ordering_fields = ["client_name"]


class ClientManagerMasterViewSet(MasterDataViewSet):
    queryset = ClientManagerMaster.objects.all()
    serializer_class = ClientManagerMasterSerializer
    search_fields = ["manager_name", "email"]
    ordering_fields = ["manager_name"]


class ReqStatusMasterViewSet(MasterDataViewSet):
    queryset = ReqStatusMaster.objects.all()
    serializer_class = ReqStatusMasterSerializer
    search_fields = ["status_name"]


class PriorityMasterViewSet(MasterDataViewSet):
    queryset = PriorityMaster.objects.all()
    serializer_class = PriorityMasterSerializer
    search_fields = ["priority_name"]


class NoticePeriodMasterViewSet(MasterDataViewSet):
    queryset = NoticePeriodMaster.objects.all()
    serializer_class = NoticePeriodMasterSerializer
    search_fields = ["np_name"]


class ReqTypeMasterViewSet(MasterDataViewSet):
    queryset = ReqTypeMaster.objects.all()
    serializer_class = ReqTypeMasterSerializer
    search_fields = ["req_type_name"]


class WorkModeMasterViewSet(MasterDataViewSet):
    queryset = WorkModeMaster.objects.all()
    serializer_class = WorkModeMasterSerializer
    search_fields = ["work_mode_name"]


class SourceMasterViewSet(MasterDataViewSet):
    queryset = SourceMaster.objects.all()
    serializer_class = SourceMasterSerializer
    search_fields = ["source_name"]


class ScreeningModeMasterViewSet(MasterDataViewSet):
    queryset = ScreeningModeMaster.objects.all()
    serializer_class = ScreeningModeMasterSerializer
    search_fields = ["mode_name", "mode_code"]


class RejectionReasonMasterViewSet(MasterDataViewSet):
    queryset = RejectionReasonMaster.objects.all()
    serializer_class = RejectionReasonMasterSerializer
    search_fields = ["reason_name", "reason_code"]


class EmailTemplateMasterViewSet(MasterDataViewSet):
    queryset = EmailTemplateMaster.objects.all()
    serializer_class = EmailTemplateMasterSerializer
    search_fields = ["name", "template_code"]


class LocationMasterViewSet(MasterDataViewSet):
    queryset = LocationMaster.objects.all()
    serializer_class = LocationMasterSerializer
    search_fields = ["city", "state", "country"]
    # HM can create (inline, from the Requirement form); edit/delete stay Admin-only.
    permission_classes = [CanManageReferenceData]


class DashboardAPIView(APIView):
    """Role-aware dashboard summary (KPIs, status breakdowns, recent items)."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(build_dashboard(request.user))
    
class ProfileView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(
            {
                "user_id": request.user.user_id,
                "full_name": request.user.full_name,
                "username": request.user.username,
                "email": request.user.email,
                "role": request.user.role.role_name,
            }
        )
