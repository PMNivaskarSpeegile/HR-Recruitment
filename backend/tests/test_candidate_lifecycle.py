"""Candidate lifecycle automation: Reject-Hold, Joined retention, visibility."""
import pytest

from admin_module.models import CandidateInteraction, CandidateStatusMaster
from candidates.services import (
    _add_months,
    apply_application_outcome,
    run_lifecycle_maintenance,
    upsert_candidate,
)

pytestmark = pytest.mark.django_db


def _cand(rec, mobile, email="x@example.com"):
    return upsert_candidate(
        data={"candidate_name": "C", "mobile": mobile, "email": f"{mobile}@ex.com",
              "is_willing_to_relocate": False},
        user=rec,
    )["candidate"]


def _set_status(cand, code):
    cand.candidate_status = CandidateStatusMaster.objects.get(status_code=code)
    cand.save(update_fields=["candidate_status"])
    return cand


def _reject(cand, user, move_to_talent_pool=False):
    apply_application_outcome(candidate=cand, outcome="REJECTED", user=user,
                              move_to_talent_pool=move_to_talent_pool)
    cand.refresh_from_db()


# --- Application outcome automation ------------------------------------------

def test_first_rejection_talent_pool_is_opt_in(recruiter_user):
    # Talent Pool is now an explicit recruiter decision. A first rejection counts
    # but does NOT move to Talent Pool unless the recruiter chose it.
    cand = _cand(recruiter_user, "9000009001")
    _reject(cand, recruiter_user)  # no opt-in
    assert cand.active_rejection_count == 1
    assert cand.candidate_status.status_code != "SAVED"
    assert cand.reject_hold_until is None
    # With the recruiter's opt-in → Talent Pool.
    cand2 = _cand(recruiter_user, "9000009011")
    _reject(cand2, recruiter_user, move_to_talent_pool=True)
    assert cand2.active_rejection_count == 1 and cand2.candidate_status.status_code == "SAVED"


def test_second_rejection_goes_on_reject_hold(recruiter_user):
    from datetime import date
    cand = _cand(recruiter_user, "9000009002")
    _reject(cand, recruiter_user)
    _reject(cand, recruiter_user)
    assert cand.active_rejection_count == 2
    assert cand.candidate_status.status_code == "REJECT_HOLD"
    assert cand.reject_hold_start == date.today()
    assert cand.reject_hold_until == _add_months(date.today(), 6)


def test_dropped_talent_pool_is_opt_in_no_count(recruiter_user):
    cand = _cand(recruiter_user, "9000009003")
    apply_application_outcome(candidate=cand, outcome="DROPPED", user=recruiter_user)  # no opt-in
    cand.refresh_from_db()
    assert cand.candidate_status.status_code != "SAVED" and cand.active_rejection_count == 0
    apply_application_outcome(candidate=cand, outcome="DROPPED", user=recruiter_user, move_to_talent_pool=True)
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "SAVED" and cand.active_rejection_count == 0


def test_withdrawn_talent_pool_is_opt_in(recruiter_user):
    cand = _cand(recruiter_user, "9000009004")
    apply_application_outcome(candidate=cand, outcome="WITHDRAWN", user=recruiter_user, move_to_talent_pool=True)
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "SAVED" and cand.active_rejection_count == 0


def test_joined_sets_joined_status_and_date(recruiter_user):
    from datetime import date
    cand = _cand(recruiter_user, "9000009005")
    apply_application_outcome(candidate=cand, outcome="JOINED", user=recruiter_user)
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "JOINED" and cand.joined_date == date.today()


def test_fake_and_blacklisted_are_not_overridden_by_outcome(recruiter_user):
    cand = _set_status(_cand(recruiter_user, "9000009006"), "BLACKLISTED")
    apply_application_outcome(candidate=cand, outcome="REJECTED", user=recruiter_user)
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "BLACKLISTED"  # hard disposition preserved
    assert cand.active_rejection_count == 0


# --- Scheduler / maintenance -------------------------------------------------

def test_reject_hold_expires_after_six_months_and_resets_counter(recruiter_user):
    cand = _cand(recruiter_user, "9000009007")
    _reject(cand, recruiter_user)
    _reject(cand, recruiter_user)
    assert cand.candidate_status.status_code == "REJECT_HOLD"
    hold_until = cand.reject_hold_until

    summary = run_lifecycle_maintenance(as_of=hold_until)  # day the hold elapses
    assert summary["reject_hold_released"] == 1
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "SAVED"       # back to Talent Pool
    assert cand.active_rejection_count == 0                    # counter reset
    assert cand.reject_hold_start is None and cand.reject_hold_until is None


