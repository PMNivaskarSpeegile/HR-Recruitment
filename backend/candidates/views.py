"""
Candidate API (UC2).

GET  /api/candidates/                  list + search/filter (§9)
POST /api/candidates/                  manual create (duplicate logic)
GET  /api/candidates/{id}/             retrieve
PUT/PATCH /api/candidates/{id}/        update
GET  /api/candidates/upload-template/  download the Excel import template
POST /api/candidates/bulk-upload/      bulk import from Excel
"""
import logging
import os

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from admin_module.models import (
    CandidateDuplicateReview,
    CandidateInteraction,
    CandidateMaster,
    CandidateStatusMaster,
    CommunicationLog,
    BulkImportBatch,
    CvDocument,
    JdCvMapping,
    LocationMaster,
    RequirementTracker,
    SourceMaster,
)
from authentication.permissions import IsAdministrator, IsRecruiterOrAdmin
from core.constants import CandidateStatus, DuplicateReview, InteractionType, Roles
from core.mixins import AuditModelMixin

from .serializers import (
    BulkImportBatchDetailSerializer,
    BulkImportBatchListSerializer,
    CandidateProfileUpdateSerializer,
    CandidateReadSerializer,
    VerifyDecisionSerializer,
    CandidateStatusChangeSerializer,
    CandidateStatusClearSerializer,
    CandidateWriteSerializer,
    DuplicateReviewCreateSerializer,
    DuplicateReviewResolveSerializer,
    DuplicateReviewSerializer,
)
from .services import (
    CREATED,
    POSSIBLE_DUPLICATE,
    UPDATED,
    BULK_TEMPLATE_HEADERS,
    BULK_TEMPLATE_EXAMPLE,
    confirm_import_batch,
    import_candidates_excel,
    preview_candidates_excel,
    reconcile_location as reconcile_location_service,
    rollback_import_batch,
    unmapped_location_summary,
    upsert_candidate,
)

logger = logging.getLogger("ats")


def _authorize_review_pool(user, requirement):
    """§9 — only the requirement's ASSIGNED recruiter (or an admin) may add/remove
    candidates from that requirement's Review Pool. Raises PermissionDenied."""
    role = getattr(getattr(user, "role", None), "role_code", None)
    if role == Roles.ADMIN:
        return
    if role == Roles.RECRUITER and requirement.recruiter_id == getattr(user, "user_id", None):
        return
    raise PermissionDenied(
        "Only the requirement's assigned recruiter (or an admin) may manage its review pool."
    )


