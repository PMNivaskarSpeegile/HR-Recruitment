"""Database reset → seeded demo baseline (dev/test utility).

Verifies the reset restores the initial-state baseline defined by the finalized
workflow: requirements Open, positions Open, candidates New-CV, explicit
review-pool tags, and NO pipeline/workflow data — with master data preserved and
the operation idempotent.
"""
import pytest

from admin_module.models import (
    ActivityLog,
    CandidateInteraction,
    CandidateMaster,
    CandidateRequirementReview,
    ClientMaster,
    CommunicationLog,
    JdCvMapping,
    RequirementPosition,
    RequirementTracker,
    Screening,
    SkillMaster,
    StatusChangeHistory,
    UserMaster,
)
from admin_module.services.demo_reset import clear_transactional_data, reset_to_baseline
from core.constants import CandidateStatus, PositionStatus, ReqStatus, ReviewStatus

pytestmark = pytest.mark.django_db


def test_reset_produces_initial_state_baseline(admin_user):
    summary = reset_to_baseline(admin_user)
    assert summary["requirements"] > 0
    assert summary["candidates"] > 0
    assert summary["review_tags"] > 0

    # Requirements Open; positions Open (0 filled).
    assert RequirementTracker.objects.exists()
    assert RequirementTracker.objects.exclude(req_status__status_code=ReqStatus.OPEN).count() == 0
    assert RequirementPosition.objects.exclude(position_status__status_code=PositionStatus.OPEN).count() == 0

    # Every candidate is New CV (nobody processed yet).
    assert CandidateMaster.objects.exists()
    assert CandidateMaster.objects.exclude(candidate_status__status_code=CandidateStatus.NEW_CV).count() == 0

    # Explicit review-pool tags exist and are all ACTIVE.
    assert CandidateRequirementReview.objects.count() == summary["review_tags"]
    assert CandidateRequirementReview.objects.exclude(status=ReviewStatus.ACTIVE).count() == 0

    # NO pipeline entry and NO workflow-generated data.
    assert JdCvMapping.objects.count() == 0
    assert Screening.objects.count() == 0
    assert ActivityLog.objects.count() == 0
    assert StatusChangeHistory.objects.count() == 0
    assert CommunicationLog.objects.count() == 0
    assert CandidateInteraction.objects.count() == 0


def test_reset_candidates_have_own_skills_and_are_tagged(admin_user):
    reset_to_baseline(admin_user)
    cand = CandidateMaster.objects.first()
    # Real skills exist on the candidate profile (from their domain, not a requirement).
    assert cand.candidateskill_set.count() > 0
    # Each tagged candidate is under review for a requirement, without a mapping.
    review = CandidateRequirementReview.objects.filter(status=ReviewStatus.ACTIVE).first()
    assert review is not None
    assert not JdCvMapping.objects.filter(candidate_id=review.candidate_id, req_id=review.req_id).exists()


def test_reset_preserves_master_and_demo_login_entities(admin_user):
    reset_to_baseline(admin_user)
    assert UserMaster.objects.filter(username="priya.sharma").exists()   # demo admin login
    assert UserMaster.objects.filter(username="rajeev.mehta").exists()   # demo recruiter login
    assert ClientMaster.objects.exists()
    assert SkillMaster.objects.exists()


def test_reset_is_idempotent(admin_user):
    s1 = reset_to_baseline(admin_user)
    s2 = reset_to_baseline(admin_user)
    assert s1 == s2  # same baseline counts, no duplication
    assert RequirementTracker.objects.count() == s2["requirements"]
    assert CandidateMaster.objects.count() == s2["candidates"]
    assert CandidateRequirementReview.objects.count() == s2["review_tags"]


def test_clear_transactional_empties_tables_but_keeps_masters(admin_user):
    reset_to_baseline(admin_user)
    assert CandidateMaster.objects.exists() and RequirementTracker.objects.exists()
    clear_transactional_data()
    assert not CandidateMaster.objects.exists()
    assert not RequirementTracker.objects.exists()
    assert not CandidateRequirementReview.objects.exists()
    assert not RequirementPosition.objects.exists()
    # Masters preserved.
    assert ClientMaster.objects.exists()
    assert UserMaster.objects.exists()
    assert SkillMaster.objects.exists()
