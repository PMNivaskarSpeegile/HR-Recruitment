"""
Pipeline API (UC3).

GET  /api/pipeline/new-cvs/?requirement=<id>   skill-matched New_CV candidates to review
POST /api/pipeline/review/                     apply a review decision
"""
import logging

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from admin_module.models import (
    CandidateInteraction,
    CandidateMaster,
    CommunicationLog,
    JdCvMapping,
    RequirementTracker,
    Screening,
)
from authentication.permissions import IsRecruiterOrAdmin
from core.constants import Roles

from .screening import (
    ScreeningError,
    complete_screening,
    reschedule_screening_round,
    schedule_screening,
    screenings_for,
)
from .serializers import (
    AdvanceInputSerializer,
    CommunicationLogSerializer,
    JdCvMappingSerializer,
    OutcomeInputSerializer,
    RescheduleInputSerializer,
    ReviewInputSerializer,
    ReviewPoolCandidateSerializer,
    ScreeningCompleteInputSerializer,
    ScreeningRescheduleInputSerializer,
    ScreeningScheduleInputSerializer,
    ScreeningSerializer,
    SendJdInputSerializer,
    TransitionInputSerializer,
)
from .services import (
    PipelineError,
    TemplateNotConfigured,
    advance_stage,
    communications_for_requirement,
    mappings_for_requirement,
    new_cv_candidates_for_requirement,
    preview_jd_emails,
    record_outcome,
    reschedule_screening,
    review_candidate,
    send_jd_emails,
    transition_mappings,
)

logger = logging.getLogger("ats")


def _get_requirement_for_recruiter(request, req_id, *, require_workable=False):
    """Fetch a requirement, enforcing 'recruiters only work their assigned reqs'
    (admins bypass). With require_workable=True, also blocks recruitment ACTIONS
    when the requirement is not in a workable state (on Hold / Cancelled / Closed
    Lost) or has expired — reads are never blocked. Raises DRF exceptions."""
    if not req_id:
        raise ValidationError({"requirement": ["This query parameter is required."]})

    requirement = RequirementTracker.objects.filter(req_id=req_id).first()
    if requirement is None:
        raise ValidationError({"requirement": ["Requirement not found."]})

    user = request.user
    is_admin = getattr(getattr(user, "role", None), "role_code", None) == Roles.ADMIN
    if not is_admin and requirement.recruiter_id != getattr(user, "user_id", None):
        raise PermissionDenied("This requirement is not assigned to you.")

    if require_workable:
        from core.constants import ReqStatus
        from requirements.services import requirement_is_expired
        if requirement.recruitment_ended:
            raise ValidationError({"detail":
                "Recruitment has permanently ended for this requirement — no further "
                "candidate tagging or pipeline progression is allowed."})
        if requirement_is_expired(requirement):
            raise ValidationError({"detail":
                "This requirement has expired — recruitment actions are paused until the "
                "Target Fill Date is extended."})
        code = requirement.req_status.status_code if requirement.req_status_id else None
        if code not in ReqStatus.WORKABLE:
            raise ValidationError({"detail":
                f"Recruitment actions are not allowed while this requirement is '{code}'."})

    return requirement


