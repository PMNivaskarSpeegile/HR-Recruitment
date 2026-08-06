import datetime
import re

import pytest

from admin_module.models import CandidateSkill, ClientMaster, ReqTypeMaster, SkillMaster
from candidates.services import CREATED, POSSIBLE_DUPLICATE, UPDATED, next_cv_serial, upsert_candidate
from requirements.services import create_requirement

pytestmark = pytest.mark.django_db


def _data(mobile, email):
    return {"candidate_name": "Test Cand", "mobile": mobile, "email": email,
            "is_willing_to_relocate": False}


def test_cv_serial_format():
    assert re.match(r"^CV-\d{6}$", next_cv_serial())


def test_candidate_skill_filter_ands_multiple_skills(auth_client, admin_user, recruiter_user):
    """?skill= (repeatable) filters candidates by skill; multiple skills are AND-ed
    (candidate must have ALL of them). Restores skill-based finding as a dedicated
    filter after free-text search stopped covering skills."""
    two = list(SkillMaster.objects.all()[:2])
    s1, s2 = two[0].skill_id, two[1].skill_id
    both = upsert_candidate(data=_data("9000009501", "both501@example.com"),
                            user=recruiter_user, extra_skill_ids=[s1, s2])["candidate"]
    one = upsert_candidate(data=_data("9000009502", "one502@example.com"),
                           user=recruiter_user, extra_skill_ids=[s1])["candidate"]
    client = auth_client(admin_user)

    # Single skill → both candidates (each has s1).
    ids1 = {r["cv_id"] for r in client.get(
        "/api/candidates/", {"skill": s1, "page_size": 100}).data["results"]}
    assert both.cv_id in ids1 and one.cv_id in ids1

    # Both skills → only the candidate having BOTH.
    ids2 = {r["cv_id"] for r in client.get(
        "/api/candidates/", {"skill": [s1, s2], "page_size": 100}).data["results"]}
    assert both.cv_id in ids2
    assert one.cv_id not in ids2


def test_duplicate_matrix(recruiter_user):
    mobile = "9000000123"
    r1 = upsert_candidate(data=_data(mobile, "a@example.com"), user=recruiter_user)
    assert r1["action"] == CREATED
    assert r1["candidate"].candidate_status.status_code == "NEW_CV"

    r2 = upsert_candidate(data=_data(mobile, "a@example.com"), user=recruiter_user)
    assert r2["action"] == UPDATED

    r3 = upsert_candidate(data=_data(mobile, "different@example.com"), user=recruiter_user)
    assert r3["action"] == POSSIBLE_DUPLICATE


def test_candidate_detail_endpoint(auth_client, recruiter_user):
    """The drawer endpoint returns the composite payload built from existing
    models, including a timeline with the 'Candidate added' event."""
    res = upsert_candidate(data=_data("9000000555", "detail@example.com"), user=recruiter_user)
    cand = res["candidate"]
    client = auth_client(recruiter_user)
    r = client.get(f"/api/candidates/{cand.cv_id}/detail/")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"candidate", "resume", "requirement_history", "active_reviews", "timeline"}
    assert body["candidate"]["cv_serial"] == cand.cv_serial
    assert body["requirement_history"] == []  # not mapped yet
    assert any(e["type"] == "created" for e in body["timeline"])  # uploaded event present


def _make_review(existing, *, name, email, user, mobile=None):
    from candidates.services import record_possible_duplicate
    review, _ = record_possible_duplicate(
        existing_candidate=existing, new_candidate_name=name, new_mobile=mobile or existing.mobile,
        new_email=email, detection_reason="same mobile, different email",
        submitted_payload={}, user=user)
    return review


def test_duplicate_review_update_writes_chosen_details_to_existing(auth_client, admin_user, recruiter_user):
    """'Update existing record' (UPDATED) writes the chosen name/email onto the
    EXISTING candidate (the submitted row was never imported) and resolves it."""
    existing = upsert_candidate(data={"candidate_name": "Ravi Varma", "mobile": "9030000047",
                                      "email": "ravi.varma@rediffmail.com", "is_willing_to_relocate": False},
                                user=recruiter_user)["candidate"]
    review = _make_review(existing, name="Ravi Verma", email="ravi.varma@outlook.com", user=recruiter_user)
    resp = auth_client(admin_user).post(
        f"/api/duplicate-reviews/{review.review_id}/resolve/",
        {"resolution": "UPDATED", "name": "Ravi Verma", "mobile": "9030000047",
         "email": "ravi.varma@outlook.com"}, format="json")
    assert resp.status_code == 200
    existing.refresh_from_db()
    assert existing.candidate_name == "Ravi Verma" and existing.email == "ravi.varma@outlook.com"
    assert existing.mobile == "9030000047"  # unchanged (same on both sides)
    review.refresh_from_db()
    assert review.review_status == "RESOLVED" and review.resolution == "UPDATED"


