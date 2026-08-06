import datetime

import pytest
from django.utils import timezone

from admin_module.models import (
    ApplicationStatusMaster,
    ClientMaster,
    JdCvMapping,
    ReqTypeMaster,
    Screening,
    ScreeningModeMaster,
    SkillMaster,
)
from candidates.services import upsert_candidate
from core.constants import ApplicationStatus, ScreeningOutcome
from core.timeutils import to_local_naive
from pipeline.screening import (
    ScreeningError,
    complete_screening,
    reschedule_screening_round,
    schedule_screening,
)
from pipeline.services import transition_mappings
from requirements.services import create_requirement

pytestmark = pytest.mark.django_db


def _mapping(hm, rec, mobile, app_status="SCREENING_SCHEDULED"):
    skills = list(SkillMaster.objects.all()[:3])
    req = create_requirement(validated_data={
        "client": ClientMaster.objects.first(), "req_type": ReqTypeMaster.objects.first(),
        "jd_role_name": "R", "positions_open": 1, "req_date": datetime.date(2026, 6, 21),
        "skill1": skills[0], "skill2": skills[1], "skill3": skills[2],
    }, user=hm)
    cand = upsert_candidate(
        data={"candidate_name": "C", "mobile": mobile, "email": f"{mobile}@e.com", "is_willing_to_relocate": False},
        user=rec,
    )["candidate"]
    st = ApplicationStatusMaster.objects.get(status_code=app_status)
    return JdCvMapping.objects.create(req=req, candidate=cand, application_stage=st, is_active=True), req


def _tel():
    return ScreeningModeMaster.objects.get(mode_code="TELEPHONIC")


def _vid():
    return ScreeningModeMaster.objects.get(mode_code="VIDEO")


def _utc(**delta):
    """An aware UTC instant offset from now — mirrors what the API delivers
    (the client sends `Date.toISOString()`)."""
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(**delta)


def test_video_requires_passed_telephonic_when_telephonic_active(hm_user, recruiter_user):
    # The telephonic→video gate applies only while the Telephonic mode is active.
    tel = _tel()
    tel.is_active = True
    tel.save(update_fields=["is_active"])
    m, _ = _mapping(hm_user, recruiter_user, "9000003000")
    with pytest.raises(ScreeningError):
        schedule_screening(mapping=m, mode=_vid(), scheduled_at=_utc(days=1), interviewer="X", notes="", user=recruiter_user)


def test_video_schedules_directly_when_telephonic_inactive(hm_user, recruiter_user):
    # Current single-round process: Telephonic is retired, so a Video screening
    # can be scheduled directly with no telephonic prerequisite.
    tel = _tel()
    tel.is_active = False
    tel.save(update_fields=["is_active"])
    m, _ = _mapping(hm_user, recruiter_user, "9000003012")
    s = schedule_screening(mapping=m, mode=_vid(), scheduled_at=_utc(days=1), interviewer="X", notes="", user=recruiter_user)
    assert s.screening_id
    # Regression: scheduling mirrors the mode + time onto the mapping so the
    # pipeline board's "Screening" column shows the type (Video), not a blank.
    m.refresh_from_db()
    assert m.screening_mode_id == _vid().screening_mode_id
    assert m.screening_datetime is not None


def test_schedule_accepts_near_future_utc_time(hm_user, recruiter_user):
    # Regression: the client sends an aware UTC instant (Date.toISOString()).
    # A time only 30 min ahead has a UTC wall-clock BEHIND the server's local
    # wall-clock; it must still be accepted (was wrongly rejected as "past").
    m, _ = _mapping(hm_user, recruiter_user, "9000003013")
    target = _utc(minutes=30)
    s = schedule_screening(mapping=m, mode=_vid(), scheduled_at=target,
                           interviewer="X", notes="", user=recruiter_user)
    assert s.screening_id
    # Stored as naive local wall-clock, matching the intended instant.
    assert abs((s.scheduled_at - to_local_naive(target)).total_seconds()) < 1


