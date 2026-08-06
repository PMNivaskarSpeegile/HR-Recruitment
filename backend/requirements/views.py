"""
Requirement API (UC1).

GET  /api/requirements/        list (any authenticated user)
POST /api/requirements/        create (Hiring Manager or Admin) -> auto numbers
GET  /api/requirements/{id}/   retrieve
PUT/PATCH /api/requirements/{id}/  update (HM/Admin)
"""
from django.db.models import Count, Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from admin_module.models import (
    RequirementPosition,
    RequirementTracker,
    StatusChangeHistory,
    UserMaster,
)
from authentication.permissions import (
    IsAdministrator,
    IsHiringManager,
    IsHiringManagerOrAdmin,
)
from core.constants import AuditEntity, ReqStatus, Roles
from core.mixins import AuditModelMixin

from .positions import PositionError, add_positions, change_position_status, delete_position
from .serializers import (
    RequirementPositionSerializer,
    RequirementReadSerializer,
    RequirementWriteSerializer,
    StatusChangeHistorySerializer,
)
from .services import (
    RequirementStatusError,
    assign_requirement,
    change_requirement_status,
    create_requirement,
    end_recruitment,
    requirement_is_expired,
)

# Requirement states to which the HM may still add positions (Rule 2).
_ADDABLE_STATES = (ReqStatus.NEW, ReqStatus.ASSIGNED, ReqStatus.OPEN, ReqStatus.PARTIAL_FILLED)