def test_duplicate_review_legacy_merged_still_resolves(auth_client, admin_user, recruiter_user):
    """Backward-compat: the legacy MERGED resolution still applies + resolves."""
    existing = upsert_candidate(data={"candidate_name": "Old", "mobile": "9030000070", "email": "old@ex.com",
                                      "is_willing_to_relocate": False}, user=recruiter_user)["candidate"]
    review = _make_review(existing, name="Oldie", email="new@ex.com", user=recruiter_user)
    resp = auth_client(admin_user).post(
        f"/api/duplicate-reviews/{review.review_id}/resolve/",
        {"resolution": "MERGED", "email": "new@ex.com"}, format="json")
    assert resp.status_code == 200
    existing.refresh_from_db()
    assert existing.email == "new@ex.com"
    review.refresh_from_db()
    assert review.resolution == "MERGED" and review.review_status == "RESOLVED"


def test_duplicate_review_update_rejects_email_of_another_candidate(auth_client, admin_user, recruiter_user):
    """Update can't set an email that already belongs to a DIFFERENT candidate —
    clean 400, existing record untouched, review stays pending."""
    upsert_candidate(data={"candidate_name": "Owner", "mobile": "9030000050", "email": "taken@ex.com",
                           "is_willing_to_relocate": False}, user=recruiter_user)
    existing = upsert_candidate(data={"candidate_name": "Ex", "mobile": "9030000051", "email": "ex@ex.com",
                                      "is_willing_to_relocate": False}, user=recruiter_user)["candidate"]
    review = _make_review(existing, name="Ex2", email="taken@ex.com", user=recruiter_user)
    resp = auth_client(admin_user).post(
        f"/api/duplicate-reviews/{review.review_id}/resolve/",
        {"resolution": "UPDATED", "email": "taken@ex.com"}, format="json")
    assert resp.status_code == 400
    existing.refresh_from_db()
    assert existing.email == "ex@ex.com"  # unchanged
    review.refresh_from_db()
    assert review.review_status == "PENDING"  # not resolved on failure


def test_duplicate_review_ignore_keeps_existing_unchanged(auth_client, admin_user, recruiter_user):
    """'Ignore submission' (KEPT_SEPARATE) resolves without touching the existing record."""
    existing = upsert_candidate(data={"candidate_name": "Keep", "mobile": "9030000060", "email": "keep@ex.com",
                                      "is_willing_to_relocate": False}, user=recruiter_user)["candidate"]
    review = _make_review(existing, name="KeepX", email="other@ex.com", user=recruiter_user)
    resp = auth_client(admin_user).post(
        f"/api/duplicate-reviews/{review.review_id}/resolve/",
        {"resolution": "KEPT_SEPARATE"}, format="json")
    assert resp.status_code == 200
    existing.refresh_from_db()
    assert existing.candidate_name == "Keep" and existing.email == "keep@ex.com"
    review.refresh_from_db()
    assert review.resolution == "KEPT_SEPARATE" and review.review_status == "RESOLVED"


def test_set_status_marks_fake_or_blacklisted_with_reason(auth_client, recruiter_user):
    """Fake / Blacklisted are the only hand-settable statuses and each needs a
    mandatory reason, which is recorded on the timeline."""
    client = auth_client(recruiter_user)
    c1 = upsert_candidate(data=_data("9000000601", "f@example.com"), user=recruiter_user)["candidate"]
    r = client.post(f"/api/candidates/{c1.cv_id}/set-status/",
                    {"status_code": "FAKE", "reason": "proxy interview detected"}, format="json")
    assert r.status_code == 200 and r.json()["candidate"]["candidate_status_code"] == "FAKE"

    c2 = upsert_candidate(data=_data("9000000608", "b@example.com"), user=recruiter_user)["candidate"]
    r2 = client.post(f"/api/candidates/{c2.cv_id}/set-status/",
                     {"status_code": "BLACKLISTED", "reason": "policy violation"}, format="json")
    assert r2.status_code == 200 and r2.json()["candidate"]["candidate_status_code"] == "BLACKLISTED"

    # Reason is mandatory.
    c3 = upsert_candidate(data=_data("9000000609", "n@example.com"), user=recruiter_user)["candidate"]
    assert client.post(f"/api/candidates/{c3.cv_id}/set-status/",
                       {"status_code": "FAKE"}, format="json").status_code == 400

    detail = client.get(f"/api/candidates/{c1.cv_id}/detail/").json()
    assert any("proxy interview detected" in (e["detail"] or "") for e in detail["timeline"])