class NewCvListView(ListAPIView):
    """UC3 Step 2 — usable candidates for a requirement (New_CV or Saved, not
    already mapped), ranked by skill match (best first)."""
    permission_classes = [IsRecruiterOrAdmin]
    serializer_class = ReviewPoolCandidateSerializer
    # Server-side search across the whole pool (applied before pagination; the
    # relevance ordering from the queryset is preserved).
    filter_backends = [filters.SearchFilter]
    search_fields = ["candidate_name", "email", "mobile", "cv_serial"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation
            return CandidateMaster.objects.none()
        self._requirement = _get_requirement_for_recruiter(
            self.request, self.request.query_params.get("requirement")
        )
        return new_cv_candidates_for_requirement(self._requirement)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        req = getattr(self, "_requirement", None)
        ctx["required_skills"] = (
            len([s for s in (req.skill1_id, req.skill2_id, req.skill3_id) if s]) if req else 0
        )
        return ctx


class ReviewView(APIView):
    """UC3 — initial resume review: apply Shortlist / Not Suitable to a candidate
    for a requirement (sets the CV verdict + the application stage)."""
    permission_classes = [IsRecruiterOrAdmin]

    @extend_schema(request=ReviewInputSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = ReviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        requirement = _get_requirement_for_recruiter(request, data["requirement"].req_id, require_workable=True)
        candidate = data["candidate"]

        mapping = review_candidate(
            requirement=requirement,
            candidate=candidate,
            decision=data["decision"],
            comments=data.get("comments"),
            rejection_reason=data.get("rejection_reason"),
            user=request.user,
        )

        candidate.refresh_from_db(fields=["candidate_status"])
        body = {
            "decision": data["decision"],
            "candidate_status": candidate.candidate_status.status_code if candidate.candidate_status_id else None,
            "mapping": JdCvMappingSerializer(mapping).data if mapping else None,
        }
        return Response(body, status=status.HTTP_200_OK)


class MappingListView(ListAPIView):
    """Load pipeline rows for a requirement, optionally by status.
    GET /api/pipeline/mappings/?requirement=<id>&status=<code>"""
    permission_classes = [IsRecruiterOrAdmin]
    serializer_class = JdCvMappingSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation
            return JdCvMapping.objects.none()
        requirement = _get_requirement_for_recruiter(
            self.request, self.request.query_params.get("requirement")
        )
        return mappings_for_requirement(requirement, self.request.query_params.get("status"))


class JdPreviewView(APIView):
    """UC4 — POST /api/pipeline/jd-preview/  {requirement, mapping_ids[]}
    Render (without sending) the JD email per shortlisted recipient."""
    permission_classes = [IsRecruiterOrAdmin]

    @extend_schema(request=SendJdInputSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = SendJdInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        requirement = _get_requirement_for_recruiter(request, data["requirement"].req_id, require_workable=True)
        try:
            result = preview_jd_emails(
                requirement=requirement, mapping_ids=data["mapping_ids"], user=request.user
            )
        except TemplateNotConfigured as exc:
            raise ValidationError({"template": [str(exc)]})
        return Response(result, status=status.HTTP_200_OK)


class SendJdView(APIView):
    """UC4 — POST /api/pipeline/send-jd/  {requirement, mapping_ids[]}"""
    permission_classes = [IsRecruiterOrAdmin]

    @extend_schema(request=SendJdInputSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = SendJdInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        requirement = _get_requirement_for_recruiter(request, data["requirement"].req_id, require_workable=True)
        try:
            report = send_jd_emails(requirement=requirement, mapping_ids=data["mapping_ids"], user=request.user)
        except TemplateNotConfigured as exc:
            raise ValidationError({"template": [str(exc)]})
        return Response(report, status=status.HTTP_200_OK)


class CommunicationListView(ListAPIView):
    """UC4 JD tracker — GET /api/pipeline/communications/?requirement=<id>
    Every JD email send attempt for a requirement, newest first."""
    permission_classes = [IsRecruiterOrAdmin]
    serializer_class = CommunicationLogSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation
            return CommunicationLog.objects.none()
        requirement = _get_requirement_for_recruiter(
            self.request, self.request.query_params.get("requirement")
        )
        return communications_for_requirement(requirement)


class TransitionView(APIView):
    """UC5 — POST /api/pipeline/transition/
    {requirement, mapping_ids[], to_status, comments?, screening_datetime?}"""
    permission_classes = [IsRecruiterOrAdmin]

    @extend_schema(request=TransitionInputSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = TransitionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        requirement = _get_requirement_for_recruiter(request, data["requirement"].req_id, require_workable=True)
        report = transition_mappings(
            requirement=requirement,
            mapping_ids=data["mapping_ids"],
            to_status=data["to_status"],
            comments=data.get("comments"),
            screening_datetime=data.get("screening_datetime"),
            screening_mode=data.get("screening_mode"),
            rejection_reason=data.get("rejection_reason"),
            user=request.user,
        )
        return Response(report, status=status.HTTP_200_OK)


class OutcomeView(APIView):
    """POST /api/pipeline/outcome/ — record a stage OUTCOME on an application via
    the centralized engine (advance the stage or close the application). Includes
    the optional "Move to Talent Pool?" answer for a non-hired close."""
    permission_classes = [IsRecruiterOrAdmin]

    @extend_schema(request=OutcomeInputSerializer, responses={200: JdCvMappingSerializer})
    def post(self, request):
        s = OutcomeInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        m = s.validated_data["mapping"]
        _get_requirement_for_recruiter(request, m.req_id, require_workable=True)
        try:
            record_outcome(
                mapping=m, outcome=s.validated_data["outcome"], user=request.user,
                reason=s.validated_data.get("reason"),
                rejection_reason=s.validated_data.get("rejection_reason"),
                move_to_talent_pool=s.validated_data.get("move_to_talent_pool", False),
            )
        except PipelineError as exc:
            raise ValidationError({"outcome": [str(exc)]})
        m.refresh_from_db()
        return Response(JdCvMappingSerializer(m).data, status=status.HTTP_200_OK)


class AdvanceView(APIView):
    """POST /api/pipeline/advance/ — advance a stage via an ACTION (Send JD /
    Schedule Screening / Release Offer)."""
    permission_classes = [IsRecruiterOrAdmin]

    @extend_schema(request=AdvanceInputSerializer, responses={200: JdCvMappingSerializer})
    def post(self, request):
        s = AdvanceInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        m = s.validated_data["mapping"]
        _get_requirement_for_recruiter(request, m.req_id, require_workable=True)
        try:
            advance_stage(
                mapping=m, action=s.validated_data["action"], user=request.user,
                screening_datetime=s.validated_data.get("screening_datetime"),
                screening_mode=s.validated_data.get("screening_mode"),
                reason=s.validated_data.get("reason"),
            )
        except PipelineError as exc:
            raise ValidationError({"action": [str(exc)]})
        m.refresh_from_db()
        return Response(JdCvMappingSerializer(m).data, status=status.HTTP_200_OK)


class RescheduleView(APIView):
    """POST /api/pipeline/reschedule/ — reschedule a scheduled screening (must be
    a future date/time; stage unchanged)."""
    permission_classes = [IsRecruiterOrAdmin]

    @extend_schema(request=RescheduleInputSerializer, responses={200: JdCvMappingSerializer})
    def post(self, request):
        s = RescheduleInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        m = s.validated_data["mapping"]
        _get_requirement_for_recruiter(request, m.req_id, require_workable=True)
        try:
            reschedule_screening(
                mapping=m, new_datetime=s.validated_data["scheduled_at"], user=request.user,
                screening_mode=s.validated_data.get("screening_mode"),
            )
        except PipelineError as exc:
            raise ValidationError({"scheduled_at": [str(exc)]})
        m.refresh_from_db()
        return Response(JdCvMappingSerializer(m).data, status=status.HTTP_200_OK)


class MappingTimelineView(APIView):
    """GET /api/pipeline/mappings/<id>/timeline/ — the recruitment timeline for ONE
    application (this requirement only). The candidate module shows the full
    cross-requirement history; the pipeline shows just this mapping's."""
    permission_classes = [IsRecruiterOrAdmin]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request, pk):
        m = JdCvMapping.objects.select_related("req", "candidate").filter(mapping_id=pk).first()
        if m is None:
            raise ValidationError({"mapping": ["Application not found."]})
        _get_requirement_for_recruiter(request, m.req_id)  # scope to recruiter's reqs
        events = []
        for it in (CandidateInteraction.objects.filter(candidate=m.candidate, req=m.req)
                   .select_related("created_by").order_by("created_on", "interaction_id")):
            events.append({
                "type": (it.interaction_type or "").lower(),
                "title": (it.interaction_type or "").replace("_", " ").title(),
                "detail": it.comment,
                "actor": it.created_by.full_name if it.created_by_id else None,
                "timestamp": it.created_on.isoformat() if it.created_on else None,
            })
        for c in (CommunicationLog.objects.filter(candidate=m.candidate, req=m.req)
                  .select_related("sent_by").order_by("sent_on", "comm_id")):
            events.append({
                "type": "email",
                "title": f"JD email {(c.status or '').lower()}".strip(),
                "detail": c.subject,
                "actor": c.sent_by.full_name if c.sent_by_id else None,
                "timestamp": c.sent_on.isoformat() if c.sent_on else None,
            })
        events.sort(key=lambda e: e["timestamp"] or "")
        return Response({"mapping": JdCvMappingSerializer(m).data, "timeline": events})


def _mapping_for_recruiter(request, mapping_id, *, require_workable=False):
    """Load an application and enforce recruiter scoping via its requirement."""
    mapping = (
        JdCvMapping.objects
        .select_related("req", "candidate", "application_stage")
        .filter(mapping_id=mapping_id)
        .first()
    )
    if mapping is None:
        raise ValidationError({"mapping": ["Application not found."]})
    _get_requirement_for_recruiter(request, mapping.req_id, require_workable=require_workable)
    return mapping


class ScreeningListCreateView(APIView):
    """Screening rounds of an application.
    GET  /api/pipeline/screenings/?mapping=<id>  → chronological history
    POST /api/pipeline/screenings/               → schedule (add) a round"""
    permission_classes = [IsRecruiterOrAdmin]

    @extend_schema(responses={200: ScreeningSerializer(many=True)})
    def get(self, request):
        mapping = _mapping_for_recruiter(request, request.query_params.get("mapping"))
        return Response(ScreeningSerializer(screenings_for(mapping), many=True).data)

    @extend_schema(request=ScreeningScheduleInputSerializer, responses={201: ScreeningSerializer})
    def post(self, request):
        serializer = ScreeningScheduleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        mapping = _mapping_for_recruiter(request, data["mapping"].mapping_id, require_workable=True)
        try:
            screening = schedule_screening(
                mapping=mapping, mode=data["screening_mode"], scheduled_at=data["scheduled_at"],
                interviewer=data.get("interviewer"), notes=data.get("notes"), user=request.user,
            )
        except ScreeningError as exc:
            raise ValidationError({"detail": str(exc)})
        return Response(ScreeningSerializer(screening).data, status=status.HTTP_201_CREATED)


class ScreeningCompleteView(APIView):
    """POST /api/pipeline/screenings/<id>/complete/  {outcome, notes?}"""
    permission_classes = [IsRecruiterOrAdmin]

    @extend_schema(request=ScreeningCompleteInputSerializer, responses={200: ScreeningSerializer})
    def post(self, request, pk):
        screening = Screening.objects.select_related("mapping__req", "screening_mode").filter(pk=pk).first()
        if screening is None:
            raise ValidationError({"detail": "Screening not found."})
        _get_requirement_for_recruiter(request, screening.mapping.req_id, require_workable=True)
        serializer = ScreeningCompleteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            complete_screening(
                screening=screening, outcome=serializer.validated_data["outcome"],
                notes=serializer.validated_data.get("notes"), user=request.user,
            )
        except ScreeningError as exc:
            raise ValidationError({"detail": str(exc)})
        return Response(ScreeningSerializer(screening).data, status=status.HTTP_200_OK)


class ScreeningRescheduleView(APIView):
    """POST /api/pipeline/screenings/<id>/reschedule/  {scheduled_at}"""
    permission_classes = [IsRecruiterOrAdmin]

    @extend_schema(request=ScreeningRescheduleInputSerializer, responses={200: ScreeningSerializer})
    def post(self, request, pk):
        screening = Screening.objects.select_related("mapping__req", "screening_mode").filter(pk=pk).first()
        if screening is None:
            raise ValidationError({"detail": "Screening not found."})
        _get_requirement_for_recruiter(request, screening.mapping.req_id, require_workable=True)
        serializer = ScreeningRescheduleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reschedule_screening_round(
                screening=screening, new_datetime=serializer.validated_data["scheduled_at"],
                user=request.user,
            )
        except ScreeningError as exc:
            raise ValidationError({"detail": str(exc)})
        return Response(ScreeningSerializer(screening).data, status=status.HTTP_200_OK)