class RequirementViewSet(AuditModelMixin, viewsets.ModelViewSet):
    queryset = (
        RequirementTracker.objects
        .select_related(
            "client", "client_mgr", "req_type", "req_status", "priority",
            "location", "recruiter", "hiring_mgr", "np",
            "skill1", "skill2", "skill3",
        )
        .prefetch_related("requirementposition_set__position_status")
        # Active (open, not-closed) applications — powers the End-Recruitment
        # confirmation summary and reporting. Filtered Count → no row multiplication.
        .annotate(active_application_count=Count(
            "jdcvmapping",
            filter=Q(jdcvmapping__is_active=True, jdcvmapping__is_closed=False),
        ))
        .order_by("-req_id")
    )

    filterset_fields = ["req_status", "priority", "client", "recruiter", "hiring_mgr", "req_type"]
    # Free-text search covers the identifiers, the role title AND the client name
    # (so the searchable requirement pickers can find "REQ-2026-014", "Backend
    # Engineer" or "Acme" alike).
    search_fields = ["req_tracker_no", "jd_serial_number", "jd_role_name", "client_req_id",
                     "client__client_name"]
    ordering_fields = ["req_id", "req_date", "target_fill_date"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return RequirementWriteSerializer
        return RequirementReadSerializer

    def get_queryset(self):
        """Role-based data visibility. Admins see everything; recruiters see only
        requirements assigned to them; hiring managers see only the ones they own.
        Enforced here (not the UI) so it also covers retrieve, the `positions`
        action, assign and updates via get_object() — a recruiter hitting another
        recruiter's requirement by id gets 404, not their data. Search, filters,
        ordering and pagination all apply on top of this scoped base queryset."""
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):  # schema generation
            return qs
        user = self.request.user
        role = getattr(getattr(user, "role", None), "role_code", None)
        if role == Roles.ADMIN:
            pass
        elif role == Roles.RECRUITER:
            qs = qs.filter(recruiter_id=getattr(user, "user_id", None))
        elif role == Roles.HIRING_MANAGER:
            qs = qs.filter(hiring_mgr_id=getattr(user, "user_id", None))
        else:
            return qs.none()  # unknown role → see nothing (safe default)

        # Dashboard / deep-link filters applied SERVER-SIDE so they page correctly
        # and the row count matches the dashboard KPI (not just the newest page).
        params = self.request.query_params
        status_param = params.get("status")
        if status_param == "active":
            qs = qs.exclude(req_status__status_code__in=ReqStatus.TERMINAL)
        elif status_param:
            qs = qs.filter(req_status__status_code=status_param)
        missing = params.get("missing")
        if missing == "recruiter":
            qs = qs.filter(recruiter__isnull=True)
        elif missing == "hm":
            qs = qs.filter(hiring_mgr__isnull=True)
        return qs

    def get_permissions(self):
        # RBAC permission matrix (also enforced in the UI):
        #   Assign/reassign recruiter        → Admin only
        #   Edit + lifecycle (Hold/Resume/    → Hiring Manager only (Admins excluded)
        #     Cancel/Reopen via set-status)
        #   Create / delete / position seats  → Hiring Manager or Admin (unchanged)
        #   Read                              → any authenticated user
        if self.action == "assign":
            return [IsAdministrator()]
        # Requirement lifecycle (Hold/Resume/Cancel/Close-Lost) AND manual position
        # status → Hiring Manager only. Admins have full access EXCEPT holding /
        # cancelling a requirement or a position (that is the HM's decision).
        if self.action in ("update", "partial_update", "set_status", "set_position_status",
                           "end_recruitment"):
            return [IsHiringManager()]
        # Create, delete, and adding/removing seats → Hiring Manager or Admin.
        if self.action in ("create", "destroy", "add_positions", "delete_position"):
            return [IsHiringManagerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def update(self, request, *args, **kwargs):
        """Editing a requirement. While the Expired overlay is showing, the
        requirement is read-only EXCEPT for the Target Fill Date (extending it
        clears the overlay)."""
        instance = self.get_object()
        if instance.recruitment_ended:
            raise ValidationError({"detail": [
                "Recruitment has permanently ended for this requirement; it is read-only "
                "(the decision cannot be reversed)."
            ]})
        if requirement_is_expired(instance):
            extra = set(request.data.keys()) - {"target_fill_date"}
            if extra:
                raise ValidationError({"detail": [
                    "This requirement has expired and is read-only. Only the Target "
                    "Fill Date can be changed (extend it to resume normal operations)."
                ]})
        return super().update(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        write = self.get_serializer(data=request.data)
        write.is_valid(raise_exception=True)
        requirement = create_requirement(validated_data=write.validated_data, user=request.user)
        read = RequirementReadSerializer(requirement, context=self.get_serializer_context())
        return Response(read.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def assign(self, request, pk=None):
        """POST /api/requirements/{id}/assign/  body: {"recruiter": <user_id>}
        Assign or reassign a recruiter — **Admin only** (RBAC). HM/Recruiter → 403."""
        requirement = self.get_object()

        recruiter_id = request.data.get("recruiter")
        if not recruiter_id:
            raise ValidationError({"recruiter": ["This field is required."]})

        try:
            recruiter = UserMaster.objects.select_related("role").get(
                user_id=recruiter_id, is_active=True
            )
        except UserMaster.DoesNotExist:
            raise ValidationError({"recruiter": ["No active user found with this id."]})

        if recruiter.role.role_code != Roles.RECRUITER:
            raise ValidationError({"recruiter": ["The selected user is not a Recruiter."]})

        assign_requirement(requirement=requirement, recruiter=recruiter, user=request.user)
        read = RequirementReadSerializer(requirement, context=self.get_serializer_context())
        return Response(read.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="set-status",
            permission_classes=[IsHiringManager])
    def set_status(self, request, pk=None):
        """Manual requirement status change — **Hiring Manager only**. Body:
        {"to_status": "HOLD|OPEN|CANCELLED|CLOSE_LOST", "reason": "…"}. Hold →
        Open seats become Inactive; Resume/Reopen restores auto-inactivated seats;
        Cancelled/Closed Lost require a reason and are explicit closures (Cancelled
        can be reopened, Closed Lost is terminal). Admins & Recruiters get 403."""
        requirement = self.get_object()
        if requirement.recruitment_ended:
            raise ValidationError({"detail": [
                "Recruitment has permanently ended for this requirement; its status can no longer be changed."
            ]})
        if requirement_is_expired(requirement):
            raise ValidationError({"detail": [
                "This requirement has expired. Extend the Target Fill Date before changing status."
            ]})
        to_status = request.data.get("to_status")
        if not to_status:
            raise ValidationError({"to_status": ["This field is required."]})
        try:
            change_requirement_status(
                requirement=requirement, to_status=to_status,
                user=request.user, reason=request.data.get("reason"),
            )
        except RequirementStatusError as exc:
            raise ValidationError({"to_status": [str(exc)]})
        requirement.refresh_from_db()
        read = RequirementReadSerializer(requirement, context=self.get_serializer_context())
        return Response(read.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="end-recruitment",
            permission_classes=[IsHiringManager])
    def end_recruitment(self, request, pk=None):
        """POST /api/requirements/{id}/end-recruitment/ — **Hiring Manager only**.
        Permanently stop recruiting the remaining positions of an EXPIRED,
        partially-filled requirement. Closes every still-active application as
        'Positions Withdrawn' and returns those candidates to the Talent Pool. The
        requirement is left in PARTIAL_FILLED + Expired (no new status); the filled
        seats and full history are preserved. Admins & Recruiters get 403."""
        requirement = self.get_object()
        try:
            result = end_recruitment(
                requirement=requirement, user=request.user, reason=request.data.get("reason"),
            )
        except RequirementStatusError as exc:
            raise ValidationError({"detail": [str(exc)]})
        requirement.refresh_from_db()
        read = RequirementReadSerializer(requirement, context=self.get_serializer_context())
        data = read.data
        data["applications_closed"] = result["closed"]
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def positions(self, request, pk=None):
        """GET /api/requirements/{id}/positions/ — the requirement's seats (any
        authenticated user). Positions are tracked independently of candidates."""
        requirement = self.get_object()
        seats = (
            RequirementPosition.objects
            .filter(req=requirement)
            .select_related("position_status", "filled_by_mapping__candidate")
            .order_by("position_no")
        )
        return Response(RequirementPositionSerializer(seats, many=True).data)

    @action(detail=True, methods=["post"], url_path="set-position-status",
            permission_classes=[IsHiringManager])
    def set_position_status(self, request, pk=None):
        """POST /api/requirements/{id}/set-position-status/  body:
        {"position_id": <id>, "to_status": "OPEN|HOLD|CANCELLED"}
        Manual seat management — **Hiring Manager only** (Admins & Recruiters are
        read-only → 403). Allowed: Open↔Hold, Open/Hold→Cancelled, Cancelled→Open.
        A manual Filled is rejected (seats fill only on Join); Filled is terminal.
        Independent of the requirement's own manual status."""
        requirement = self.get_object()
        if requirement.recruitment_ended:
            raise ValidationError({"detail": ["Recruitment has ended for this requirement; seats are read-only."]})
        if requirement_is_expired(requirement):
            raise ValidationError({"detail": ["This requirement has expired; positions are read-only."]})
        position_id = request.data.get("position_id")
        to_status = request.data.get("to_status")
        if not position_id or not to_status:
            raise ValidationError({"detail": ["position_id and to_status are required."]})
        try:
            position = RequirementPosition.objects.get(position_id=position_id, req=requirement)
        except RequirementPosition.DoesNotExist:
            raise ValidationError({"position_id": ["No such position for this requirement."]})
        try:
            change_position_status(
                position=position, to_status_code=to_status,
                user=request.user, reason=request.data.get("reason"),
            )
        except PositionError as exc:
            raise ValidationError({"to_status": [str(exc)]})
        requirement.refresh_from_db()
        read = RequirementReadSerializer(requirement, context=self.get_serializer_context())
        return Response(read.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="add-positions",
            permission_classes=[IsHiringManagerOrAdmin])
    def add_positions(self, request, pk=None):
        """POST /api/requirements/{id}/add-positions/  body: {"count": N}
        Hiring Manager / Admin add seats to an ACTIVE requirement. New seats are
        Open; the rollup reflects the added demand (a Filled requirement becomes
        Partially Filled). Blocked when the requirement is closed/expired."""
        requirement = self.get_object()
        if requirement.recruitment_ended:
            raise ValidationError({"detail": ["Recruitment has ended for this requirement; new positions cannot be added."]})
        if requirement_is_expired(requirement):
            raise ValidationError({"detail": ["This requirement has expired; extend the Target Fill Date first."]})
        code = requirement.req_status.status_code if requirement.req_status_id else None
        if code not in _ADDABLE_STATES:
            raise ValidationError({"detail": [
                f"Positions can only be added while the requirement is active — not '{code}'."
            ]})
        try:
            count = int(request.data.get("count", 1))
        except (TypeError, ValueError):
            raise ValidationError({"count": ["Must be a whole number."]})
        if count < 1:
            raise ValidationError({"count": ["Add at least one position."]})
        add_positions(requirement=requirement, count=count, user=request.user)
        requirement.refresh_from_db()
        return Response(RequirementReadSerializer(requirement, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="delete-position",
            permission_classes=[IsHiringManagerOrAdmin])
    def delete_position(self, request, pk=None):
        """POST /api/requirements/{id}/delete-position/  body: {"position_id": N}
        Remove a seat — only if it was never Filled and has no recruitment activity
        (else Cancel it instead)."""
        requirement = self.get_object()
        if requirement_is_expired(requirement):
            raise ValidationError({"detail": ["This requirement has expired; positions are read-only."]})
        position_id = request.data.get("position_id")
        if not position_id:
            raise ValidationError({"position_id": ["This field is required."]})
        try:
            position = RequirementPosition.objects.get(position_id=position_id, req=requirement)
        except RequirementPosition.DoesNotExist:
            raise ValidationError({"position_id": ["No such position for this requirement."]})
        try:
            delete_position(position=position, user=request.user)
        except PositionError as exc:
            raise ValidationError({"detail": [str(exc)]})
        requirement.refresh_from_db()
        return Response(RequirementReadSerializer(requirement, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get"], url_path="status-history")
    def status_history(self, request, pk=None):
        """GET /api/requirements/{id}/status-history/ — combined audit timeline of
        this requirement and its positions (newest first)."""
        requirement = self.get_object()
        pos_ids = list(
            RequirementPosition.objects.filter(req=requirement).values_list("position_id", flat=True)
        )
        rows = (
            StatusChangeHistory.objects
            .filter(
                Q(entity_type=AuditEntity.REQUIREMENT, entity_id=requirement.req_id)
                | Q(entity_type=AuditEntity.POSITION, entity_id__in=pos_ids)
            )
            .select_related("changed_by")
            .order_by("-changed_on", "-history_id")
        )
        return Response(StatusChangeHistorySerializer(rows, many=True).data)
