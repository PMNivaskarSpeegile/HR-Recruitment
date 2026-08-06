"""Requirement-closure cascade: when a requirement reaches an irreversible
terminal state (Close Filled / Close Lost) or an expired partially-filled
requirement ends recruitment, every remaining ACTIVE application is auto-closed
with a system (non-rejection) outcome and its candidate returns to the Talent
Pool. Terminal applications and reversible Cancel are left untouched.
"""
import datetime

import pytest

from admin_module.models import (
    ApplicationStatusMaster,
    CandidateStatusMaster,
    ClientMaster,
    JdCvMapping,
    ReqStatusMaster,
    ReqTypeMaster,
    RequirementPosition,
    SkillMaster,
    StatusChangeHistory,
)
from candidates.services import upsert_candidate
from core.constants import ApplicationStatus as A
from core.constants import AuditEntity, CandidateStatus, ChangeType, ReqStatus
from pipeline.services import close_remaining_applications, record_outcome
from requirements.services import (
    RequirementStatusError,
    change_requirement_status,
    end_recruitment,
)

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _req(hm, positions=1, target_fill_date=None, status=ReqStatus.OPEN):
    skills = list(SkillMaster.objects.all()[:3])
    req = _create(hm, positions, target_fill_date)
    req.req_status = ReqStatusMaster.objects.get(status_code=status)
    req.save(update_fields=["req_status"])
    return req


def _create(hm, positions, target_fill_date):
    from requirements.services import create_requirement
    skills = list(SkillMaster.objects.all()[:3])
    return create_requirement(validated_data={
        "client": ClientMaster.objects.first(), "req_type": ReqTypeMaster.objects.first(),
        "jd_role_name": "Closure Role", "positions_open": positions,
        "req_date": datetime.date(2026, 1, 1), "target_fill_date": target_fill_date,
        "skill1": skills[0], "skill2": skills[1], "skill3": skills[2],
    }, user=hm)


def _cand(rec, mobile, status=CandidateStatus.SAVED):
    cand = upsert_candidate(
        data={"candidate_name": "C", "mobile": mobile, "email": f"{mobile}@example.com",
              "is_willing_to_relocate": False},
        user=rec,
    )["candidate"]
    cand.candidate_status = CandidateStatusMaster.objects.get(status_code=status)
    cand.save(update_fields=["candidate_status"])
    return cand


def _map(req, cand, stage_code, *, closed_outcome=None):
    """Create a mapping at a stage; optionally pre-close it with an outcome."""
    stage = ApplicationStatusMaster.objects.get(status_code=stage_code)
    m = JdCvMapping.objects.create(req=req, candidate=cand, application_stage=stage, is_active=True)
    if closed_outcome:
        m.latest_outcome = ApplicationStatusMaster.objects.get(status_code=closed_outcome)
        m.is_closed = True
        m.save(update_fields=["latest_outcome", "is_closed"])
    return m


# --------------------------------------------------------------------------- #
# Close Lost (manual, irreversible)
# --------------------------------------------------------------------------- #
def test_close_lost_frees_active_applications_to_talent_pool(hm_user, recruiter_user):
    req = _req(hm_user, positions=1)
    active1 = _map(req, _cand(recruiter_user, "9000050001"), A.SHORTLISTED)
    active2 = _map(req, _cand(recruiter_user, "9000050002"), A.SCREENING_SCHEDULED)
    # An already-terminal application must be left exactly as it is.
    closed = _map(req, _cand(recruiter_user, "9000050003"), A.SCREENING_SCHEDULED,
                  closed_outcome=A.REJECTED)

    change_requirement_status(requirement=req, to_status=ReqStatus.CLOSE_LOST,
                              user=hm_user, reason="Budget cut")

    for m in (active1, active2):
        m.refresh_from_db()
        assert m.is_closed is True
        assert m.latest_outcome.status_code == A.REQ_CLOSE_LOST
        assert m.closed_on is not None and m.closed_by_id == hm_user.user_id
        m.candidate.refresh_from_db()
        assert m.candidate.candidate_status.status_code == CandidateStatus.SAVED

    closed.refresh_from_db()
    assert closed.latest_outcome.status_code == A.REJECTED  # untouched

    req.refresh_from_db()
    assert req.req_status.status_code == ReqStatus.CLOSE_LOST


def test_close_lost_writes_auto_audit_row(hm_user, recruiter_user):
    req = _req(hm_user, positions=1)
    m = _map(req, _cand(recruiter_user, "9000050010"), A.SHORTLISTED)
    change_requirement_status(requirement=req, to_status=ReqStatus.CLOSE_LOST,
                              user=hm_user, reason="Lost")
    row = StatusChangeHistory.objects.filter(
        entity_type=AuditEntity.APPLICATION, entity_id=m.mapping_id,
        new_status=A.REQ_CLOSE_LOST,
    ).first()
    assert row is not None and row.change_type == ChangeType.AUTO


