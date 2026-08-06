import pytest

pytestmark = pytest.mark.django_db


def test_admin_dashboard_is_business_level(auth_client, admin_user):
    resp = auth_client(admin_user).get("/api/dashboard/")
    assert resp.status_code == 200
    d = resp.data
    assert d["role"] == "ADM"

    kpi_keys = {k["key"] for k in d["kpis"]}
    assert kpi_keys == {
        "active_requirements", "total_positions", "total_filled_positions",
        "open_positions", "in_pipeline", "candidates_available", "joined_this_month",
        "active_recruiters", "active_clients",
    }

    # High-level monitoring sections present (incl. the full pipeline flow)…
    for key in ("requirement_status", "pipeline_stages", "recruiter_workload", "top_clients",
                "admin_tasks", "stalled_requirements", "recent_requirements", "recent_activity"):
        assert key in d, key

    # Pipeline chart matches the board: starts at Shortlisted (no "New"), no outcomes.
    assert [s["status"] for s in d["pipeline_stages"]] == [
        "Shortlisted", "JD Email Sent", "Screening Scheduled", "OK to Proceed",
        "Offer Released", "Awaiting Joining",
    ]
    # Possible-duplicate review is an admin task with a deep-link key.
    assert any(t["key"] == "possible_duplicate_review" for t in d["admin_tasks"])

    # …and per-candidate operational detail is NOT on the admin dashboard.
    assert "recent_candidates" not in d


def test_admin_recent_requirements_are_enriched(auth_client, admin_user):
    resp = auth_client(admin_user).get("/api/dashboard/")
    rows = resp.data["recent_requirements"]
    if rows:  # seeded data present
        r = rows[0]
        for field in ("client_name", "recruiter_name", "positions_required",
                      "positions_filled", "positions_open"):
            assert field in r


def test_recruiter_dashboard_still_operational(auth_client, recruiter_user):
    resp = auth_client(recruiter_user).get("/api/dashboard/")
    assert resp.status_code == 200
    assert resp.data["role"] == "REC"
    # Recruiters keep their operational pipeline view (now the full ordered flow).
    assert "pipeline_stages" in resp.data
    kpi_keys = {k["key"] for k in resp.data["kpis"]}
    assert {"total_positions", "total_filled_positions", "candidates_available"} <= kpi_keys


def test_dashboard_position_kpis_are_role_scoped(auth_client, admin_user, hm_user, recruiter_user):
    """Total/Filled positions respect role scope: admin >= HM/recruiter subsets."""
    def totals(u):
        k = {x["key"]: x["value"] for x in auth_client(u).get("/api/dashboard/").data["kpis"]}
        return k["total_positions"], k["total_filled_positions"]
    a_total, a_filled = totals(admin_user)
    h_total, _ = totals(hm_user)
    r_total, _ = totals(recruiter_user)
    assert a_total >= h_total and a_total >= r_total  # admin sees org-wide superset
    assert a_filled >= 0


def test_recruiter_candidates_available_is_review_pool_not_uploads(auth_client, hm_user, recruiter_user, admin_user):
    """'Candidates Available' for a recruiter counts candidates under active review
    for THEIR requirements — not candidates they merely uploaded. Admin sees the
    whole recruitable database."""
    from admin_module.models import ClientMaster, ReqTypeMaster, SkillMaster
    from requirements.services import assign_requirement, create_requirement
    from candidates.services import tag_candidate_for_review, upsert_candidate

    def avail(u):
        kpis = {k["key"]: k["value"] for k in auth_client(u).get("/api/dashboard/").data["kpis"]}
        return kpis["candidates_available"]

    skills = list(SkillMaster.objects.all()[:3])
    req = create_requirement(validated_data={
        "client": ClientMaster.objects.first(), "req_type": ReqTypeMaster.objects.first(),
        "jd_role_name": "Dash Role", "positions_open": 1,
        "skill1": skills[0], "skill2": skills[1], "skill3": skills[2],
    }, user=hm_user)
    assign_requirement(requirement=req, recruiter=recruiter_user, user=hm_user)

    before = avail(recruiter_user)
    # Uploaded by the recruiter but NOT tagged to a requirement → must NOT count.
    cand = upsert_candidate(data={"candidate_name": "Pool Test", "mobile": "9000009410",
                                  "email": "pool410@ex.com", "is_willing_to_relocate": False},
                            user=recruiter_user)["candidate"]
    assert avail(recruiter_user) == before
    # Now under review for the recruiter's requirement → counts.
    tag_candidate_for_review(candidate=cand, requirement=req, user=recruiter_user)
    assert avail(recruiter_user) == before + 1
    # Admin sees the whole recruitable DB (superset of any recruiter's scoped view).
    assert avail(admin_user) >= avail(recruiter_user)


def test_recruiter_candidate_widget_excludes_hidden(auth_client, recruiter_user):
    """The recruiter candidate-upload widget shows only recruitable candidates."""
    from admin_module.models import CandidateStatusMaster
    from candidates.services import upsert_candidate
    c = upsert_candidate(data={"candidate_name": "Hidden One", "mobile": "9000009301",
                               "email": "h301@ex.com", "is_willing_to_relocate": False},
                         user=recruiter_user)["candidate"]
    c.candidate_status = CandidateStatusMaster.objects.get(status_code="BLACKLISTED")
    c.save(update_fields=["candidate_status"])
    rows = auth_client(recruiter_user).get("/api/dashboard/").data["recent_candidates"]
    assert all(r["status"] != "Blacklisted" for r in rows)
    assert c.cv_serial not in {r["cv_serial"] for r in rows}