class CandidateViewSet(AuditModelMixin, viewsets.ModelViewSet):
    queryset = (
        CandidateMaster.objects
        .select_related("candidate_status", "current_location", "notice_period",
                        "work_mode", "source", "uploaded_by")
        .prefetch_related("candidateskill_set__skill")
        .order_by("-cv_id")
    )

    # Global candidate search (§9). candidate_status is handled in get_queryset
    # (role visibility + default hidden set + ?status=<code>/ALL), not the filterset.
    filterset_fields = ["source", "notice_period", "work_mode",
                        "current_location", "uploaded_by", "is_willing_to_relocate"]
    # Free-text search: name/contact/company plus the (to-one) current location's
    # city & state, so "Mumbai" or "Maharashtra" match server-side too. Skills are
    # searched via the dedicated ?skill=<id> filter (a text join here would
    # multiply rows).
    search_fields = ["candidate_name", "mobile", "email", "current_company",
                     "current_location__city", "current_location__state"]
    ordering_fields = ["cv_id", "candidate_name", "created_on", "exp_max"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CandidateWriteSerializer
        return CandidateReadSerializer

    def get_permissions(self):
        # Removing a Fake/Blacklisted mark is ADMIN-only.
        if self.action == "clear_status":
            return [IsAdministrator()]
        if self.action in ("create", "update", "partial_update", "destroy",
                           "bulk_upload", "bulk_preview", "set_status", "verify_profile",
                           "unmapped_locations", "reconcile_location",
                           "tag_requirements", "untag_requirement"):
            return [IsRecruiterOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):  # schema generation
            return qs
        # ?skill=<id> (repeatable) — candidates tagged with the given skill(s), §9.
        # Multiple skills are AND-ed (a separate .filter() per skill → the
        # candidate must have EVERY selected skill), matching a "must-have skills"
        # sourcing filter. distinct() dedupes the joins.
        skill_ids = [s for s in self.request.query_params.getlist("skill") if s.isdigit()]
        for sid in skill_ids:
            qs = qs.filter(candidateskill__skill_id=sid)
        if skill_ids:
            qs = qs.distinct()

        # --- Candidate Database visibility (backend-enforced, not UI-only) ----
        role = getattr(getattr(self.request.user, "role", None), "role_code", None)
        uid = getattr(self.request.user, "user_id", None)

        # Hiring Managers get a READ-ONLY sourcing view (write actions are already
        # blocked in get_permissions). Their BASE visibility (every action, list AND
        # detail, so a mapped candidate's drawer stays reachable by id) is: New_CV +
        # Talent Pool candidates, PLUS any candidate mapped to a requirement THEY
        # own. They never see candidates that belong only to other owners' reqs.
        if role == Roles.HIRING_MANAGER:
            hm_mapped_ids = JdCvMapping.objects.filter(
                req__hiring_mgr_id=uid
            ).values_list("candidate_id", flat=True)
            qs = qs.filter(
                Q(candidate_status__status_code__in=CandidateStatus.HM_VISIBLE)
                | Q(cv_id__in=list(hm_mapped_ids))
            )

        # The default-hidden view is a LIST convenience for REC/ADM; a specific
        # candidate stays reachable by id for detail actions (retrieve/set-status/
        # detail/resume) — otherwise you couldn't act on a Fake/Held candidate.
        if self.action != "list":
            return qs

        # List views show only ACTIVE candidates (a rolled-back bulk import soft-
        # deletes its rows → is_active=False → they drop out of the database view;
        # they stay reachable by id for detail actions).
        qs = qs.filter(is_active=True)

        status_param = self.request.query_params.get("status")

        # --- Requirement filter (?requirement=<id>) — ALL roles -----------------
        # Selecting a requirement shows ONLY candidates mapped to it (deterministic:
        # never auto-includes untagged New_CV / Talent Pool). The requirement must
        # be one the user can access (Admin: any; Recruiter: assigned; HM: owned);
        # an inaccessible id yields no rows (no data leak). A status filter still
        # composes on top; otherwise mapped candidates of ANY status are shown
        # (they're already associated with the requirement).
        req_param = self.request.query_params.get("requirement")
        if req_param and req_param.isdigit():
            if not self._requirement_accessible(int(req_param), role, uid):
                return qs.none()
            mapped_ids = JdCvMapping.objects.filter(req_id=int(req_param)).values_list("candidate_id", flat=True)
            qs = qs.filter(cv_id__in=list(mapped_ids))
            if status_param and status_param != "ALL" and not (
                role == Roles.HIRING_MANAGER and status_param not in CandidateStatus.HM_VISIBLE
            ):
                qs = qs.filter(candidate_status__status_code=status_param)
            return qs

        # --- No requirement selected: role default views ------------------------
        if role == Roles.HIRING_MANAGER:
            # HM only narrows within their visible set (New_CV / Talent Pool).
            if status_param and status_param != "ALL" and status_param in CandidateStatus.HM_VISIBLE:
                qs = qs.filter(candidate_status__status_code=status_param)
            return qs
        if status_param == "ALL":
            return qs
        if status_param:
            return qs.filter(candidate_status__status_code=status_param)
        return qs.exclude(candidate_status__status_code__in=CandidateStatus.DB_DEFAULT_HIDDEN)

    def _requirement_accessible(self, req_id, role, uid):
        """Whether the current user may filter candidates by this requirement:
        Admin → any; Recruiter → assigned to them; HM → owned by them."""
        req = (
            RequirementTracker.objects
            .filter(req_id=req_id)
            .values("recruiter_id", "hiring_mgr_id")
            .first()
        )
        if req is None:
            return False
        if role == Roles.ADMIN:
            return True
        if role == Roles.RECRUITER:
            return req["recruiter_id"] == uid
        if role == Roles.HIRING_MANAGER:
            return req["hiring_mgr_id"] == uid
        return False

    # ---- manual single create with duplicate handling -------------------
    def create(self, request, *args, **kwargs):
        write = self.get_serializer(data=request.data)
        write.is_valid(raise_exception=True)
        data = dict(write.validated_data)
        requirement = data.pop("requirement", None)
        if requirement is not None:
            # Selecting a requirement creates a Review-Pool tag (not skill copy).
            _authorize_review_pool(request.user, requirement)
            from .services import _requirement_open_for_review
            if not _requirement_open_for_review(requirement):
                raise ValidationError({"requirement": ["This requirement is not open for new candidates."]})
        skills = data.pop("skill_ids", None)
        extra_skill_ids = [s.skill_id for s in skills] if skills else None

        result = upsert_candidate(
            data=data, user=request.user,
            requirement=requirement, extra_skill_ids=extra_skill_ids,
        )
        candidate = result["candidate"]
        read = CandidateReadSerializer(candidate, context=self.get_serializer_context())

        if result["action"] == POSSIBLE_DUPLICATE:
            return Response(
                {
                    "action": POSSIBLE_DUPLICATE,
                    "message": (
                        "A candidate with this mobile already exists with a different "
                        "email. Review the two records and, if this looks like a "
                        "duplicate, submit it for Admin review."
                    ),
                    "reason": "Same mobile number, different email address.",
                    "existing_candidate": read.data,
                    "submitted": {
                        "candidate_name": request.data.get("candidate_name"),
                        "mobile": request.data.get("mobile"),
                        "email": request.data.get("email"),
                        "current_company": request.data.get("current_company"),
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )

        http_status = status.HTTP_201_CREATED if result["action"] == CREATED else status.HTTP_200_OK
        return Response({"action": result["action"], "candidate": read.data}, status=http_status)

    # ---- mark Fake / Blacklisted (recruiter/admin) ----------------------
    @extend_schema(request=CandidateStatusChangeSerializer, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["post"], url_path="set-status",
            permission_classes=[IsRecruiterOrAdmin])
    def set_status(self, request, pk=None):
        """Mark a candidate **Fake** or **Blacklisted** — the only hand-settable
        statuses (a mandatory reason is recorded for audit). The two are MUTUALLY
        EXCLUSIVE: you can't mark one while the other is set — an Admin must remove
        the existing mark first. All recruitment history is preserved."""
        candidate = self.get_object()
        serializer = CandidateStatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["status_code"]
        reason = serializer.validated_data["reason"].strip()

        exclusive = {CandidateStatus.FAKE, CandidateStatus.BLACKLISTED}
        current = candidate.candidate_status.status_code if candidate.candidate_status_id else None
        if code in exclusive and current in exclusive and current != code:
            current_label = candidate.candidate_status.status_name
            new_label = CandidateStatusMaster.objects.get(status_code=code).status_name
            raise ValidationError({"status_code": [
                f"This candidate is already marked {current_label}. "
                f"{current_label} and {new_label} are mutually exclusive — an admin "
                f"must remove {current_label} before marking as {new_label}."
            ]})

        new_status = CandidateStatusMaster.objects.get(status_code=code)
        now = timezone.now()
        candidate.candidate_status = new_status
        candidate.last_status_changed_on = now
        candidate.updated_by = request.user
        candidate.updated_on = now
        candidate.save(update_fields=["candidate_status", "last_status_changed_on", "updated_by", "updated_on"])

        CandidateInteraction.objects.create(
            candidate=candidate,
            interaction_type=InteractionType.STATUS_CHANGE,
            comment=f"Marked {new_status.status_name}. Reason: {reason}",
            created_by=request.user,
            created_on=now,
        )
        read = CandidateReadSerializer(candidate, context=self.get_serializer_context())
        return Response({"candidate": read.data}, status=status.HTTP_200_OK)

    # ---- remove a Fake / Blacklisted mark (ADMIN only) -------------------
    @extend_schema(request=CandidateStatusClearSerializer, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["post"], url_path="clear-status",
            permission_classes=[IsAdministrator])
    def clear_status(self, request, pk=None):
        """Admin-only: remove a Fake / Blacklisted mark and restore the candidate
        to the Talent Pool so they can re-enter the normal workflow. Recorded on
        the timeline (history preserved). Rejected for any other status."""
        candidate = self.get_object()
        current = candidate.candidate_status.status_code if candidate.candidate_status_id else None
        if current not in (CandidateStatus.FAKE, CandidateStatus.BLACKLISTED):
            raise ValidationError({"detail": ["Only a Fake or Blacklisted candidate can have their status removed."]})
        serializer = CandidateStatusClearSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = (serializer.validated_data.get("reason") or "").strip()

        cleared_label = candidate.candidate_status.status_name
        now = timezone.now()
        candidate.candidate_status = CandidateStatusMaster.objects.get(status_code=CandidateStatus.SAVED)
        candidate.last_status_changed_on = now
        candidate.updated_by = request.user
        candidate.updated_on = now
        candidate.save(update_fields=["candidate_status", "last_status_changed_on", "updated_by", "updated_on"])

        note = f"Removed {cleared_label} mark — restored to Talent Pool."
        if reason:
            note = f"{note} Reason: {reason}"
        CandidateInteraction.objects.create(
            candidate=candidate, interaction_type=InteractionType.STATUS_CHANGE,
            comment=note, created_by=request.user, created_on=now,
        )
        read = CandidateReadSerializer(candidate, context=self.get_serializer_context())
        return Response({"candidate": read.data}, status=status.HTTP_200_OK)

    # ---- Verify & Update the master profile (recruiter/admin) ------------
    @extend_schema(request=CandidateProfileUpdateSerializer, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["post"], url_path="verify-profile",
            permission_classes=[IsRecruiterOrAdmin])
    def verify_profile(self, request, pk=None):
        """Verify & update the SINGLE master candidate profile (visible across all
        requirements) — full field-level audit + timeline + verification stamp.
        A mobile/email change re-runs duplicate detection; a collision with another
        candidate opens a duplicate review and is NOT saved (409). HM is read-only."""
        candidate = self.get_object()
        serializer = CandidateProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # The optional one recruiter DECISION (Shortlist / Not Suitable / Fake /
        # Blacklist / Save) made alongside the profile update — replaces Review.
        decision_ser = VerifyDecisionSerializer(data=request.data)
        decision_ser.is_valid(raise_exception=True)
        from .services import (
            DecisionError, DuplicateConflict, apply_candidate_decision,
            record_possible_duplicate, verify_and_update_candidate,
        )
        try:
            result = verify_and_update_candidate(
                candidate=candidate, validated_data=serializer.validated_data, user=request.user,
            )
        except DuplicateConflict as exc:
            # Persist the possible-duplicate review OUTSIDE the service's rolled-back
            # transaction (existing duplicate-review workflow).
            record_possible_duplicate(
                existing_candidate=exc.existing,
                new_candidate_name=exc.new_candidate_name,
                new_mobile=exc.new_mobile, new_email=exc.new_email,
                detection_reason=(f"Profile edit of {exc.editing.cv_serial} — new mobile/email "
                                  f"matches {exc.existing.cv_serial}"),
                submitted_payload={"source": "profile_update", "editing_cv": exc.editing.cv_id,
                                   "candidate_name": exc.new_candidate_name,
                                   "mobile": exc.new_mobile, "email": exc.new_email},
                user=request.user,
            )
            existing = CandidateReadSerializer(exc.existing, context=self.get_serializer_context())
            return Response(
                {
                    "action": POSSIBLE_DUPLICATE,
                    "message": (
                        "The mobile/email you entered belongs to another candidate. A "
                        "duplicate review was created for an admin to resolve — your change "
                        "was NOT saved."
                    ),
                    "existing_candidate": existing.data,
                },
                status=status.HTTP_409_CONFLICT,
            )
        # Apply the recruiter's decision (if any) on the just-verified profile.
        decision = decision_ser.validated_data.get("decision")
        decision_result = None
        if decision:
            try:
                outcome = apply_candidate_decision(
                    candidate=result["candidate"], decision=decision, user=request.user,
                    requirement=decision_ser.validated_data.get("requirement"),
                    reason=decision_ser.validated_data.get("decision_reason"),
                    move_to_talent_pool=decision_ser.validated_data.get("move_to_talent_pool", False),
                )
            except DecisionError as exc:
                raise ValidationError({"decision": [str(exc)]})
            candidate.refresh_from_db()
            mapping = outcome.get("mapping")
            decision_result = {
                "decision": decision,
                "mapping_id": mapping.mapping_id if mapping else None,
                "application_stage": (mapping.application_stage.status_code
                                      if mapping and mapping.application_stage_id else None),
                "latest_outcome": (mapping.latest_outcome.status_code
                                   if mapping and mapping.latest_outcome_id else None),
                "is_closed": mapping.is_closed if mapping else None,
            }

        read = CandidateReadSerializer(result["candidate"], context=self.get_serializer_context())
        return Response(
            {"candidate": read.data, "changed_fields": result["changed_fields"],
             "verified": result["verified"], "decision": decision_result},
            status=status.HTTP_200_OK,
        )

    # ---- Excel template download ----------------------------------------
    @action(detail=False, methods=["get"], url_path="upload-template",
            permission_classes=[permissions.IsAuthenticated])
    def upload_template(self, request):
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Candidate Details"
        ws.append(BULK_TEMPLATE_HEADERS)
        ws.append(BULK_TEMPLATE_EXAMPLE)  # one example row to guide the recruiter

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="candidate_bulk_upload_template.xlsx"'
        wb.save(response)
        return response

    # ---- Excel bulk upload ----------------------------------------------
    def _bulk_file(self, request):
        """Validate the uploaded file; returns (file, error_response)."""
        upload = request.FILES.get("file")
        if not upload:
            return None, Response({"file": ["No file uploaded. Send a .xlsx in 'file'."]},
                                  status=status.HTTP_400_BAD_REQUEST)
        if not upload.name.lower().endswith(".xlsx"):
            return None, Response({"file": ["Only .xlsx files are supported."]},
                                  status=status.HTTP_400_BAD_REQUEST)
        # Reject oversized uploads before parsing (Feature 4). Generous default.
        max_bytes = getattr(settings, "BULK_MAX_BYTES", 5 * 1024 * 1024)
        if getattr(upload, "size", 0) and upload.size > max_bytes:
            mb = max_bytes / (1024 * 1024)
            return None, Response({"file": [f"File too large (max {mb:.0f} MB)."]},
                                  status=status.HTTP_400_BAD_REQUEST)
        return upload, None

    @action(detail=True, methods=["post"], url_path="tag-requirements")
    def tag_requirements(self, request, pk=None):
        """Add this candidate to one or more requirements' Review Pools ("under
        review"). Body: {"requirement_ids": [..]} (or {"requirement": id}). §9 — only
        each requirement's assigned recruiter (or an admin) may tag. Never creates a
        jd_cv_mapping."""
        candidate = self.get_object()
        raw = request.data.get("requirement_ids")
        if raw is None and request.data.get("requirement") is not None:
            raw = [request.data.get("requirement")]
        if not raw:
            raise ValidationError({"requirement_ids": ["Select at least one requirement."]})
        from .services import DecisionError, tag_candidate_for_review
        tagged = []
        for rid in raw:
            req = RequirementTracker.objects.filter(req_id=rid).first()
            if req is None:
                raise ValidationError({"requirement_ids": [f"Requirement {rid} not found."]})
            _authorize_review_pool(request.user, req)
            try:
                tag_candidate_for_review(candidate=candidate, requirement=req, user=request.user)
            except DecisionError as exc:
                raise ValidationError({"detail": [str(exc)]})
            tagged.append(rid)
        return Response({"tagged": tagged}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="untag-requirement")
    def untag_requirement(self, request, pk=None):
        """Remove this candidate from a requirement's Review Pool. Body:
        {"requirement": id}. §9 authorization applies."""
        candidate = self.get_object()
        rid = request.data.get("requirement")
        req = RequirementTracker.objects.filter(req_id=rid).first() if rid else None
        if req is None:
            raise ValidationError({"requirement": ["Requirement not found."]})
        _authorize_review_pool(request.user, req)
        from .services import untag_candidate_review
        untag_candidate_review(candidate=candidate, requirement=req, user=request.user)
        return Response({"untagged": rid}, status=status.HTTP_200_OK)

    def _bulk_source_requirement(self, request):
        """Resolve optional requirement (skill tagging) + source. Source is
        configurable via Source Master; defaults to 'Naukri' if omitted. Returns
        (source, requirement, error_response)."""
        requirement = None
        req_id = request.data.get("requirement")
        if req_id:
            requirement = RequirementTracker.objects.filter(req_id=req_id).first()
            if requirement is None:
                return None, None, Response({"requirement": ["Requirement not found."]},
                                            status=status.HTTP_400_BAD_REQUEST)
            # §9 authorization + the requirement must be open for new candidates
            # (the import auto-creates review-pool tags, never skill copies).
            _authorize_review_pool(request.user, requirement)
            from .services import _requirement_open_for_review
            if not _requirement_open_for_review(requirement):
                return None, None, Response(
                    {"requirement": ["This requirement is not open for new candidates."]},
                    status=status.HTTP_400_BAD_REQUEST)
        source = None
        raw_source = request.data.get("source")
        if raw_source:
            source = (SourceMaster.objects.filter(source_id=raw_source).first()
                      if str(raw_source).isdigit()
                      else SourceMaster.objects.filter(source_name__iexact=str(raw_source)).first())
        if source is None:
            source = SourceMaster.objects.filter(source_name__iexact="Naukri").first()
        return source, requirement, None

    @action(detail=False, methods=["post"], url_path="bulk-preview",
            parser_classes=[MultiPartParser, FormParser])
    def bulk_preview(self, request):
        """Validate every row (no candidate writes) + persist a reusable DRAFT
        batch so import can confirm this exact dataset (returns its `batch_id`)."""
        upload, err = self._bulk_file(request)
        if err:
            return err
        report = preview_candidates_excel(file=upload, user=request.user)
        code = status.HTTP_200_OK if report.get("ok") else status.HTTP_400_BAD_REQUEST
        return Response(report, status=code)

    @action(detail=False, methods=["post"], url_path="bulk-upload",
            parser_classes=[MultiPartParser, FormParser])
    def bulk_upload(self, request):
        """Import valid rows. Preferred: confirm a preview DRAFT via `batch_id`
        (imports the exact validated dataset — no re-upload/re-parse). Fallback:
        a direct `file` upload. Optional `requirement` + `source`."""
        source, requirement, err = self._bulk_source_requirement(request)
        if err:
            return err

        batch_id = request.data.get("batch_id")
        if batch_id:
            batch = BulkImportBatch.objects.filter(batch_id=batch_id, status="DRAFT").first()
            if batch is None:
                return Response({"batch_id": ["Draft not found or already used — re-run the preview."]},
                                status=status.HTTP_400_BAD_REQUEST)
            is_admin = getattr(getattr(request.user, "role", None), "role_code", None) == Roles.ADMIN
            if not (is_admin or batch.uploaded_by_id == getattr(request.user, "user_id", None)):
                raise PermissionDenied("You can only confirm your own import draft.")
            report = confirm_import_batch(batch=batch, user=request.user, source=source, requirement=requirement)
            code = status.HTTP_200_OK if report.get("ok") else status.HTTP_400_BAD_REQUEST
            return Response(report, status=code)

        # Fallback: direct file import (no preview).
        upload, ferr = self._bulk_file(request)
        if ferr:
            return ferr
        report = import_candidates_excel(file=upload, user=request.user,
                                         requirement=requirement, source=source)
        code = status.HTTP_200_OK if report.get("ok") else status.HTTP_400_BAD_REQUEST
        return Response(report, status=code)

    # ---- Location reconciliation ----------------------------------------
    @action(detail=False, methods=["get"], url_path="unmapped-locations")
    def unmapped_locations(self, request):
        """Distinct import 'kept as text' locations (Location FK still NULL), with
        candidate counts + a suggested Location Master match."""
        return Response(unmapped_location_summary())

    @action(detail=False, methods=["post"], url_path="reconcile-location")
    def reconcile_location(self, request):
        """Map every still-unmapped candidate with this exact location text to an
        existing Location Master city (sets the FK, clears the text). Does NOT
        create master rows — add a new city via master data first, then map."""
        text = (request.data.get("text") or "").strip()
        loc_id = request.data.get("location_id")
        if not text or not loc_id:
            return Response({"detail": "Both 'text' and 'location_id' are required."},
                            status=status.HTTP_400_BAD_REQUEST)
        location = LocationMaster.objects.filter(location_id=loc_id).first()
        if location is None:
            return Response({"location_id": ["Location not found."]}, status=status.HTTP_400_BAD_REQUEST)
        n = reconcile_location_service(text=text, location=location, user=request.user)
        return Response({"reconciled": n, "location": f"{location.city}, {location.state}"},
                        status=status.HTTP_200_OK)

    # ---- Candidate Details drawer (read-only composite) -----------------
    @staticmethod
    def _active_cv_document(candidate):
        return (
            CvDocument.objects.filter(candidate=candidate, active_version=True).order_by("-document_id").first()
            or CvDocument.objects.filter(candidate=candidate).order_by("-document_id").first()
        )

    @staticmethod
    def _resume_fs_path(doc):
        # file_path is stored relative to the backend root (e.g. "uploads/cvs/..").
        if not doc or not doc.file_path:
            return None
        return os.path.join(settings.BASE_DIR, doc.file_path)

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["get"], url_path="detail")
    def candidate_detail(self, request, pk=None):
        """Composite payload for the Candidate Details drawer: the candidate,
        their resume metadata, requirement history and an activity timeline —
        built from existing models (no schema changes)."""
        cand = self.get_object()

        # Resume (active CV document). `available` reflects whether the file is
        # actually on disk (seed rows are metadata-only).
        doc = self._active_cv_document(cand)
        resume = None
        if doc:
            path = self._resume_fs_path(doc)
            resume = {
                "document_id": doc.document_id,
                "file_name": doc.file_name,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "uploaded_on": doc.upload_date.isoformat() if doc.upload_date else None,
                "available": bool(path and os.path.exists(path)),
            }

        # Requirement history — every mapping this candidate appears in.
        mappings = (
            JdCvMapping.objects.filter(candidate=cand)
            .select_related("req", "req__client", "req__recruiter", "application_stage")
            .order_by("-created_on", "-mapping_id")
        )
        requirement_history = [
            {
                "mapping_id": m.mapping_id,
                "req_id": m.req_id,
                "req_tracker_no": m.req.req_tracker_no,
                "jd_role_name": m.req.jd_role_name,
                "client_name": m.req.client.client_name if m.req.client_id else None,
                "recruiter_name": m.req.recruiter.full_name if m.req.recruiter_id else None,
                "status": m.application_stage.status_name if m.application_stage_id else None,
                "status_code": m.application_stage.status_code if m.application_stage_id else None,
                "created_on": m.created_on.isoformat() if m.created_on else None,
            }
            for m in mappings
        ]

        # Global activity timeline — candidate-level events (creation/import) plus
        # every application event, oldest first. Each application event is tagged
        # with its requirement (name + tracker no) so the global feed never mixes
        # applications without context; candidate-level events carry no requirement.
        def _req_ctx(req):
            return {
                "req_id": req.req_id if req else None,
                "req_tracker_no": req.req_tracker_no if req else None,
                "req_role": req.jd_role_name if req else None,
            }

        events = []
        if cand.created_on:
            events.append({
                "type": "created", "title": "Candidate added",
                "detail": f"Uploaded as {cand.cv_serial}",
                "actor": cand.uploaded_by.full_name if cand.uploaded_by_id else None,
                "timestamp": cand.created_on.isoformat(),
                **_req_ctx(None),
            })
        for it in (CandidateInteraction.objects.filter(candidate=cand)
                   .select_related("created_by", "req").order_by("created_on", "interaction_id")):
            events.append({
                "type": (it.interaction_type or "").lower(),
                "title": (it.interaction_type or "").replace("_", " ").title(),
                "detail": it.comment,
                "actor": it.created_by.full_name if it.created_by_id else None,
                "timestamp": it.created_on.isoformat() if it.created_on else None,
                **_req_ctx(it.req),
            })
        for c in (CommunicationLog.objects.filter(candidate=cand)
                  .select_related("sent_by", "req").order_by("sent_on", "comm_id")):
            events.append({
                "type": "email",
                "title": f"JD email {(c.status or '').lower()}".strip(),
                "detail": c.subject,
                "actor": c.sent_by.full_name if c.sent_by_id else None,
                "timestamp": c.sent_on.isoformat() if c.sent_on else None,
                **_req_ctx(c.req),
            })
        events.sort(key=lambda e: e["timestamp"] or "")

        # Active pre-pipeline review associations (which requirements this candidate
        # is currently UNDER REVIEW for — the Review Pool, distinct from the pipeline
        # mappings above).
        from admin_module.models import CandidateRequirementReview
        from core.constants import ReviewStatus
        active_reviews = [
            {
                "review_id": rv.review_id,
                "req_id": rv.req_id,
                "req_tracker_no": rv.req.req_tracker_no,
                "jd_role_name": rv.req.jd_role_name,
                "client_name": rv.req.client.client_name if rv.req.client_id else None,
                "tagged_on": rv.tagged_on.isoformat() if rv.tagged_on else None,
            }
            for rv in (CandidateRequirementReview.objects
                       .filter(candidate=cand, status=ReviewStatus.ACTIVE)
                       .select_related("req", "req__client").order_by("-tagged_on"))
        ]

        return Response({
            "candidate": CandidateReadSerializer(cand, context=self.get_serializer_context()).data,
            "resume": resume,
            "requirement_history": requirement_history,
            "active_reviews": active_reviews,
            "timeline": events,
        })

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    @action(detail=True, methods=["get"])
    def resume(self, request, pk=None):
        """Stream the candidate's active résumé file (for inline preview /
        download). 404 when no file is on disk."""
        cand = self.get_object()
        doc = self._active_cv_document(cand)
        path = self._resume_fs_path(doc)
        if not path or not os.path.exists(path):
            raise Http404("Resume file not available.")
        return FileResponse(open(path, "rb"),
                            content_type=doc.file_type or "application/octet-stream",
                            filename=doc.file_name)


class DuplicateReviewViewSet(viewsets.ModelViewSet):
    """Duplicate Review workflow — a SEPARATE process from the candidate lifecycle
    (never touches candidate_status). Recruiters CREATE a review when a duplicate
    is detected; only Admins may list, retrieve and resolve them (the Duplicate
    Review page is Admin-only). Full audit: created_by/on + resolved_by/on."""
    queryset = (
        CandidateDuplicateReview.objects
        .select_related("existing_candidate__candidate_status", "created_by", "resolved_by")
        .order_by("-review_id")
    )
    serializer_class = DuplicateReviewSerializer
    filterset_fields = ["review_status", "resolution"]

    def get_permissions(self):
        if self.action == "create":
            return [IsRecruiterOrAdmin()]
        return [IsAdministrator()]  # list / retrieve / resolve → Admin only

    def get_serializer_class(self):
        if self.action == "create":
            return DuplicateReviewCreateSerializer
        return DuplicateReviewSerializer

    def create(self, request, *args, **kwargs):
        write = DuplicateReviewCreateSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        d = write.validated_data
        # Shared create/dedupe (same path bulk upload uses).
        from .services import record_possible_duplicate
        review, created = record_possible_duplicate(
            existing_candidate=d["existing_candidate"],
            new_candidate_name=d["new_candidate_name"],
            new_mobile=d["new_mobile"],
            new_email=d.get("new_email"),
            detection_reason=d["detection_reason"],
            submitted_payload=d.get("submitted_payload"),
            user=request.user,
        )
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(DuplicateReviewSerializer(review).data, status=code)

    @extend_schema(request=DuplicateReviewResolveSerializer, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def resolve(self, request, pk=None):
        """Admin resolves a review (two outcomes):
          - UPDATED       — write the chosen name/mobile/email onto the EXISTING
                            candidate (the submitted row was never imported), so the
                            one surviving record carries the correct details. Covers
                            both "same person, adopt submitted info" and "fix a typo
                            on the existing record".
          - KEPT_SEPARATE — dismiss: keep the existing record as-is, discard the
                            submission (shown in the UI as "Ignored").
        (Legacy MERGED/CORRECTED still resolve the same way for old clients.)
        Records the full audit; never loses history."""
        review = self.get_object()
        if review.review_status == DuplicateReview.RESOLVED:
            raise ValidationError({"detail": ["This review is already resolved."]})
        serializer = DuplicateReviewResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        resolution = d["resolution"]

        # MERGED and CORRECTED both write the chosen identity onto the existing
        # candidate; only the fields that actually change are saved. Mobile/email
        # are pre-checked against the UNIQUE constraints so a clash returns a clean
        # 400 (and the review stays open) instead of a DB IntegrityError.
        if resolution in (DuplicateReview.UPDATED, DuplicateReview.MERGED, DuplicateReview.CORRECTED):
            cand = review.existing_candidate
            changed = []
            name = (d.get("name") or "").strip()
            if name and name != (cand.candidate_name or ""):
                cand.candidate_name = name; changed.append("candidate_name")
            mobile = (d.get("mobile") or "").strip()
            if mobile and mobile != (cand.mobile or ""):
                if CandidateMaster.objects.filter(mobile=mobile).exclude(cv_id=cand.cv_id).exists():
                    raise ValidationError({"detail": ["That mobile already belongs to another candidate — can't apply it."]})
                cand.mobile = mobile; changed.append("mobile")
            email = (d.get("email") or "").strip()
            if email and email.lower() != (cand.email or "").lower():
                if CandidateMaster.objects.filter(email__iexact=email).exclude(cv_id=cand.cv_id).exists():
                    raise ValidationError({"detail": ["That email already belongs to another candidate — can't apply it."]})
                cand.email = email; changed.append("email")
            if changed:
                cand.updated_by = request.user
                cand.updated_on = timezone.now()
                cand.save(update_fields=changed + ["updated_by", "updated_on"])

        review.resolution = resolution
        review.notes = d.get("notes") or None
        review.review_status = DuplicateReview.RESOLVED
        review.resolved_by = request.user
        review.resolved_on = timezone.now()
        review.save(update_fields=["resolution", "notes", "review_status", "resolved_by", "resolved_on"])
        return Response(DuplicateReviewSerializer(review).data, status=status.HTTP_200_OK)


class ImportBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Bulk-import history + audit. Recruiters see their own uploads; Admins see
    all. `report/` re-downloads the per-row report; `rollback/` soft-deletes the
    still-untouched candidates a batch created."""
    permission_classes = [IsRecruiterOrAdmin]
    queryset = (
        BulkImportBatch.objects
        .exclude(status="DRAFT")  # drafts are transient preview state, not history
        .select_related("uploaded_by", "source", "requirement")
        .order_by("-batch_id")
    )

    def get_serializer_class(self):
        return BulkImportBatchDetailSerializer if self.action == "retrieve" else BulkImportBatchListSerializer

    def _is_admin(self):
        return getattr(getattr(self.request.user, "role", None), "role_code", None) == Roles.ADMIN

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return qs
        if not self._is_admin():
            qs = qs.filter(uploaded_by_id=getattr(self.request.user, "user_id", None))
        return qs

    @action(detail=True, methods=["get"], url_path="report")
    def report(self, request, pk=None):
        """Download this batch's per-row report as an .xlsx."""
        import openpyxl
        batch = self.get_object()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Import Report"
        ws.append(["Excel Row", "Name", "Mobile", "Email", "Status", "Errors", "Warnings"])
        for r in (batch.row_report or []):
            ws.append([
                r.get("excel_row"), r.get("name"), r.get("mobile"), r.get("email"),
                r.get("status"), " | ".join(r.get("errors") or []), " | ".join(r.get("warnings") or []),
            ])
        resp = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = f'attachment; filename="import_batch_{batch.batch_id}_report.xlsx"'
        wb.save(resp)
        return resp

    @action(detail=True, methods=["post"], url_path="mark-failed", permission_classes=[IsAdministrator])
    def mark_failed(self, request, pk=None):
        """Admin recovery for a batch stuck in PENDING (e.g. after a crash)."""
        batch = self.get_object()
        if batch.status != "PENDING":
            return Response({"detail": "Only a PENDING batch can be marked failed."},
                            status=status.HTTP_400_BAD_REQUEST)
        batch.status = "FAILED"
        batch.error_message = "Marked FAILED by admin (stuck PENDING)."
        batch.completed_on = timezone.now()
        batch.save(update_fields=["status", "error_message", "completed_on"])
        return Response({"batch_id": batch.batch_id, "status": batch.status}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="rollback")
    def rollback(self, request, pk=None):
        """Soft-delete the still-untouched candidates this batch created. Allowed
        for an Admin or the recruiter who uploaded the batch."""
        batch = self.get_object()
        if not (self._is_admin() or batch.uploaded_by_id == getattr(request.user, "user_id", None)):
            raise PermissionDenied("Only an admin or the uploader can roll back this import.")
        if batch.status != "COMPLETED":
            msg = ("This batch has already been rolled back." if batch.status == "ROLLED_BACK"
                   else f"Only a completed import can be rolled back (this batch is {batch.status}).")
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        result = rollback_import_batch(batch=batch, user=request.user)
        return Response(result, status=status.HTTP_200_OK)
