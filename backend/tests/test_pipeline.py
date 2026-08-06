import datetime

import pytest

from admin_module.models import (
    ApplicationStatusMaster,
    ClientMaster,
    JdCvMapping,
    ReqTypeMaster,
    SkillMaster,
)
from candidates.services import upsert_candidate
from core.constants import ApplicationStatus, CandidateStatus
from pipeline.services import review_candidate, transition_mappings
from requirements.services import create_requirement

pytestmark = pytest.mark.django_db


def _make_requirement(hm):
    skills = list(SkillMaster.objects.all()[:3])
    return create_requirement(validated_data={
        "client": ClientMaster.objects.first(), "req_type": ReqTypeMaster.objects.first(),
        "jd_role_name": "R", "positions_open": 1, "req_date": datetime.date(2026, 6, 21),
        "skill1": skills[0], "skill2": skills[1], "skill3": skills[2],
    }, user=hm)


def _make_candidate(rec, mobile):
    return upsert_candidate(
        data={"candidate_name": "C", "mobile": mobile, "email": f"{mobile}@example.com",
              "is_willing_to_relocate": False},
        user=rec,
    )["candidate"]


def _mapping_at(status_code, hm, rec, mobile):
    req = _make_requirement(hm)
    cand = _make_candidate(rec, mobile)
    status = ApplicationStatusMaster.objects.get(status_code=status_code)
    mapping = JdCvMapping.objects.create(req=req, candidate=cand, application_stage=status, is_active=True)
    return mapping, req, cand


def test_review_shortlist_sets_stage(hm_user, recruiter_user):
    req = _make_requirement(hm_user)
    cand = _make_candidate(recruiter_user, "9000001000")
    mapping = review_candidate(requirement=req, candidate=cand, decision="SHORTLISTED",
                               comments="ok", user=recruiter_user)
    # application_stage is the single source of truth for progress.
    assert mapping.application_stage.status_code == "SHORTLISTED"
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "SAVED"  # candidate stays in the pool


def test_review_not_suitable_sets_stage(hm_user, recruiter_user):
    req = _make_requirement(hm_user)
    cand = _make_candidate(recruiter_user, "9000001099")
    mapping = review_candidate(requirement=req, candidate=cand, decision="NOT_SUITABLE",
                               comments="skills gap", user=recruiter_user)
    assert mapping.application_stage.status_code == "NOT_SUITABLE"  # closed at the Not-Suitable stage
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "SAVED"  # still available for other reqs


def test_review_only_offers_shortlist_and_not_suitable():
    from pipeline.services import REVIEW_DECISIONS
    assert REVIEW_DECISIONS == ["SHORTLISTED", "NOT_SUITABLE"]