# --------------------------------------------------------------------------- #
# Close Filled (automatic rollup on the final join)
# --------------------------------------------------------------------------- #
def test_close_filled_on_join_frees_others_but_not_the_winner(hm_user, recruiter_user):
    req = _req(hm_user, positions=1, status=ReqStatus.OPEN)
    winner = _map(req, _cand(recruiter_user, "9000050101"), A.AWAITING_JOINING)
    other = _map(req, _cand(recruiter_user, "9000050102"), A.SHORTLISTED)

    record_outcome(mapping=winner, outcome=A.JOINED, user=recruiter_user)

    req.refresh_from_db()
    assert req.req_status.status_code == ReqStatus.CLOSE_FILLED

    winner.refresh_from_db()
    assert winner.latest_outcome.status_code == A.JOINED  # NOT clobbered
    winner.candidate.refresh_from_db()
    assert winner.candidate.candidate_status.status_code == CandidateStatus.JOINED

    other.refresh_from_db()
    assert other.is_closed is True
    assert other.latest_outcome.status_code == A.REQ_CLOSE_FILLED
    other.candidate.refresh_from_db()
    assert other.candidate.candidate_status.status_code == CandidateStatus.SAVED


# --------------------------------------------------------------------------- #
# End Recruitment (expired + partially filled; no status change)
# --------------------------------------------------------------------------- #
def _partially_filled_expired(hm_user, recruiter_user, base_mobile):
    """2-seat requirement with one candidate joined (→ PARTIAL_FILLED), then
    expired by back-dating the target fill date. Returns (req, remaining_mapping)."""
    req = _req(hm_user, positions=2, status=ReqStatus.OPEN)
    winner = _map(req, _cand(recruiter_user, base_mobile + "1"), A.AWAITING_JOINING)
    record_outcome(mapping=winner, outcome=A.JOINED, user=recruiter_user)
    req.refresh_from_db()
    assert req.req_status.status_code == ReqStatus.PARTIAL_FILLED
    remaining = _map(req, _cand(recruiter_user, base_mobile + "2"), A.SHORTLISTED)
    req.target_fill_date = datetime.date(2020, 1, 1)  # in the past → Expired overlay
    req.save(update_fields=["target_fill_date"])
    return req, remaining


def test_end_recruitment_withdraws_seats_closes_apps_keeps_partial_filled(hm_user, recruiter_user):
    req, remaining = _partially_filled_expired(hm_user, recruiter_user, "900005020")

    result = end_recruitment(requirement=req, user=hm_user, reason="No budget for the rest")
    assert result["closed"] == 1

    # Remaining application closed to the Talent Pool with the business outcome.
    remaining.refresh_from_db()
    assert remaining.is_closed is True
    assert remaining.latest_outcome.status_code == A.REQ_POSITIONS_WITHDRAWN
    assert remaining.closed_by_id == hm_user.user_id
    remaining.candidate.refresh_from_db()
    assert remaining.candidate.candidate_status.status_code == CandidateStatus.SAVED

    req.refresh_from_db()
    # Decision persisted on the requirement (the source of truth for the freeze).
    assert req.recruitment_ended is True
    assert req.recruitment_ended_on is not None
    assert req.recruitment_ended_by_id == hm_user.user_id
    # Status stays PARTIAL_FILLED — the flag froze the rollup despite the seat change.
    assert req.req_status.status_code == ReqStatus.PARTIAL_FILLED
    # Filled seat preserved; the remaining open seat withdrawn to Inactive.
    assert RequirementPosition.objects.filter(
        req=req, position_status__status_code="FILLED").count() == 1
    inactive = RequirementPosition.objects.filter(
        req=req, position_status__status_code="INACTIVE")
    assert inactive.count() == 1
    assert inactive.first().status_source == "AUTO_END_RECRUITMENT"


def test_end_recruitment_is_permanent_across_date_extension(hm_user, recruiter_user):
    req, _ = _partially_filled_expired(hm_user, recruiter_user, "900005040")
    end_recruitment(requirement=req, user=hm_user)
    # Extending the target date clears Expired, but the decision is permanent.
    req.target_fill_date = datetime.date(2035, 1, 1)
    req.save(update_fields=["target_fill_date"])
    req.refresh_from_db()
    from requirements.services import requirement_is_expired
    assert requirement_is_expired(req) is False   # no longer expired
    assert req.recruitment_ended is True           # still ended
    assert req.req_status.status_code == ReqStatus.PARTIAL_FILLED


def test_end_recruitment_requires_expired(hm_user, recruiter_user):
    # Precondition per spec: available only once the requirement has expired.
    req = _req(hm_user, positions=2, status=ReqStatus.OPEN)  # not expired
    winner = _map(req, _cand(recruiter_user, "9000005251"), A.AWAITING_JOINING)
    record_outcome(mapping=winner, outcome=A.JOINED, user=recruiter_user)
    req.refresh_from_db()
    assert req.req_status.status_code == ReqStatus.PARTIAL_FILLED
    with pytest.raises(RequirementStatusError):
        end_recruitment(requirement=req, user=hm_user)


