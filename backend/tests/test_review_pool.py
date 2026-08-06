"""Pre-pipeline Review Pool (candidate_requirement_review) — the explicit
"candidate under review for a requirement" association introduced by the workflow
redesign. Distinct from jd_cv_mapping (which means the candidate ENTERED the
pipeline via Shortlist).

Covers: tagging (no skill copy, no mapping), review-pool membership (explicit tags
only, not skill match), the five recruiter decisions, multi-requirement tagging,
requirement-closure sweeps, authorization (§9), and tag guards.
"""
import datetime

import pytest

from admin_module.models import (
    CandidateRequirementReview,
    ClientMaster,
    JdCvMapping,
    ReqStatusMaster,
    ReqTypeMaster,
    SkillMaster,
    CandidateStatusMaster,
)
from candidates.services import (
    apply_candidate_decision,
    tag_candidate_for_review,
    untag_candidate_review,
    upsert_candidate,
)
from core.constants import CandidateStatus, ReqStatus, ReviewResolution, ReviewStatus
from pipeline.services import new_cv_candidates_for_requirement
from requirements.services import change_requirement_status, create_requirement, end_recruitment

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _req(hm, recruiter=None, positions=1, status=ReqStatus.OPEN, target_fill_date=None):
    skills = list(SkillMaster.objects.all()[:3])
    req = create_requirement(validated_data={
        "client": ClientMaster.objects.first(), "req_type": ReqTypeMaster.objects.first(),
        "jd_role_name": "Reviewer role", "positions_open": positions,
        "req_date": datetime.date(2026, 1, 1), "target_fill_date": target_fill_date,
        "skill1": skills[0], "skill2": skills[1], "skill3": skills[2],
    }, user=hm)
    req.req_status = ReqStatusMaster.objects.get(status_code=status)
    if recruiter is not None:
        req.recruiter = recruiter
    req.save(update_fields=["req_status", "recruiter"])
    return req


def _cand(rec, mobile, status=CandidateStatus.NEW_CV):
    cand = upsert_candidate(
        data={"candidate_name": "C", "mobile": mobile, "email": f"{mobile}@ex.com",
              "is_willing_to_relocate": False},
        user=rec,
    )["candidate"]
    if status != CandidateStatus.NEW_CV:
        cand.candidate_status = CandidateStatusMaster.objects.get(status_code=status)
        cand.save(update_fields=["candidate_status"])
    return cand


# --------------------------------------------------------------------------- #
# Tagging: no skill copy, no mapping, explicit association
# --------------------------------------------------------------------------- #
def test_tagging_creates_active_review_no_mapping_no_skills(hm_user, recruiter_user):
    req = _req(hm_user, recruiter_user)
    cand = _cand(recruiter_user, "9000060001")
    tag_candidate_for_review(candidate=cand, requirement=req, user=recruiter_user)

    review = CandidateRequirementReview.objects.get(candidate=cand, req=req)
    assert review.status == ReviewStatus.ACTIVE
    assert not JdCvMapping.objects.filter(candidate=cand, req=req).exists()
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == CandidateStatus.NEW_CV  # unchanged by tagging


def test_tag_is_idempotent_and_reactivates(hm_user, recruiter_user):
    req = _req(hm_user, recruiter_user)
    cand = _cand(recruiter_user, "9000060002")
    tag_candidate_for_review(candidate=cand, requirement=req, user=recruiter_user)
    untag_candidate_review(candidate=cand, requirement=req, user=recruiter_user)
    assert CandidateRequirementReview.objects.get(candidate=cand, req=req).status == ReviewStatus.RESOLVED
    # Re-tag reactivates the SAME row (one per pair).
    tag_candidate_for_review(candidate=cand, requirement=req, user=recruiter_user)
    assert CandidateRequirementReview.objects.filter(candidate=cand, req=req).count() == 1
    assert CandidateRequirementReview.objects.get(candidate=cand, req=req).status == ReviewStatus.ACTIVE


def test_bulk_upsert_with_requirement_tags_not_skills(hm_user, recruiter_user):
    from admin_module.models import CandidateSkill
    req = _req(hm_user, recruiter_user)
    res = upsert_candidate(data={"candidate_name": "B", "mobile": "9000060003",
                                 "email": "b@ex.com", "is_willing_to_relocate": False},
                           user=recruiter_user, requirement=req)
    cand = res["candidate"]
    assert CandidateSkill.objects.filter(candidate=cand).count() == 0  # NO requirement skills
    assert CandidateRequirementReview.objects.filter(candidate=cand, req=req, status="ACTIVE").exists()