def test_review_api_endpoint_shortlist(auth_client, admin_user, hm_user, recruiter_user):
    # Exercises the HTTP view (not just the service) — guards the response payload.
    req = _make_requirement(hm_user)
    cand = _make_candidate(recruiter_user, "9000004000")
    resp = auth_client(admin_user).post(
        "/api/pipeline/review/",
        {"requirement": req.req_id, "candidate": cand.cv_id, "decision": "SHORTLISTED"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["candidate_status"] == "SAVED"
    assert resp.data["mapping"]["application_stage_code"] == "SHORTLISTED"


def test_review_api_rejects_removed_decisions(auth_client, admin_user, hm_user, recruiter_user):
    req = _make_requirement(hm_user)
    cand = _make_candidate(recruiter_user, "9000004001")
    resp = auth_client(admin_user).post(
        "/api/pipeline/review/",
        {"requirement": req.req_id, "candidate": cand.cv_id, "decision": "FAKE"},
        format="json",
    )
    assert resp.status_code == 400  # Fake/Save no longer valid review decisions


def test_legal_transition(hm_user, recruiter_user):
    # OK to Proceed → Offer Released is a legal stage advance.
    mapping, req, _ = _mapping_at(ApplicationStatus.OK_TO_PROCEED, hm_user, recruiter_user, "9000001001")
    report = transition_mappings(requirement=req, mapping_ids=[mapping.mapping_id],
                                 to_status=ApplicationStatus.OFFERED, comments="",
                                 screening_datetime=None, user=recruiter_user)
    assert report["updated"] == 1 and not report["invalid"]


def test_illegal_transition_rejected(hm_user, recruiter_user):
    # Schedule Screening is no longer a stage — JD Email Sent can't jump to it.
    mapping, req, _ = _mapping_at(ApplicationStatus.JD_EMAIL_SENT, hm_user, recruiter_user, "9000001002")
    report = transition_mappings(requirement=req, mapping_ids=[mapping.mapping_id],
                                 to_status=ApplicationStatus.OK_TO_PROCEED, comments="",
                                 screening_datetime=None, user=recruiter_user)
    assert report["updated"] == 0 and len(report["invalid"]) == 1


def test_offer_flow_accept_and_decline(hm_user, recruiter_user):
    # Offer Released → Offer Accepted advances to Awaiting Joining.
    m1, req, _ = _mapping_at(ApplicationStatus.OFFERED, hm_user, recruiter_user, "9000001003")
    r1 = transition_mappings(requirement=req, mapping_ids=[m1.mapping_id],
                             to_status=ApplicationStatus.AWAITING_JOINING, comments="",
                             screening_datetime=None, user=recruiter_user)
    assert r1["updated"] == 1
    m1.refresh_from_db()
    assert m1.application_stage.status_code == "AWAITING_JOINING"

    # Offer Released → Offer Declined closes the app. Talent Pool is now an
    # explicit recruiter decision (not automatic), so a plain decline records no
    # rejection and does NOT force the candidate to Talent Pool / Reject Hold.
    m2, req2, cand2 = _mapping_at(ApplicationStatus.OFFERED, hm_user, recruiter_user, "9000001005")
    transition_mappings(requirement=req2, mapping_ids=[m2.mapping_id],
                        to_status=ApplicationStatus.OFFER_DECLINED, comments="",
                        screening_datetime=None, user=recruiter_user)
    cand2.refresh_from_db()
    assert cand2.active_rejection_count == 0
    assert cand2.candidate_status.status_code != "REJECT_HOLD"


def test_fake_flips_candidate_global_status(hm_user, recruiter_user):
    mapping, req, cand = _mapping_at(ApplicationStatus.SCREENING_SCHEDULED, hm_user, recruiter_user, "9000001004")
    transition_mappings(requirement=req, mapping_ids=[mapping.mapping_id],
                        to_status=CandidateStatus.FAKE, comments="bad", screening_datetime=None,
                        user=recruiter_user)
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "FAKE"


# --- Redesign: Joining consumes one Open position (no auto-withdraw). ---------

def _awaiting_mapping(req, cand):
    # Joining now flows from the Awaiting Joining stage (offer accepted).
    return JdCvMapping.objects.create(
        req=req, candidate=cand,
        application_stage=ApplicationStatusMaster.objects.get(status_code=ApplicationStatus.AWAITING_JOINING),
        is_active=True,
    )


def test_join_consumes_one_open_position(hm_user, recruiter_user):
    from admin_module.models import RequirementPosition
    from core.constants import ApplicationStatus, PositionStatus
    req = _make_requirement(hm_user)  # 1 opening → 1 seat
    cand = _make_candidate(recruiter_user, "9000002000")
    mapping = _awaiting_mapping(req, cand)

    report = transition_mappings(requirement=req, mapping_ids=[mapping.mapping_id],
                                 to_status=ApplicationStatus.JOINED, comments="joined",
                                 screening_datetime=None, user=recruiter_user)
    assert report["updated"] == 1 and not report["invalid"]

    seat = RequirementPosition.objects.get(req=req)
    assert seat.position_status.status_code == PositionStatus.FILLED
    assert seat.filled_by_mapping_id == mapping.mapping_id
    req.refresh_from_db()
    assert req.req_status.status_code == "CLOSE_FILLED"
    assert req.positions_filled == 1

    # The real join date is recorded, and the join is on the audit feed.
    mapping.refresh_from_db()
    assert mapping.joined_date is not None
    from admin_module.models import ActivityLog
    assert ActivityLog.objects.filter(activity_type="candidate_joined", candidate=cand).exists()


def test_join_refused_when_no_open_position_and_others_untouched(hm_user, recruiter_user):
    from core.constants import ApplicationStatus
    req = _make_requirement(hm_user)  # 1 opening only
    m1 = _awaiting_mapping(req, _make_candidate(recruiter_user, "9000002001"))
    m2 = _awaiting_mapping(req, _make_candidate(recruiter_user, "9000002002"))

    transition_mappings(requirement=req, mapping_ids=[m1.mapping_id], to_status=ApplicationStatus.JOINED,
                        comments="", screening_datetime=None, user=recruiter_user)
    report = transition_mappings(requirement=req, mapping_ids=[m2.mapping_id], to_status=ApplicationStatus.JOINED,
                                 comments="", screening_datetime=None, user=recruiter_user)
    # Over-fill refused: only one seat existed.
    assert report["updated"] == 0 and len(report["invalid"]) == 1
    # No auto-withdraw — the losing application is left independent (still Awaiting Joining).
    m2.refresh_from_db()
    assert m2.application_stage.status_code == "AWAITING_JOINING"


# --- Stage x Outcome engine (centralized) -----------------------------------
def test_engine_advance_records_stage_and_outcome(hm_user, recruiter_user):
    from pipeline.services import record_outcome
    m, req, _ = _mapping_at(ApplicationStatus.SCREENING_SCHEDULED, hm_user, recruiter_user, "9000005001")
    record_outcome(mapping=m, outcome=ApplicationStatus.PASSED, user=recruiter_user)
    m.refresh_from_db()
    assert m.application_stage.status_code == "OK_TO_PROCEED"
    assert m.latest_outcome.status_code == "PASSED"
    assert m.is_closed is False


def test_engine_close_sets_flags_and_talent_pool_is_opt_in(hm_user, recruiter_user):
    from pipeline.services import record_outcome
    # Close with Rejected, opting into Talent Pool.
    m, req, cand = _mapping_at(ApplicationStatus.OK_TO_PROCEED, hm_user, recruiter_user, "9000005002")
    record_outcome(mapping=m, outcome=ApplicationStatus.REJECTED, user=recruiter_user, move_to_talent_pool=True)
    m.refresh_from_db(); cand.refresh_from_db()
    assert m.is_closed is True and m.closed_on is not None
    assert m.latest_outcome.status_code == "REJECTED"
    assert cand.active_rejection_count == 1 and cand.candidate_status.status_code == "SAVED"


def test_engine_rejects_invalid_outcome_for_stage(hm_user, recruiter_user):
    from pipeline.services import PipelineError, record_outcome
    m, _, _ = _mapping_at(ApplicationStatus.SHORTLISTED, hm_user, recruiter_user, "9000005003")
    with pytest.raises(PipelineError):
        record_outcome(mapping=m, outcome=ApplicationStatus.PASSED, user=recruiter_user)


def test_engine_drop_closes_from_jd_email_sent(hm_user, recruiter_user):
    # A candidate can drop out after receiving the JD — Dropped is valid (closes) here.
    from pipeline.services import record_outcome
    m, _, _ = _mapping_at(ApplicationStatus.JD_EMAIL_SENT, hm_user, recruiter_user, "9000005007")
    record_outcome(mapping=m, outcome=ApplicationStatus.DROPPED, user=recruiter_user)
    m.refresh_from_db()
    assert m.is_closed is True and m.latest_outcome.status_code == "DROPPED"


def test_engine_no_response_not_allowed_at_jd_email_sent(hm_user, recruiter_user):
    # No Response is no longer a valid outcome at JD Email Sent — only Drop closes here.
    from pipeline.services import PipelineError, record_outcome
    m, _, _ = _mapping_at(ApplicationStatus.JD_EMAIL_SENT, hm_user, recruiter_user, "9000005011")
    with pytest.raises(PipelineError):
        record_outcome(mapping=m, outcome=ApplicationStatus.NO_RESPONSE, user=recruiter_user)


def test_engine_blacklist_not_allowed_at_ok_to_proceed(hm_user, recruiter_user):
    # Blacklisted is no longer offered at OK to Proceed (client-interview stage).
    from pipeline.services import PipelineError, record_outcome
    m, _, _ = _mapping_at(ApplicationStatus.OK_TO_PROCEED, hm_user, recruiter_user, "9000005012")
    with pytest.raises(PipelineError):
        record_outcome(mapping=m, outcome=ApplicationStatus.BLACKLISTED, user=recruiter_user)


def test_engine_closed_application_is_immutable(hm_user, recruiter_user):
    from pipeline.services import PipelineError, record_outcome
    m, _, _ = _mapping_at(ApplicationStatus.AWAITING_JOINING, hm_user, recruiter_user, "9000005004")
    record_outcome(mapping=m, outcome=ApplicationStatus.WITHDRAWN, user=recruiter_user)
    m.refresh_from_db()
    with pytest.raises(PipelineError):
        record_outcome(mapping=m, outcome=ApplicationStatus.JOINED, user=recruiter_user)


def test_engine_schedule_screening_requires_future_datetime(hm_user, recruiter_user):
    import datetime as dt
    from pipeline.services import PipelineError, SCHEDULE_SCREENING, advance_stage
    # Aware UTC, as the API delivers datetimes (client sends Date.toISOString()).
    now_utc = dt.datetime.now(dt.timezone.utc)
    m, _, _ = _mapping_at(ApplicationStatus.JD_EMAIL_SENT, hm_user, recruiter_user, "9000005005")
    with pytest.raises(PipelineError):
        advance_stage(mapping=m, action=SCHEDULE_SCREENING, user=recruiter_user,
                      screening_datetime=now_utc - dt.timedelta(hours=1))
    advance_stage(mapping=m, action=SCHEDULE_SCREENING, user=recruiter_user,
                  screening_datetime=now_utc + dt.timedelta(days=2))
    m.refresh_from_db()
    assert m.application_stage.status_code == "SCREENING_SCHEDULED"


def test_engine_reschedule_must_be_future(hm_user, recruiter_user):
    import datetime as dt
    from pipeline.services import PipelineError, reschedule_screening
    now_utc = dt.datetime.now(dt.timezone.utc)
    m, _, _ = _mapping_at(ApplicationStatus.SCREENING_SCHEDULED, hm_user, recruiter_user, "9000005006")
    with pytest.raises(PipelineError):
        reschedule_screening(mapping=m, new_datetime=now_utc - dt.timedelta(hours=1), user=recruiter_user)
    reschedule_screening(mapping=m, new_datetime=now_utc + dt.timedelta(days=1), user=recruiter_user)
    m.refresh_from_db()
    assert m.screening_datetime is not None


def test_engine_join_fills_seat_and_audits(hm_user, recruiter_user):
    from admin_module.models import RequirementPosition, StatusChangeHistory
    from pipeline.services import record_outcome
    m, req, cand = _mapping_at(ApplicationStatus.AWAITING_JOINING, hm_user, recruiter_user, "9000005007")
    record_outcome(mapping=m, outcome=ApplicationStatus.JOINED, user=recruiter_user)
    m.refresh_from_db(); cand.refresh_from_db()
    assert m.is_closed and m.latest_outcome.status_code == "JOINED" and m.joined_date is not None
    assert cand.candidate_status.status_code == "JOINED"
    assert RequirementPosition.objects.filter(req=req, position_status__status_code="FILLED").exists()
    assert StatusChangeHistory.objects.filter(entity_type="APPLICATION", entity_id=m.mapping_id,
                                              new_status="JOINED").exists()


# --- Item 6 engine API endpoints -------------------------------------------
def test_outcome_endpoint_advances_stage(auth_client, admin_user, hm_user, recruiter_user):
    m, _, _ = _mapping_at(ApplicationStatus.SCREENING_SCHEDULED, hm_user, recruiter_user, "9000006001")
    r = auth_client(admin_user).post("/api/pipeline/outcome/",
                                     {"mapping": m.mapping_id, "outcome": "PASSED"}, format="json")
    assert r.status_code == 200
    assert r.data["application_stage_code"] == "OK_TO_PROCEED"
    assert r.data["latest_outcome_code"] == "PASSED" and r.data["is_closed"] is False


def test_outcome_endpoint_close_with_talent_pool_optin(auth_client, admin_user, hm_user, recruiter_user):
    m, _, cand = _mapping_at(ApplicationStatus.OK_TO_PROCEED, hm_user, recruiter_user, "9000006002")
    r = auth_client(admin_user).post("/api/pipeline/outcome/",
                                     {"mapping": m.mapping_id, "outcome": "REJECTED", "move_to_talent_pool": True},
                                     format="json")
    assert r.status_code == 200 and r.data["is_closed"] is True and r.data["latest_outcome_code"] == "REJECTED"
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "SAVED" and cand.active_rejection_count == 1


def test_outcome_endpoint_rejects_invalid_for_stage(auth_client, admin_user, hm_user, recruiter_user):
    m, _, _ = _mapping_at(ApplicationStatus.SHORTLISTED, hm_user, recruiter_user, "9000006003")
    r = auth_client(admin_user).post("/api/pipeline/outcome/",
                                     {"mapping": m.mapping_id, "outcome": "PASSED"}, format="json")
    assert r.status_code == 400


def test_advance_and_reschedule_endpoints_enforce_future(auth_client, admin_user, hm_user, recruiter_user):
    import datetime as dt
    from django.utils import timezone
    m, _, _ = _mapping_at(ApplicationStatus.JD_EMAIL_SENT, hm_user, recruiter_user, "9000006004")
    future = (timezone.now() + dt.timedelta(days=2)).isoformat()
    r = auth_client(admin_user).post("/api/pipeline/advance/",
                                     {"mapping": m.mapping_id, "action": "SCHEDULE_SCREENING",
                                      "screening_datetime": future}, format="json")
    assert r.status_code == 200 and r.data["application_stage_code"] == "SCREENING_SCHEDULED"
    past = (timezone.now() - dt.timedelta(days=1)).isoformat()
    r2 = auth_client(admin_user).post("/api/pipeline/reschedule/",
                                      {"mapping": m.mapping_id, "scheduled_at": past}, format="json")
    assert r2.status_code == 400


def test_mapping_timeline_endpoint(auth_client, admin_user, hm_user, recruiter_user):
    m, _, _ = _mapping_at(ApplicationStatus.SCREENING_SCHEDULED, hm_user, recruiter_user, "9000006005")
    auth_client(admin_user).post("/api/pipeline/outcome/",
                                 {"mapping": m.mapping_id, "outcome": "PASSED"}, format="json")
    r = auth_client(admin_user).get(f"/api/pipeline/mappings/{m.mapping_id}/timeline/")
    assert r.status_code == 200
    assert isinstance(r.data["timeline"], list) and len(r.data["timeline"]) >= 1
