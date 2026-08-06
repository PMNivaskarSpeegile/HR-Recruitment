import pytest

pytestmark = pytest.mark.django_db


def test_unauthenticated_is_blocked(api):
    resp = api.get("/api/requirements/")
    assert resp.status_code in (401, 403)


def test_me_requires_auth(api):
    # The startup session-verification endpoint must reject a missing token.
    assert api.get("/api/auth/me/").status_code in (401, 403)


def test_me_returns_current_user(auth_client, recruiter_user):
    resp = auth_client(recruiter_user).get("/api/auth/me/")
    assert resp.status_code == 200
    assert resp.data["username"] == recruiter_user.username
    assert resp.data["role"]["code"] == "REC"
    assert "password_hash" not in resp.data


def test_recruiter_cannot_create_requirement(auth_client, recruiter_user):
    client = auth_client(recruiter_user)
    resp = client.post("/api/requirements/", {
        "client": 1, "req_type": 1, "jd_role_name": "X",
        "positions_open": 1, "req_date": "2026-06-21",
    }, format="json")
    assert resp.status_code == 403


def test_recruiter_cannot_write_master_data(auth_client, recruiter_user):
    client = auth_client(recruiter_user)
    resp = client.post("/api/skills/", {"skill_name": "ZZTempSkill", "is_active": True}, format="json")
    assert resp.status_code == 403


def test_admin_can_write_master_data(auth_client, admin_user, a_domain_id):
    client = auth_client(admin_user)
    resp = client.post("/api/skills/",
                       {"skill_name": "ZZUniqueHardeningSkill", "domain": a_domain_id, "is_active": True},
                       format="json")
    assert resp.status_code == 201


def test_recruiter_cannot_create_location(auth_client, recruiter_user):
    client = auth_client(recruiter_user)
    resp = client.post("/api/locations/",
                       {"city": "ZZTempCity", "state": "Maharashtra", "country": "India", "is_active": True},
                       format="json")
    assert resp.status_code == 403


# --- Inline reference-data creation: Hiring Manager may CREATE skills/locations
#     (from the requirement form) but never edit or delete them. --------------- #

def test_hiring_manager_can_create_skill(auth_client, hm_user, a_domain_id):
    client = auth_client(hm_user)
    resp = client.post("/api/skills/",
                       {"skill_name": "ZZInlineHMSkill", "domain": a_domain_id, "is_active": True},
                       format="json")
    assert resp.status_code == 201


def test_skill_requires_a_domain(auth_client, hm_user):
    # Domain is mandatory — a skill must be classified under an existing domain.
    client = auth_client(hm_user)
    resp = client.post("/api/skills/", {"skill_name": "ZZNoDomainSkill", "is_active": True}, format="json")
    assert resp.status_code == 400
    assert "domain" in resp.data.get("error", resp.data)


def test_hiring_manager_can_create_location(auth_client, hm_user):
    client = auth_client(hm_user)
    resp = client.post("/api/locations/",
                       {"city": "ZZInlineHMCity", "state": "Maharashtra", "country": "India", "is_active": True},
                       format="json")
    assert resp.status_code == 201


def test_hiring_manager_cannot_edit_skill(auth_client, hm_user):
    client = auth_client(hm_user)
    resp = client.patch("/api/skills/1/", {"skill_name": "ZZRenamed"}, format="json")
    assert resp.status_code == 403


def test_hiring_manager_cannot_delete_location(auth_client, hm_user):
    client = auth_client(hm_user)
    resp = client.delete("/api/locations/1/")
    assert resp.status_code == 403


# --- Code is an auto-generated, frozen system identifier ---------------------- #