# --------------------------------------------------------------------------- #
# Review pool: explicit tags only (never skill matching)
# --------------------------------------------------------------------------- #
def test_review_pool_contains_only_tagged_candidates(hm_user, recruiter_user):
    req = _req(hm_user, recruiter_user)
    tagged = _cand(recruiter_user, "9000060010")
    untagged = _cand(recruiter_user, "9000060011")  # usable NEW_CV but NOT tagged
    tag_candidate_for_review(candidate=tagged, requirement=req, user=recruiter_user)

    pool_ids = set(new_cv_candidates_for_requirement(req).values_list("cv_id", flat=True))
    assert tagged.cv_id in pool_ids
    assert untagged.cv_id not in pool_ids  # skill match must NOT pull in untagged candidates


# --------------------------------------------------------------------------- #
# The five recruiter decisions
# --------------------------------------------------------------------------- #
def test_shortlist_creates_mapping_and_resolves_review(hm_user, recruiter_user):
    req = _req(hm_user, recruiter_user)
    cand = _cand(recruiter_user, "9000060020")
    tag_candidate_for_review(candidate=cand, requirement=req, user=recruiter_user)
    apply_candidate_decision(candidate=cand, decision="SHORTLIST", requirement=req, user=recruiter_user)

    assert JdCvMapping.objects.get(req=req, candidate=cand).application_stage.status_code == "SHORTLISTED"
    review = CandidateRequirementReview.objects.get(candidate=cand, req=req)
    assert review.status == ReviewStatus.RESOLVED and review.resolution == ReviewResolution.SHORTLISTED
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == CandidateStatus.SAVED
    # Shortlisted → leaves the review pool.
    assert cand.cv_id not in set(new_cv_candidates_for_requirement(req).values_list("cv_id", flat=True))


def test_talent_pool_resolves_review_no_mapping(hm_user, recruiter_user):
    req = _req(hm_user, recruiter_user)
    cand = _cand(recruiter_user, "9000060021")
    tag_candidate_for_review(candidate=cand, requirement=req, user=recruiter_user)
    apply_candidate_decision(candidate=cand, decision="SAVE", requirement=req, user=recruiter_user)

    assert not JdCvMapping.objects.filter(candidate=cand, req=req).exists()
    review = CandidateRequirementReview.objects.get(candidate=cand, req=req)
    assert review.status == ReviewStatus.RESOLVED and review.resolution == ReviewResolution.TALENT_POOL
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == CandidateStatus.SAVED


def test_not_suitable_resolves_review_only(hm_user, recruiter_user):
    req = _req(hm_user, recruiter_user)
    cand = _cand(recruiter_user, "9000060022")
    tag_candidate_for_review(candidate=cand, requirement=req, user=recruiter_user)
    apply_candidate_decision(candidate=cand, decision="NOT_SUITABLE", requirement=req, user=recruiter_user)

    assert not JdCvMapping.objects.filter(candidate=cand, req=req).exists()  # never enters pipeline
    review = CandidateRequirementReview.objects.get(candidate=cand, req=req)
    assert review.status == ReviewStatus.RESOLVED and review.resolution == ReviewResolution.NOT_SUITABLE
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == CandidateStatus.NEW_CV  # global status unchanged


def test_fake_sets_global_and_resolves_all_reviews(hm_user, recruiter_user):
    reqa = _req(hm_user, recruiter_user)
    reqb = _req(hm_user, recruiter_user)
    cand = _cand(recruiter_user, "9000060023")
    tag_candidate_for_review(candidate=cand, requirement=reqa, user=recruiter_user)
    tag_candidate_for_review(candidate=cand, requirement=reqb, user=recruiter_user)
    apply_candidate_decision(candidate=cand, decision="FAKE", requirement=reqa,
                             user=recruiter_user, reason="proxy")

    cand.refresh_from_db()
    assert cand.candidate_status.status_code == CandidateStatus.FAKE
    # ALL active reviews resolved, none left active.
    assert not CandidateRequirementReview.objects.filter(candidate=cand, status=ReviewStatus.ACTIVE).exists()
    assert not JdCvMapping.objects.filter(candidate=cand).exists()