def test_end_recruitment_requires_partial_filled(hm_user, recruiter_user):
    req = _req(hm_user, positions=1, status=ReqStatus.OPEN,
               target_fill_date=datetime.date(2020, 1, 1))  # expired but not partial
    with pytest.raises(RequirementStatusError):
        end_recruitment(requirement=req, user=hm_user)


def test_end_recruitment_is_idempotent(hm_user, recruiter_user):
    req, _ = _partially_filled_expired(hm_user, recruiter_user, "900005030")
    first = end_recruitment(requirement=req, user=hm_user)
    second = end_recruitment(requirement=req, user=hm_user)  # already ended → no-op
    assert first["closed"] == 1
    assert second["closed"] == 0 and second.get("already_ended") is True


# --------------------------------------------------------------------------- #
# Guards: Cancel is reversible (no cascade); protective states preserved
# --------------------------------------------------------------------------- #
def test_cancel_does_not_close_applications(hm_user, recruiter_user):
    req = _req(hm_user, positions=1, status=ReqStatus.OPEN)
    m = _map(req, _cand(recruiter_user, "9000050401"), A.SHORTLISTED)
    change_requirement_status(requirement=req, to_status=ReqStatus.CANCELLED,
                              user=hm_user, reason="Paused")
    m.refresh_from_db()
    assert m.is_closed is False  # reopenable → pipeline preserved
    assert m.latest_outcome is None


def test_closure_does_not_release_active_reject_hold(hm_user, recruiter_user):
    req = _req(hm_user, positions=1, status=ReqStatus.OPEN)
    held = _cand(recruiter_user, "9000050501", status=CandidateStatus.REJECT_HOLD)
    m = _map(req, held, A.SHORTLISTED)
    change_requirement_status(requirement=req, to_status=ReqStatus.CLOSE_LOST,
                              user=hm_user, reason="Lost")
    m.refresh_from_db()
    assert m.is_closed is True and m.latest_outcome.status_code == A.REQ_CLOSE_LOST
    held.refresh_from_db()
    assert held.candidate_status.status_code == CandidateStatus.REJECT_HOLD  # hold preserved


def test_close_remaining_applications_returns_count(hm_user, recruiter_user):
    req = _req(hm_user, positions=1, status=ReqStatus.OPEN)
    _map(req, _cand(recruiter_user, "9000050601"), A.SHORTLISTED)
    _map(req, _cand(recruiter_user, "9000050602"), A.OK_TO_PROCEED)
    n = close_remaining_applications(requirement=req, outcome=A.REQ_CLOSE_LOST, user=hm_user)
    assert n == 2


# --------------------------------------------------------------------------- #
# API / permissions
# --------------------------------------------------------------------------- #
def test_end_recruitment_endpoint_is_hm_only(auth_client, hm_user, recruiter_user, admin_user):
    req, _ = _partially_filled_expired(hm_user, recruiter_user, "900005070")
    url = f"/api/requirements/{req.req_id}/end-recruitment/"
    # Non-HM is denied: Admin isn't an HM (403); a recruiter can't even see this
    # requirement in their scope (404). Both mean "not allowed".
    assert auth_client(recruiter_user).post(url, {}, format="json").status_code in (403, 404)
    assert auth_client(admin_user).post(url, {}, format="json").status_code in (403, 404)
    resp = auth_client(hm_user).post(url, {"reason": "Business decision"}, format="json")
    assert resp.status_code == 200
    assert resp.data["recruitment_ended"] is True
    assert resp.data["applications_closed"] == 1


def test_ended_requirement_is_read_only_and_irreversible(auth_client, hm_user, recruiter_user):
    req, _ = _partially_filled_expired(hm_user, recruiter_user, "900005095")
    end_recruitment(requirement=req, user=hm_user)
    client = auth_client(hm_user)
    # No extending the target fill date (would otherwise revive an ended req).
    r1 = client.patch(f"/api/requirements/{req.req_id}/",
                      {"target_fill_date": "2035-12-31"}, format="json")
    assert r1.status_code == 400
    # No status change (the decision is final).
    r2 = client.post(f"/api/requirements/{req.req_id}/set-status/",
                     {"to_status": "CLOSE_LOST", "reason": "x"}, format="json")
    assert r2.status_code == 400
    req.refresh_from_db()
    assert req.recruitment_ended is True
    assert req.req_status.status_code == ReqStatus.PARTIAL_FILLED


def test_pipeline_entry_blocked_after_end_recruitment(auth_client, hm_user, recruiter_user, admin_user):
    req, _ = _partially_filled_expired(hm_user, recruiter_user, "900005080")
    end_recruitment(requirement=req, user=hm_user)
    fresh = _cand(recruiter_user, "9000005089", status=CandidateStatus.NEW_CV)
    # Admin bypasses the assignment check but is still stopped by the ended guard.
    resp = auth_client(admin_user).post(
        "/api/pipeline/review/",
        {"requirement": req.req_id, "candidate": fresh.cv_id, "decision": "SHORTLISTED"},
        format="json",
    )
    assert resp.status_code == 400