def test_sequential_flow_and_no_concurrent_open(hm_user, recruiter_user):
    m, _ = _mapping(hm_user, recruiter_user, "9000003001")
    s1 = schedule_screening(mapping=m, mode=_tel(), scheduled_at=_utc(days=1), interviewer="A", notes="", user=recruiter_user)
    # A second round can't be scheduled while one is still open.
    with pytest.raises(ScreeningError):
        schedule_screening(mapping=m, mode=_tel(), scheduled_at=_utc(days=1), interviewer="A", notes="", user=recruiter_user)
    complete_screening(screening=s1, outcome=ScreeningOutcome.PASSED, notes="ok", user=recruiter_user)
    s2 = schedule_screening(mapping=m, mode=_vid(), scheduled_at=_utc(days=1), interviewer="B", notes="", user=recruiter_user)
    assert s2.screening_mode.mode_code == "VIDEO"


def test_repeat_telephonic_only_on_reschedule(hm_user, recruiter_user):
    m, _ = _mapping(hm_user, recruiter_user, "9000003002")
    s1 = schedule_screening(mapping=m, mode=_tel(), scheduled_at=_utc(days=1), interviewer="A", notes="", user=recruiter_user)
    complete_screening(screening=s1, outcome=ScreeningOutcome.FAILED, notes="", user=recruiter_user)
    with pytest.raises(ScreeningError):  # failed → no repeat telephonic
        schedule_screening(mapping=m, mode=_tel(), scheduled_at=_utc(days=1), interviewer="A", notes="", user=recruiter_user)

    m2, _ = _mapping(hm_user, recruiter_user, "9000003003")
    t1 = schedule_screening(mapping=m2, mode=_tel(), scheduled_at=_utc(days=1), interviewer="A", notes="", user=recruiter_user)
    complete_screening(screening=t1, outcome=ScreeningOutcome.RESCHEDULE_REQUIRED, notes="", user=recruiter_user)
    t2 = schedule_screening(mapping=m2, mode=_tel(), scheduled_at=_utc(days=1), interviewer="A", notes="", user=recruiter_user)
    assert t2.screening_id  # reschedule → repeat telephonic allowed


def test_rejected_application_blocks_screening(hm_user, recruiter_user):
    m, _ = _mapping(hm_user, recruiter_user, "9000003004", app_status="REJECTED")
    with pytest.raises(ScreeningError):
        schedule_screening(mapping=m, mode=_tel(), scheduled_at=_utc(days=1), interviewer="A", notes="", user=recruiter_user)


def test_ok_to_proceed_outcome_advances_from_screening(hm_user, recruiter_user):
    # New model: recording the "OK to Proceed" outcome at the Screening Scheduled
    # stage IS the pass — it advances the application directly (no separate
    # screening-round gate). The screening-rounds module still tracks meetings.
    m, req = _mapping(hm_user, recruiter_user, "9000003005")
    rep = transition_mappings(requirement=req, mapping_ids=[m.mapping_id],
                              to_status=ApplicationStatus.OK_TO_PROCEED,
                              comments="", screening_datetime=None, user=recruiter_user)
    assert rep["updated"] == 1 and not rep["invalid"]
    m.refresh_from_db()
    assert m.application_stage.status_code == "OK_TO_PROCEED"
    assert m.latest_outcome.status_code == "PASSED"


def test_passing_screening_advances_to_ok_to_proceed(hm_user, recruiter_user):
    # The board's Screening-Scheduled menu has no manual "OK to Proceed"; passing
    # the interview in the Screenings tab is what advances the application.
    m, _ = _mapping(hm_user, recruiter_user, "9000003014")  # starts SCREENING_SCHEDULED
    s = schedule_screening(mapping=m, mode=_vid(), scheduled_at=_utc(days=1), interviewer="X", notes="", user=recruiter_user)
    complete_screening(screening=s, outcome=ScreeningOutcome.PASSED, notes="", user=recruiter_user)
    m.refresh_from_db()
    assert m.application_stage.status_code == "OK_TO_PROCEED"
    assert m.latest_outcome.status_code == "PASSED"