def test_fake_and_blacklisted_are_mutually_exclusive(auth_client, admin_user, recruiter_user):
    """Can't mark one while the other is set — an admin must remove it first."""
    cand = upsert_candidate(data=_data("9000000610", "mx@example.com"), user=recruiter_user)["candidate"]
    rec = auth_client(recruiter_user)
    assert rec.post(f"/api/candidates/{cand.cv_id}/set-status/",
                    {"status_code": "BLACKLISTED", "reason": "fraud"}, format="json").status_code == 200
    # Now try Fake → blocked (mutually exclusive).
    blocked = rec.post(f"/api/candidates/{cand.cv_id}/set-status/",
                       {"status_code": "FAKE", "reason": "x"}, format="json")
    assert blocked.status_code == 400
    assert "mutually exclusive" in str(blocked.data).lower()

    # Admin removes the Blacklisted mark → Talent Pool, then Fake can be set.
    assert auth_client(recruiter_user).post(  # recruiter CANNOT clear (admin only)
        f"/api/candidates/{cand.cv_id}/clear-status/", {}, format="json").status_code == 403
    cleared = auth_client(admin_user).post(
        f"/api/candidates/{cand.cv_id}/clear-status/", {"reason": "appeal upheld"}, format="json")
    assert cleared.status_code == 200 and cleared.data["candidate"]["candidate_status_code"] == "SAVED"
    now_fake = rec.post(f"/api/candidates/{cand.cv_id}/set-status/",
                        {"status_code": "FAKE", "reason": "confirmed fake"}, format="json")
    assert now_fake.status_code == 200 and now_fake.data["candidate"]["candidate_status_code"] == "FAKE"


def test_clear_status_only_for_fake_or_blacklisted_and_preserves_history(auth_client, admin_user, recruiter_user):
    from admin_module.models import CandidateInteraction
    cand = upsert_candidate(data=_data("9000000611", "h@example.com"), user=recruiter_user)["candidate"]
    # Not fake/blacklisted → clear rejected.
    assert auth_client(admin_user).post(
        f"/api/candidates/{cand.cv_id}/clear-status/", {}, format="json").status_code == 400
    # Mark fake, then clear; history (interactions) only grows.
    auth_client(recruiter_user).post(f"/api/candidates/{cand.cv_id}/set-status/",
                                     {"status_code": "FAKE", "reason": "fake id"}, format="json")
    before = CandidateInteraction.objects.filter(candidate=cand).count()
    auth_client(admin_user).post(f"/api/candidates/{cand.cv_id}/clear-status/", {}, format="json")
    after = CandidateInteraction.objects.filter(candidate=cand).count()
    assert after >= before + 1  # restore is appended; nothing erased


@pytest.mark.parametrize("mobile,code", [
    ("9000000602", "NEW_CV"),
    ("9000000603", "POSSIBLE_DUPLICATE"),
    ("9000000605", "SAVED"),         # Talent Pool is now system-managed
    ("9000000606", "REJECT_HOLD"),
    ("9000000607", "JOINED"),
    ("9000000604", "BOGUS"),
])
def test_set_status_rejects_system_only_codes(auth_client, recruiter_user, mobile, code):
    """Only FAKE/BLACKLISTED are manual — every system-managed status is rejected."""
    cand = upsert_candidate(data=_data(mobile, f"{mobile}@example.com"),
                            user=recruiter_user)["candidate"]
    r = auth_client(recruiter_user).post(
        f"/api/candidates/{cand.cv_id}/set-status/", {"status_code": code}, format="json")
    assert r.status_code == 400
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "NEW_CV"  # unchanged


def test_candidate_detail_requires_auth(api, recruiter_user):
    res = upsert_candidate(data=_data("9000000556", "noauth@example.com"), user=recruiter_user)
    r = api.get(f"/api/candidates/{res['candidate'].cv_id}/detail/")
    assert r.status_code in (401, 403)


def test_candidate_resume_404_when_no_file(auth_client, recruiter_user):
    """Seed/manual candidates have no résumé file on disk → 404 (UI shows the
    empty state)."""
    res = upsert_candidate(data=_data("9000000557", "noresume@example.com"), user=recruiter_user)
    r = auth_client(recruiter_user).get(f"/api/candidates/{res['candidate'].cv_id}/resume/")
    assert r.status_code == 404


def test_selecting_requirement_creates_review_tag_not_skills(recruiter_user, hm_user):
    """Selecting a requirement at creation must NOT copy the requirement's skills
    onto the candidate; it creates an explicit pre-pipeline Review association."""
    from admin_module.models import CandidateRequirementReview
    skills = list(SkillMaster.objects.all()[:3])
    req = create_requirement(validated_data={
        "client": ClientMaster.objects.first(), "req_type": ReqTypeMaster.objects.first(),
        "jd_role_name": "R", "positions_open": 1, "req_date": datetime.date(2026, 6, 21),
        "skill1": skills[0], "skill2": skills[1], "skill3": skills[2],
    }, user=hm_user)
    res = upsert_candidate(data=_data("9000000999", "c@example.com"),
                           user=recruiter_user, requirement=req)
    cand = res["candidate"]
    # No requirement skills copied.
    assert CandidateSkill.objects.filter(candidate=cand).count() == 0
    # An ACTIVE review association was created (candidate under review for the req).
    review = CandidateRequirementReview.objects.get(candidate=cand, req=req)
    assert review.status == "ACTIVE"
    # And NO jd_cv_mapping (not in the pipeline).
    from admin_module.models import JdCvMapping
    assert not JdCvMapping.objects.filter(candidate=cand, req=req).exists()


# --- Duplicate Review workflow (separate from candidate_status) ---------------

def _mk(recruiter, mobile, email):
    return upsert_candidate(data=_data(mobile, email), user=recruiter)["candidate"]