def test_reject_hold_not_released_before_expiry(recruiter_user):
    from datetime import timedelta
    cand = _cand(recruiter_user, "9000009008")
    _reject(cand, recruiter_user)
    _reject(cand, recruiter_user)
    summary = run_lifecycle_maintenance(as_of=cand.reject_hold_until - timedelta(days=1))
    assert summary["reject_hold_released"] == 0
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "REJECT_HOLD"


def test_joined_returns_to_talent_pool_after_two_years(recruiter_user):
    # Isolated to the candidate this test creates: we assert on THIS candidate's
    # transition (not the global maintenance count), and drive the window off its
    # own joined_date — so the result never depends on other (seeded) joined
    # candidates such as CV-000027 or on the absolute current date.
    from datetime import timedelta
    cand = _cand(recruiter_user, "9000009009")
    apply_application_outcome(candidate=cand, outcome="JOINED", user=recruiter_user)
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "JOINED"

    # A day before the 2-year retention elapses → this candidate is NOT released.
    run_lifecycle_maintenance(as_of=_add_months(cand.joined_date, 24) - timedelta(days=1))
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "JOINED"

    # On the day the 2-year retention elapses → this candidate returns to Talent Pool.
    run_lifecycle_maintenance(as_of=_add_months(cand.joined_date, 24))
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "SAVED"


def test_history_intact_after_rejection_count_reset(recruiter_user):
    cand = _cand(recruiter_user, "9000009010")
    _reject(cand, recruiter_user)
    _reject(cand, recruiter_user)
    before = CandidateInteraction.objects.filter(candidate=cand).count()
    run_lifecycle_maintenance(as_of=cand.reject_hold_until)
    cand.refresh_from_db()
    after = CandidateInteraction.objects.filter(candidate=cand).count()
    assert cand.active_rejection_count == 0       # working counter reset
    assert after >= before + 1                    # maintenance APPENDS history, never deletes


def test_management_command_runs(recruiter_user):
    from django.core.management import call_command
    call_command("run_candidate_lifecycle")  # smoke: no candidates due → no error


# --- Candidate Database visibility (backend-enforced) ------------------------

def _visible_ids(resp):
    return {c["cv_id"] for c in resp.data["results"]}


def test_recruiter_default_hides_lifecycle_statuses(auth_client, recruiter_user):
    saved = _set_status(_cand(recruiter_user, "9000009101"), "SAVED")
    hold = _set_status(_cand(recruiter_user, "9000009102"), "REJECT_HOLD")
    joined = _set_status(_cand(recruiter_user, "9000009103"), "JOINED")
    fake = _set_status(_cand(recruiter_user, "9000009104"), "FAKE")
    ids = _visible_ids(auth_client(recruiter_user).get("/api/candidates/"))
    assert saved.cv_id in ids
    assert hold.cv_id not in ids and joined.cv_id not in ids and fake.cv_id not in ids


def test_recruiter_all_candidates_overrides_default(auth_client, recruiter_user):
    hold = _set_status(_cand(recruiter_user, "9000009105"), "REJECT_HOLD")
    ids = _visible_ids(auth_client(recruiter_user).get("/api/candidates/?status=ALL"))
    assert hold.cv_id in ids
    # and a specific status filter works too
    only = auth_client(recruiter_user).get("/api/candidates/?status=REJECT_HOLD")
    assert all(c["candidate_status_code"] == "REJECT_HOLD" for c in only.data["results"])


def test_hiring_manager_only_sees_newcv_and_talent_pool(auth_client, hm_user, recruiter_user):
    saved = _set_status(_cand(recruiter_user, "9000009106"), "SAVED")
    hold = _set_status(_cand(recruiter_user, "9000009107"), "REJECT_HOLD")
    joined = _set_status(_cand(recruiter_user, "9000009108"), "JOINED")
    resp = auth_client(hm_user).get("/api/candidates/")
    ids, codes = _visible_ids(resp), {c["candidate_status_code"] for c in resp.data["results"]}
    assert saved.cv_id in ids
    assert hold.cv_id not in ids and joined.cv_id not in ids
    assert codes <= {"NEW_CV", "SAVED"}
    # HM cannot override with ?status=ALL — still restricted.
    ids_all = _visible_ids(auth_client(hm_user).get("/api/candidates/?status=ALL"))
    assert hold.cv_id not in ids_all and joined.cv_id not in ids_all