def test_failing_screening_does_not_advance(hm_user, recruiter_user):
    m, _ = _mapping(hm_user, recruiter_user, "9000003015")
    s = schedule_screening(mapping=m, mode=_vid(), scheduled_at=_utc(days=1), interviewer="X", notes="", user=recruiter_user)
    complete_screening(screening=s, outcome=ScreeningOutcome.FAILED, notes="", user=recruiter_user)
    m.refresh_from_db()
    assert m.application_stage.status_code == "SCREENING_SCHEDULED"  # recruiter closes via the Outcome menu


def test_screening_added_to_activity_timeline(hm_user, recruiter_user):
    from admin_module.models import CandidateInteraction
    m, _ = _mapping(hm_user, recruiter_user, "9000003006")
    schedule_screening(mapping=m, mode=_tel(), scheduled_at=_utc(days=1), interviewer="A", notes="", user=recruiter_user)
    assert CandidateInteraction.objects.filter(candidate=m.candidate, req=m.req).exists()


def test_cannot_schedule_screening_in_the_past(hm_user, recruiter_user):
    m, _ = _mapping(hm_user, recruiter_user, "9000003007")
    with pytest.raises(ScreeningError):
        schedule_screening(mapping=m, mode=_tel(), scheduled_at=_utc(minutes=-1),
                           interviewer="A", notes="", user=recruiter_user)


def test_reschedule_scheduled_round_to_future(hm_user, recruiter_user):
    m, _ = _mapping(hm_user, recruiter_user, "9000003008")
    s = schedule_screening(mapping=m, mode=_tel(), scheduled_at=_utc(days=1),
                           interviewer="A", notes="", user=recruiter_user)
    new_dt = _utc(days=3)
    reschedule_screening_round(screening=s, new_datetime=new_dt, user=recruiter_user)
    s.refresh_from_db()
    assert abs((s.scheduled_at - to_local_naive(new_dt)).total_seconds()) < 1


def test_reschedule_rejects_past_datetime(hm_user, recruiter_user):
    m, _ = _mapping(hm_user, recruiter_user, "9000003009")
    s = schedule_screening(mapping=m, mode=_tel(), scheduled_at=_utc(days=1),
                           interviewer="A", notes="", user=recruiter_user)
    with pytest.raises(ScreeningError):
        reschedule_screening_round(screening=s, new_datetime=_utc(minutes=-1),
                                   user=recruiter_user)


def test_reschedule_rejects_completed_round(hm_user, recruiter_user):
    m, _ = _mapping(hm_user, recruiter_user, "9000003010")
    s = schedule_screening(mapping=m, mode=_tel(), scheduled_at=_utc(days=1),
                           interviewer="A", notes="", user=recruiter_user)
    complete_screening(screening=s, outcome=ScreeningOutcome.PASSED, notes="", user=recruiter_user)
    with pytest.raises(ScreeningError):
        reschedule_screening_round(screening=s, new_datetime=timezone.now() + datetime.timedelta(days=2),
                                   user=recruiter_user)


def test_interviewer_required_alpha_only_and_titlecased():
    """Schedule serializer: interviewer is mandatory, letters/spaces only, stored
    Title Case (no DB needed — field validator)."""
    from rest_framework import serializers as drf
    from pipeline.serializers import ScreeningScheduleInputSerializer
    ser = ScreeningScheduleInputSerializer()
    assert ser.validate_interviewer("  rajeev   mehta ") == "Rajeev Mehta"
    assert ser.validate_interviewer("PRIYA sharma") == "Priya Sharma"
    for bad in ("", "   ", "rajeev123", "john.doe", "a@b"):
        with pytest.raises(drf.ValidationError):
            ser.validate_interviewer(bad)