def test_code_generated_from_name_when_omitted(auth_client, admin_user):
    client = auth_client(admin_user)
    resp = client.post(
        "/api/req-status/",
        {"status_name": "Screening Scheduled Test", "is_active": True},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["status_code"] == "SCREENING_SCHEDULED_TEST"


def test_supplied_code_is_honored_on_create(auth_client, admin_user):
    # The admin may edit the auto-generated code once, during creation.
    client = auth_client(admin_user)
    resp = client.post(
        "/api/req-status/",
        {"status_name": "CTC Is Too High", "status_code": "CTC_HIGH", "is_active": True},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["status_code"] == "CTC_HIGH"


def test_invalid_code_is_rejected_on_create(auth_client, admin_user):
    client = auth_client(admin_user)
    resp = client.post(
        "/api/req-status/",
        {"status_name": "Bad Code Case", "status_code": "123_BAD", "is_active": True},
        format="json",
    )
    assert resp.status_code == 400  # must start with a letter


def test_code_is_frozen_when_name_is_edited(auth_client, admin_user):
    client = auth_client(admin_user)
    created = client.post(
        "/api/req-status/",
        {"status_name": "Screening Scheduled Frozen", "is_active": True},
        format="json",
    )
    assert created.status_code == 201
    sid = created.data["status_id"]
    original_code = created.data["status_code"]
    assert original_code == "SCREENING_SCHEDULED_FROZEN"

    edited = client.patch(
        f"/api/req-status/{sid}/",
        {"status_name": "Initial Screening Scheduled Frozen", "status_code": "CHANGED"},
        format="json",
    )
    assert edited.status_code == 200
    assert edited.data["status_name"] == "Initial Screening Scheduled Frozen"
    assert edited.data["status_code"] == original_code  # code never changes


def test_generated_code_is_made_unique(auth_client, admin_user):
    client = auth_client(admin_user)
    a = client.post("/api/req-status/", {"status_name": "Dup Code Case"}, format="json")
    b = client.post("/api/req-status/", {"status_name": "Dup  Code   Case"}, format="json")  # same slug
    assert a.status_code == 201
    # Second one is a name duplicate (case/space-insensitive) → rejected before a
    # colliding code can be created.
    assert b.status_code == 400


def test_client_code_auto_generated_from_name_and_frozen(auth_client, admin_user):
    # Client Master follows the same Code lifecycle as the other masters.
    client = auth_client(admin_user)
    created = client.post("/api/clients/", {"client_name": "Zeta Global Services"}, format="json")
    assert created.status_code == 201
    assert created.data["client_code"] == "ZETA_GLOBAL_SERVICES"
    cid = created.data["client_id"]
    edited = client.patch(
        f"/api/clients/{cid}/",
        {"client_name": "Zeta Global Solutions", "client_code": "ZGS"},
        format="json",
    )
    assert edited.status_code == 200
    assert edited.data["client_code"] == "ZETA_GLOBAL_SERVICES"  # frozen


def test_client_code_one_time_edit_on_create(auth_client, admin_user):
    client = auth_client(admin_user)
    resp = client.post(
        "/api/clients/",
        {"client_name": "Omega Retail Limited", "client_code": "OMEGA"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["client_code"] == "OMEGA"


# --- Domains: controlled classification data — Admin-only writes; HM read-only;
#     a domain referenced by skills can only be deactivated, not hard-deleted. -- #

def test_any_authenticated_user_can_read_domains(auth_client, hm_user):
    resp = auth_client(hm_user).get("/api/domains/")
    assert resp.status_code == 200


def test_hiring_manager_cannot_create_domain(auth_client, hm_user):
    resp = auth_client(hm_user).post("/api/domains/", {"domain_name": "ZZ HM Domain", "is_active": True}, format="json")
    assert resp.status_code == 403


def test_hiring_manager_cannot_edit_domain(auth_client, hm_user):
    resp = auth_client(hm_user).patch("/api/domains/1/", {"domain_name": "ZZ Renamed"}, format="json")
    assert resp.status_code == 403


def test_admin_can_create_domain_normalised(auth_client, admin_user):
    resp = auth_client(admin_user).post(
        "/api/domains/", {"domain_name": "  data &   analytics ", "is_active": True}, format="json")
    assert resp.status_code == 201
    # Trimmed/collapsed + Title-cased via the shared master rules.
    assert resp.data["domain_name"] == "Data & Analytics"


def test_domain_in_use_cannot_be_permanently_deleted(auth_client, admin_user, a_domain_id):
    # a_domain_id is referenced by seeded skills → permanent delete blocked (409).
    resp = auth_client(admin_user).delete(f"/api/domains/{a_domain_id}/permanent/")
    assert resp.status_code == 409
    assert resp.data["code"] == "referenced"


# --- Validation parity: the inline (HM) create path runs the SAME normalisation
#     + duplicate rules as the Master Data module (single source of truth). ----- #

def test_inline_created_skill_is_normalised(auth_client, hm_user, a_domain_id):
    client = auth_client(hm_user)
    resp = client.post("/api/skills/",
                       {"skill_name": "  go   lang ", "domain": a_domain_id, "is_active": True}, format="json")
    assert resp.status_code == 201
    # Whitespace collapsed/trimmed + Title-cased exactly as the master would store it.
    assert resp.data["skill_name"] == "Go Lang"


def test_inline_skill_duplicate_is_rejected(auth_client, hm_user, a_domain_id):
    client = auth_client(hm_user)
    first = client.post("/api/skills/",
                        {"skill_name": "ZZ Dedupe Skill", "domain": a_domain_id, "is_active": True}, format="json")
    assert first.status_code == 201
    # Same name, different case/spacing → case-/space-insensitive duplicate → 400.
    dup = client.post("/api/skills/",
                      {"skill_name": "  zz   dedupe   skill ", "domain": a_domain_id, "is_active": True}, format="json")
    assert dup.status_code == 400


def test_user_list_hides_password_hash(auth_client, admin_user):
    client = auth_client(admin_user)
    resp = client.get("/api/users/")
    assert resp.status_code == 200
    rows = resp.data["results"] if isinstance(resp.data, dict) and "results" in resp.data else resp.data
    assert all("password_hash" not in row for row in rows)


# The user directory is staff PII — only Admins may read it (regression: it was
# inheriting the read-open reference-data policy).
def test_recruiter_cannot_list_users(auth_client, recruiter_user):
    assert auth_client(recruiter_user).get("/api/users/").status_code == 403


def test_hiring_manager_cannot_list_users(auth_client, hm_user):
    assert auth_client(hm_user).get("/api/users/").status_code == 403


def _user_payload(**over):
    from admin_module.models import RoleMaster
    base = {
        "username": "zz.pwtest", "full_name": "PW Test", "email": "zz.pwtest@example.com",
        "mobile": "9000000771", "role": RoleMaster.objects.first().role_id,
    }
    base.update(over)
    return base


def test_weak_password_rejected_on_user_create(auth_client, admin_user):
    """AUTH_PASSWORD_VALIDATORS are enforced on user create (regression: they
    were configured but never called, so any weak password was accepted)."""
    resp = auth_client(admin_user).post("/api/users/", _user_payload(password="1"), format="json")
    assert resp.status_code == 400
    body = resp.data.get("error", resp.data)
    assert "password" in body


def test_strong_password_accepted_on_user_create(auth_client, admin_user):
    resp = auth_client(admin_user).post(
        "/api/users/",
        _user_payload(username="zz.strongpw", email="zz.strongpw@example.com",
                      mobile="9000000772", password="Str0ng!Phrase42"),
        format="json",
    )
    assert resp.status_code in (200, 201)