def test_duplicate_detection_returns_review_payload(auth_client, recruiter_user):
    _mk(recruiter_user, "9000000710", "orig@example.com")
    r = auth_client(recruiter_user).post(
        "/api/candidates/",
        {"candidate_name": "Dup", "mobile": "9000000710", "email": "different@example.com",
         "is_willing_to_relocate": False},
        format="json",
    )
    assert r.status_code == 409
    assert r.data["action"] == "POSSIBLE_DUPLICATE"
    assert r.data["reason"]
    assert r.data["existing_candidate"]["cv_id"]
    assert r.data["submitted"]["email"] == "different@example.com"


def test_duplicate_review_create_is_recruiter_and_admin(auth_client, admin_user, hm_user, recruiter_user):
    existing = _mk(recruiter_user, "9000000711", "a@example.com")
    body = {"existing_candidate": existing.cv_id, "new_candidate_name": "Dup Person",
            "new_mobile": "9000000711", "new_email": "b@example.com",
            "detection_reason": "Same mobile, different email"}
    # Recruiter can create
    r = auth_client(recruiter_user).post("/api/duplicate-reviews/", body, format="json")
    assert r.status_code == 201
    assert r.data["review_status"] == "PENDING" and r.data["created_by_name"]
    # Dedupe: same clash again → returns the existing PENDING review (200, same id)
    r2 = auth_client(recruiter_user).post("/api/duplicate-reviews/", body, format="json")
    assert r2.status_code == 200 and r2.data["review_id"] == r.data["review_id"]
    # HM cannot create (recruiter/admin only)
    assert auth_client(hm_user).post("/api/duplicate-reviews/", body, format="json").status_code == 403


def test_duplicate_review_list_and_resolve_are_admin_only(auth_client, admin_user, recruiter_user):
    existing = _mk(recruiter_user, "9000000712", "a@example.com")
    body = {"existing_candidate": existing.cv_id, "new_candidate_name": "D",
            "new_mobile": "9000000712", "new_email": "b@example.com", "detection_reason": "x"}
    rid = auth_client(recruiter_user).post("/api/duplicate-reviews/", body, format="json").data["review_id"]
    # Recruiter cannot list or resolve
    assert auth_client(recruiter_user).get("/api/duplicate-reviews/").status_code == 403
    assert auth_client(recruiter_user).post(
        f"/api/duplicate-reviews/{rid}/resolve/", {"resolution": "KEPT_SEPARATE"}, format="json").status_code == 403
    # Admin lists
    lst = auth_client(admin_user).get("/api/duplicate-reviews/?review_status=PENDING")
    assert lst.status_code == 200 and any(x["review_id"] == rid for x in lst.data["results"])


def test_duplicate_review_corrected_fixes_existing_candidate(auth_client, admin_user, recruiter_user):
    existing = _mk(recruiter_user, "9000000713", "typo@example.com")
    body = {"existing_candidate": existing.cv_id, "new_candidate_name": "D",
            "new_mobile": "9000000713", "new_email": "correct@example.com", "detection_reason": "x"}
    rid = auth_client(recruiter_user).post("/api/duplicate-reviews/", body, format="json").data["review_id"]
    adm = auth_client(admin_user)
    res = adm.post(f"/api/duplicate-reviews/{rid}/resolve/",
                   {"resolution": "CORRECTED", "email": "correct@example.com", "notes": "email typo"},
                   format="json")
    assert res.status_code == 200
    assert res.data["review_status"] == "RESOLVED" and res.data["resolution"] == "CORRECTED"
    assert res.data["resolved_by_name"] and res.data["resolved_on"]
    existing.refresh_from_db()
    assert existing.email == "correct@example.com"  # existing candidate corrected
    # Already resolved → cannot resolve again
    assert adm.post(f"/api/duplicate-reviews/{rid}/resolve/", {"resolution": "MERGED"}, format="json").status_code == 400


def test_duplicate_review_never_touches_candidate_status(auth_client, admin_user, recruiter_user):
    existing = _mk(recruiter_user, "9000000714", "a@example.com")
    before = existing.candidate_status.status_code
    body = {"existing_candidate": existing.cv_id, "new_candidate_name": "D",
            "new_mobile": "9000000714", "new_email": "b@example.com", "detection_reason": "x"}
    rid = auth_client(recruiter_user).post("/api/duplicate-reviews/", body, format="json").data["review_id"]
    auth_client(admin_user).post(f"/api/duplicate-reviews/{rid}/resolve/", {"resolution": "MERGED"}, format="json")
    existing.refresh_from_db()
    assert existing.candidate_status.status_code == before  # lifecycle untouched by the review process