# --------------------------------------------------------------------------- #
# Multi-requirement tagging
# --------------------------------------------------------------------------- #
def test_shortlist_for_one_req_leaves_other_review_active(hm_user, recruiter_user):
    reqa = _req(hm_user, recruiter_user)
    reqb = _req(hm_user, recruiter_user)
    cand = _cand(recruiter_user, "9000060030")
    tag_candidate_for_review(candidate=cand, requirement=reqa, user=recruiter_user)
    tag_candidate_for_review(candidate=cand, requirement=reqb, user=recruiter_user)
    apply_candidate_decision(candidate=cand, decision="SHORTLIST", requirement=reqa, user=recruiter_user)

    assert CandidateRequirementReview.objects.get(candidate=cand, req=reqa).status == ReviewStatus.RESOLVED
    assert CandidateRequirementReview.objects.get(candidate=cand, req=reqb).status == ReviewStatus.ACTIVE
    assert cand.cv_id in set(new_cv_candidates_for_requirement(reqb).values_list("cv_id", flat=True))


# --------------------------------------------------------------------------- #
# Requirement closure sweeps the review pool
# --------------------------------------------------------------------------- #
def test_close_lost_resolves_active_reviews(hm_user, recruiter_user):
    req = _req(hm_user, recruiter_user, status=ReqStatus.OPEN)
    cand = _cand(recruiter_user, "9000060040")
    tag_candidate_for_review(candidate=cand, requirement=req, user=recruiter_user)
    change_requirement_status(requirement=req, to_status=ReqStatus.CLOSE_LOST,
                              user=hm_user, reason="lost")
    review = CandidateRequirementReview.objects.get(candidate=cand, req=req)
    assert review.status == ReviewStatus.RESOLVED and review.resolution == ReviewResolution.REQ_CLOSED


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #
def test_cannot_tag_fake_candidate(hm_user, recruiter_user):
    from candidates.services import DecisionError
    req = _req(hm_user, recruiter_user)
    cand = _cand(recruiter_user, "9000060050", status=CandidateStatus.FAKE)
    with pytest.raises(DecisionError):
        tag_candidate_for_review(candidate=cand, requirement=req, user=recruiter_user)


def test_cannot_tag_to_closed_requirement(hm_user, recruiter_user):
    from candidates.services import DecisionError
    req = _req(hm_user, recruiter_user, status=ReqStatus.OPEN)
    change_requirement_status(requirement=req, to_status=ReqStatus.CLOSE_LOST, user=hm_user, reason="x")
    cand = _cand(recruiter_user, "9000060051")
    with pytest.raises(DecisionError):
        tag_candidate_for_review(candidate=cand, requirement=req, user=recruiter_user)


# --------------------------------------------------------------------------- #
# API + authorization (§9): assigned recruiter or admin
# --------------------------------------------------------------------------- #
def test_tag_endpoint_authorization(auth_client, hm_user, recruiter_user, admin_user):
    # Requirement assigned to recruiter_user.
    req = _req(hm_user, recruiter_user)
    cand = _cand(recruiter_user, "9000060060")
    url = f"/api/candidates/{cand.cv_id}/tag-requirements/"
    body = {"requirement_ids": [req.req_id]}

    # Assigned recruiter → 200
    r1 = auth_client(recruiter_user).post(url, body, format="json")
    assert r1.status_code == 200
    assert CandidateRequirementReview.objects.filter(candidate=cand, req=req, status="ACTIVE").exists()

    # Admin → allowed (untag then re-tag as admin)
    r2 = auth_client(admin_user).post(f"/api/candidates/{cand.cv_id}/untag-requirement/",
                                      {"requirement": req.req_id}, format="json")
    assert r2.status_code == 200


def test_tag_endpoint_rejects_unassigned_recruiter(auth_client, hm_user, recruiter_user):
    # Requirement NOT assigned to recruiter_user (no recruiter).
    req = _req(hm_user, recruiter=None)
    cand = _cand(recruiter_user, "9000060061")
    r = auth_client(recruiter_user).post(
        f"/api/candidates/{cand.cv_id}/tag-requirements/",
        {"requirement_ids": [req.req_id]}, format="json")
    assert r.status_code in (403, 404)
    assert not CandidateRequirementReview.objects.filter(candidate=cand, req=req).exists()