def test_duplicate_review_end_to_end(auth_client, admin_user, hm_user, recruiter_user):
    """Full workflow exactly as the UI drives it:
    create → 409 → submit review → admin sees Pending → resolve → Resolved."""
    rec = auth_client(recruiter_user)
    adm = auth_client(admin_user)

    # 1-3. Recruiter creates the original, then a same-mobile/diff-email candidate → 409.
    rec.post("/api/candidates/", {"candidate_name": "Asha Rao", "mobile": "9000008001",
             "email": "asha@old.com", "is_willing_to_relocate": False}, format="json")
    dup = rec.post("/api/candidates/", {"candidate_name": "Asha R", "mobile": "9000008001",
                   "email": "asha@new.com", "is_willing_to_relocate": False}, format="json")
    assert dup.status_code == 409
    payload = dup.data
    assert payload["action"] == "POSSIBLE_DUPLICATE"
    assert payload["existing_candidate"]["cv_id"] and payload["submitted"]["email"] == "asha@new.com"

    # 7-9. "Submit for Admin review" → POST /duplicate-reviews/ from the 409 payload.
    created = rec.post("/api/duplicate-reviews/", {
        "existing_candidate": payload["existing_candidate"]["cv_id"],
        "new_candidate_name": payload["submitted"]["candidate_name"],
        "new_mobile": payload["submitted"]["mobile"],
        "new_email": payload["submitted"]["email"],
        "detection_reason": payload["reason"],
        "submitted_payload": payload["submitted"],
    }, format="json")
    assert created.status_code == 201
    rid = created.data["review_id"]

    # 10. Admin sees it under Pending.
    pending = adm.get("/api/duplicate-reviews/?review_status=PENDING")
    assert pending.status_code == 200
    row = next(x for x in pending.data["results"] if x["review_id"] == rid)
    assert row["review_status"] == "PENDING"
    assert row["existing_candidate_detail"]["email"] == "asha@old.com"
    assert row["new_email"] == "asha@new.com"
    assert row["created_by_name"]  # audit: who reported it

    # Admin resolves → moves to Resolved tab.
    done = adm.post(f"/api/duplicate-reviews/{rid}/resolve/", {"resolution": "KEPT_SEPARATE"}, format="json")
    assert done.status_code == 200 and done.data["review_status"] == "RESOLVED"
    assert done.data["resolved_by_name"]
    assert any(x["review_id"] == rid for x in adm.get("/api/duplicate-reviews/?review_status=RESOLVED").data["results"])

    # Permissions: HM is locked out of the whole workflow.
    assert auth_client(hm_user).get("/api/duplicate-reviews/").status_code == 403


def _xlsx(rows):
    """Build an in-memory .xlsx with the standard candidate headers + given rows."""
    import io
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["candidate_name", "mobile", "email"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    buf.name = "candidates.xlsx"
    return buf


def test_bulk_upload_persists_possible_duplicates_to_review_queue(recruiter_user):
    from admin_module.models import CandidateDuplicateReview
    from candidates.services import import_candidates_excel
    # Seed the original.
    upsert_candidate(data=_data("9000009401", "orig@ex.com"), user=recruiter_user)

    # Bulk file: one same-mobile/diff-email (possible duplicate) + one brand-new.
    report = import_candidates_excel(
        file=_xlsx([
            ["Dup Person", "9000009401", "new@ex.com"],
            ["Fresh Person", "9000009402", "fresh@ex.com"],
        ]),
        user=recruiter_user,
    )
    assert report["created"] == 1                       # the fresh row
    assert len(report["possible_duplicates"]) == 1      # still reported for feedback
    # …and now persisted to the Admin queue.
    reviews = CandidateDuplicateReview.objects.filter(
        new_mobile="9000009401", review_status="PENDING")
    assert reviews.count() == 1
    rev = reviews.first()
    assert rev.new_email == "new@ex.com"
    assert rev.submitted_payload["source"] == "bulk_upload"      # traceability
    assert rev.submitted_payload["row"] == 2 and rev.submitted_payload["batch"]
    assert rev.created_by_id == recruiter_user.user_id


def test_bulk_upload_dedupes_pending_reviews(recruiter_user):
    from admin_module.models import CandidateDuplicateReview
    from candidates.services import import_candidates_excel
    upsert_candidate(data=_data("9000009403", "orig@ex.com"), user=recruiter_user)
    for _ in range(2):  # same duplicate uploaded twice
        import_candidates_excel(
            file=_xlsx([["Dup", "9000009403", "new@ex.com"]]), user=recruiter_user)
    assert CandidateDuplicateReview.objects.filter(
        new_mobile="9000009403", new_email="new@ex.com", review_status="PENDING").count() == 1


def test_bulk_upload_does_not_create_reviews_for_created_or_updated(recruiter_user):
    from admin_module.models import CandidateDuplicateReview
    from candidates.services import import_candidates_excel
    before = CandidateDuplicateReview.objects.count()
    import_candidates_excel(file=_xlsx([
        ["New A", "9000009404", "a@ex.com"],          # CREATED
        ["New A", "9000009404", "a@ex.com"],          # same mobile+email → UPDATED
    ]), user=recruiter_user)
    assert CandidateDuplicateReview.objects.count() == before  # no reviews for created/updated


# --- Candidate Profile Verification & Update ---------------------------------

def test_verify_profile_updates_master_with_audit_and_verification(auth_client, recruiter_user):
    from admin_module.models import CandidateProfileAudit
    cand = upsert_candidate(data=_data("9000009501", "v@example.com"), user=recruiter_user)["candidate"]
    r = auth_client(recruiter_user).post(
        f"/api/candidates/{cand.cv_id}/verify-profile/",
        {"current_company": "Acme Corp", "current_designation": "Lead Dev",
         "notice_period": None, "verified": True},
        format="json",
    )
    assert r.status_code == 200, r.content
    assert set(r.data["changed_fields"]) >= {"Current Company", "Current Designation"}
    assert r.data["verified"] is True
    cand.refresh_from_db()
    assert cand.current_company == "Acme Corp" and cand.current_designation == "Lead Dev"
    assert cand.profile_verified and cand.profile_verified_by_id == recruiter_user.user_id and cand.profile_verified_on
    # Field-level audit (old/new) recorded.
    audits = CandidateProfileAudit.objects.filter(candidate=cand)
    company = audits.filter(field_name="Current Company").first()
    assert company and company.new_value == "Acme Corp" and company.source == "Recruiter Manual Update"
    assert company.changed_by_id == recruiter_user.user_id
    # Timeline entry lists the changed fields.
    detail = auth_client(recruiter_user).get(f"/api/candidates/{cand.cv_id}/detail/").json()
    assert any("profile" in (e["detail"] or "").lower() for e in detail["timeline"])


def test_verify_profile_history_is_never_overwritten(auth_client, recruiter_user):
    from admin_module.models import CandidateProfileAudit
    cand = upsert_candidate(data=_data("9000009502", "h@example.com"), user=recruiter_user)["candidate"]
    c = auth_client(recruiter_user)
    c.post(f"/api/candidates/{cand.cv_id}/verify-profile/", {"current_company": "First"}, format="json")
    c.post(f"/api/candidates/{cand.cv_id}/verify-profile/", {"current_company": "Second"}, format="json")
    rows = CandidateProfileAudit.objects.filter(candidate=cand, field_name="Current Company").order_by("audit_id")
    assert [x.new_value for x in rows] == ["First", "Second"]  # both kept, append-only


def test_verify_profile_mobile_change_conflict_creates_review_and_blocks(auth_client, recruiter_user):
    from admin_module.models import CandidateDuplicateReview
    other = upsert_candidate(data=_data("9000009600", "other@example.com"), user=recruiter_user)["candidate"]
    cand = upsert_candidate(data=_data("9000009601", "me@example.com"), user=recruiter_user)["candidate"]
    # Try to change cand's mobile to `other`'s mobile → conflict.
    r = auth_client(recruiter_user).post(
        f"/api/candidates/{cand.cv_id}/verify-profile/",
        {"mobile": "9000009600"}, format="json",
    )
    assert r.status_code == 409 and r.data["action"] == "POSSIBLE_DUPLICATE"
    cand.refresh_from_db()
    assert cand.mobile == "9000009601"  # NOT saved
    assert CandidateDuplicateReview.objects.filter(existing_candidate=other, review_status="PENDING").exists()


def test_verify_profile_is_recruiter_admin_only(auth_client, hm_user, recruiter_user):
    cand = upsert_candidate(data=_data("9000009502b", "hm@example.com"), user=recruiter_user)["candidate"]
    # Hiring Manager is read-only → 403.
    assert auth_client(hm_user).post(
        f"/api/candidates/{cand.cv_id}/verify-profile/", {"current_company": "X"}, format="json").status_code == 403


# ---------------------------------------------------------------------------
# Hiring Manager read-only candidate access (sourcing view)
# ---------------------------------------------------------------------------
def _other(role_code, exclude_pk):
    from admin_module.models import UserMaster
    return UserMaster.objects.filter(role__role_code=role_code, is_active=True).exclude(pk=exclude_pk).first()


def _req_for(hm):
    import datetime as _dt
    from requirements.services import create_requirement
    return create_requirement(validated_data={
        "client": ClientMaster.objects.first(),
        "req_type": ReqTypeMaster.objects.first(),
        "jd_role_name": "HM View Role",
        "positions_open": 2,
        "req_date": _dt.date(2026, 6, 21),
    }, user=hm)


def _map(req, cand, user):
    from pipeline.services import review_candidate
    return review_candidate(requirement=req, candidate=cand, decision="SHORTLISTED", comments="", user=user)


def _ids(client, params=""):
    r = client.get(f"/api/candidates/{params}")
    assert r.status_code == 200
    return {row["cv_id"] for row in r.json()["results"]}


def test_hm_sees_new_cv_and_talent_pool(auth_client, hm_user, recruiter_user):
    """HM's default sourcing view includes New_CV and Talent Pool candidates."""
    new_cv = upsert_candidate(data=_data("9000011001", "hmnew@example.com"), user=recruiter_user)["candidate"]
    saved = upsert_candidate(data=_data("9000011002", "hmsaved@example.com"), user=recruiter_user)["candidate"]
    # Push `saved` to Talent Pool (SAVED) via an application outcome — no HM action.
    from candidates.services import apply_application_outcome
    apply_application_outcome(candidate=saved, outcome="WITHDRAWN", user=recruiter_user)

    ids = _ids(auth_client(hm_user))
    assert new_cv.cv_id in ids
    assert saved.cv_id in ids


def test_hm_cannot_see_hidden_candidate_of_another_owner(auth_client, hm_user, recruiter_user):
    """A Fake (hidden) candidate mapped only to ANOTHER HM's requirement stays
    invisible to this HM — list AND detail (404)."""
    other_hm = _other("HM", hm_user.pk)
    theirs = _req_for(other_hm)
    cand = upsert_candidate(data=_data("9000011010", "hidden@example.com"), user=recruiter_user)["candidate"]
    _map(theirs, cand, recruiter_user)
    # Mark Fake (hidden status, not HM_VISIBLE).
    auth_client(recruiter_user).post(
        f"/api/candidates/{cand.cv_id}/set-status/", {"status_code": "FAKE", "reason": "x"}, format="json")

    hm = auth_client(hm_user)
    assert cand.cv_id not in _ids(hm)                       # hidden from the list
    assert hm.get(f"/api/candidates/{cand.cv_id}/").status_code == 404   # and by id


def test_hm_sees_hidden_candidate_mapped_to_own_requirement(auth_client, hm_user, recruiter_user):
    """A candidate at a hidden status is STILL visible to the HM (list + detail)
    when mapped to a requirement the HM owns — regardless of pipeline stage."""
    mine = _req_for(hm_user)
    cand = upsert_candidate(data=_data("9000011020", "ownmapped@example.com"), user=recruiter_user)["candidate"]
    _map(mine, cand, recruiter_user)
    auth_client(recruiter_user).post(
        f"/api/candidates/{cand.cv_id}/set-status/", {"status_code": "FAKE", "reason": "x"}, format="json")

    hm = auth_client(hm_user)
    assert cand.cv_id in _ids(hm)
    assert hm.get(f"/api/candidates/{cand.cv_id}/detail/").status_code == 200


def test_requirement_filter_shows_only_mapped_candidates(auth_client, hm_user, recruiter_user):
    """Selecting a requirement shows ONLY candidates mapped to it — it never
    auto-includes untagged New_CV / Talent Pool candidates. A hidden-status mapped
    candidate still shows (they're associated with the requirement)."""
    req_a = _req_for(hm_user)
    req_b = _req_for(hm_user)  # no mappings
    mapped_a = upsert_candidate(data=_data("9000011030", "ma@example.com"), user=recruiter_user)["candidate"]
    _map(req_a, mapped_a, recruiter_user)
    auth_client(recruiter_user).post(
        f"/api/candidates/{mapped_a.cv_id}/set-status/", {"status_code": "FAKE", "reason": "x"}, format="json")
    new_cv = upsert_candidate(data=_data("9000011031", "nc@example.com"), user=recruiter_user)["candidate"]

    hm = auth_client(hm_user)
    a_ids = _ids(hm, f"?requirement={req_a.req_id}")
    assert mapped_a.cv_id in a_ids      # mapped (even though Fake) → shown
    assert new_cv.cv_id not in a_ids    # untagged New_CV → NOT included
    assert _ids(hm, f"?requirement={req_b.req_id}") == set()  # no mappings → empty


def test_requirement_filter_inaccessible_yields_no_rows(auth_client, hm_user, recruiter_user):
    """Filtering by a requirement the user can't access returns nothing (no leak),
    even though it has mapped candidates."""
    other_hm = _other("HM", hm_user.pk)
    theirs = _req_for(other_hm)
    cand = upsert_candidate(data=_data("9000011035", "leak@example.com"), user=recruiter_user)["candidate"]
    _map(theirs, cand, recruiter_user)
    assert _ids(auth_client(hm_user), f"?requirement={theirs.req_id}") == set()


def test_requirement_filter_recruiter_scope(auth_client, hm_user, recruiter_user):
    """Recruiter can filter by a requirement ASSIGNED to them (only mapped shown);
    a requirement assigned to another recruiter yields nothing."""
    from requirements.services import assign_requirement
    mine = _req_for(hm_user)
    assign_requirement(requirement=mine, recruiter=recruiter_user, user=hm_user)
    mapped = upsert_candidate(data=_data("9000011050", "recmap@example.com"), user=recruiter_user)["candidate"]
    _map(mine, mapped, recruiter_user)
    unmapped = upsert_candidate(data=_data("9000011051", "recun@example.com"), user=recruiter_user)["candidate"]

    rec = auth_client(recruiter_user)
    ids = _ids(rec, f"?requirement={mine.req_id}")
    assert mapped.cv_id in ids and unmapped.cv_id not in ids

    other_rec = _other("REC", recruiter_user.pk)
    theirs = _req_for(hm_user)
    assign_requirement(requirement=theirs, recruiter=other_rec, user=hm_user)
    _map(theirs, upsert_candidate(data=_data("9000011052", "t@example.com"), user=recruiter_user)["candidate"], other_rec)
    assert _ids(rec, f"?requirement={theirs.req_id}") == set()


def test_requirement_filter_admin_any_and_multi_mapping(auth_client, admin_user, hm_user, recruiter_user):
    """Admin can filter by ANY requirement; a candidate mapped to several reqs
    appears under each of their requirements."""
    req1 = _req_for(hm_user)
    req2 = _req_for(hm_user)
    multi = upsert_candidate(data=_data("9000011070", "multi@example.com"), user=recruiter_user)["candidate"]
    _map(req1, multi, recruiter_user)
    _map(req2, multi, recruiter_user)
    unmapped = upsert_candidate(data=_data("9000011071", "um@example.com"), user=recruiter_user)["candidate"]

    adm = auth_client(admin_user)
    ids1 = _ids(adm, f"?requirement={req1.req_id}")
    assert multi.cv_id in ids1 and unmapped.cv_id not in ids1
    assert multi.cv_id in _ids(adm, f"?requirement={req2.req_id}")


def test_hm_cannot_tag_candidate_to_requirement(auth_client, hm_user, recruiter_user):
    """HM is locked out of the mapping/review endpoint used for tagging → 403."""
    mine = _req_for(hm_user)
    cand = upsert_candidate(data=_data("9000011040", "notag@example.com"), user=recruiter_user)["candidate"]
    r = auth_client(hm_user).post(
        "/api/pipeline/review/",
        {"requirement": mine.req_id, "candidate": cand.cv_id, "decision": "SHORTLISTED"}, format="json")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Verify & Update — the single recruiter decision (replaces standalone Review)
# ---------------------------------------------------------------------------
def _req_for_decision(hm):
    import datetime as _dt
    from requirements.services import create_requirement
    return create_requirement(validated_data={
        "client": ClientMaster.objects.first(), "req_type": ReqTypeMaster.objects.first(),
        "jd_role_name": "Decision Role", "positions_open": 1, "req_date": _dt.date(2026, 6, 21),
    }, user=hm)


def test_verify_shortlist_enters_pipeline(auth_client, hm_user, recruiter_user):
    from admin_module.models import JdCvMapping
    req = _req_for_decision(hm_user)
    cand = upsert_candidate(data=_data("9000012001", "vs@example.com"), user=recruiter_user)["candidate"]
    r = auth_client(recruiter_user).post(
        f"/api/candidates/{cand.cv_id}/verify-profile/",
        {"decision": "SHORTLIST", "requirement": req.req_id}, format="json")
    assert r.status_code == 200 and r.data["decision"]["application_stage"] == "SHORTLISTED"
    m = JdCvMapping.objects.get(req=req, candidate=cand)
    assert m.application_stage.status_code == "SHORTLISTED" and not m.is_closed
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "SAVED"


def test_verify_not_suitable_resolves_review_without_mapping(auth_client, hm_user, recruiter_user):
    from admin_module.models import CandidateRequirementReview, JdCvMapping
    req = _req_for_decision(hm_user)
    cand = upsert_candidate(data=_data("9000012002", "ns@example.com"),
                            user=recruiter_user, requirement=req)["candidate"]
    assert CandidateRequirementReview.objects.get(candidate=cand, req=req).status == "ACTIVE"
    r = auth_client(recruiter_user).post(
        f"/api/candidates/{cand.cv_id}/verify-profile/",
        {"decision": "NOT_SUITABLE", "requirement": req.req_id}, format="json")
    assert r.status_code == 200
    # Not Suitable never enters the pipeline → NO jd_cv_mapping is created.
    assert not JdCvMapping.objects.filter(candidate=cand, req=req).exists()
    # The review association is resolved as NOT_SUITABLE.
    review = CandidateRequirementReview.objects.get(candidate=cand, req=req)
    assert review.status == "RESOLVED" and review.resolution == "NOT_SUITABLE"


def test_verify_fake_sets_global_and_closes(auth_client, hm_user, recruiter_user):
    req = _req_for_decision(hm_user)
    cand = upsert_candidate(data=_data("9000012003", "fk@example.com"), user=recruiter_user)["candidate"]
    auth_client(recruiter_user).post(
        f"/api/candidates/{cand.cv_id}/verify-profile/",
        {"decision": "SHORTLIST", "requirement": req.req_id}, format="json")
    r = auth_client(recruiter_user).post(
        f"/api/candidates/{cand.cv_id}/verify-profile/",
        {"decision": "FAKE", "requirement": req.req_id, "decision_reason": "proxy"}, format="json")
    assert r.status_code == 200
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "FAKE"


def test_verify_save_to_talent_pool(auth_client, hm_user, recruiter_user):
    cand = upsert_candidate(data=_data("9000012004", "sv@example.com"), user=recruiter_user)["candidate"]
    r = auth_client(recruiter_user).post(
        f"/api/candidates/{cand.cv_id}/verify-profile/", {"decision": "SAVE"}, format="json")
    assert r.status_code == 200
    cand.refresh_from_db()
    assert cand.candidate_status.status_code == "SAVED"


def test_verify_shortlist_requires_requirement(auth_client, hm_user, recruiter_user):
    cand = upsert_candidate(data=_data("9000012005", "nr@example.com"), user=recruiter_user)["candidate"]
    r = auth_client(recruiter_user).post(
        f"/api/candidates/{cand.cv_id}/verify-profile/", {"decision": "SHORTLIST"}, format="json")
    assert r.status_code == 400
