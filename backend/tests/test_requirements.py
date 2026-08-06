import datetime
import re

import pytest

from admin_module.models import ClientMaster, ReqTypeMaster
from requirements.services import assign_requirement, create_requirement, generate_identifiers

pytestmark = pytest.mark.django_db


def _req_data():
    return {
        "client": ClientMaster.objects.first(),
        "req_type": ReqTypeMaster.objects.first(),
        "jd_role_name": "Test Role",
        "positions_open": 2,
        "req_date": datetime.date(2026, 6, 21),
    }


def test_generate_identifiers_format():
    req_no, jd = generate_identifiers(2026, 7)
    assert req_no == "REQ-2026-007"
    assert jd == "JD-2026-00007"


def test_assign_recruiter_to_newly_created_requirement(auth_client, admin_user, hm_user, recruiter_user):
    """Regression: assigning a recruiter to a freshly created requirement must not
    fail the chk_dates constraint (req_date is the system creation date — today —
    not a future 'Required by' value)."""
    from admin_module.models import SkillMaster
    skills = list(SkillMaster.objects.all()[:3])
    created = auth_client(hm_user).post("/api/requirements/", {
        "client": ClientMaster.objects.first().client_id,
        "req_type": ReqTypeMaster.objects.first().req_type_id,
        "jd_role_name": "Assignable Role", "positions_open": 1,
        "target_fill_date": "2026-12-24",  # future deadline is fine — it's target close
        "skill1": skills[0].skill_id, "skill2": skills[1].skill_id, "skill3": skills[2].skill_id,
    }, format="json")
    assert created.status_code == 201
    req_id = created.data["req_id"]

    r = auth_client(admin_user).post(
        f"/api/requirements/{req_id}/assign/", {"recruiter": recruiter_user.user_id}, format="json")
    assert r.status_code == 200
    assert r.data["recruiter"] == recruiter_user.user_id


def test_create_requirement_auto_numbers(hm_user):
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    assert re.match(r"^REQ-\d{4}-\d{3}$", req.req_tracker_no)
    assert re.match(r"^JD-\d{4}-\d{5}$", req.jd_serial_number)
    assert req.req_status.status_code == "NEW"
    assert req.is_active is True
    # A Hiring Manager creating a requirement owns it by default.
    assert req.hiring_mgr_id == hm_user.user_id


def test_required_by_maps_to_target_close_not_created(auth_client, hm_user):
    """Regression: 'Required by' must populate target_fill_date (Target Close), NOT
    req_date (Created). 'Created' is the system created_on timestamp and is never
    driven by user input; editing Required by changes only the target close."""
    from admin_module.models import ClientMaster, ReqTypeMaster, SkillMaster
    skills = list(SkillMaster.objects.all()[:3])
    payload = {
        "client": ClientMaster.objects.first().client_id,
        "req_type": ReqTypeMaster.objects.first().req_type_id,
        "jd_role_name": "Date Mapping Role",
        "positions_open": 1,
        "target_fill_date": "2026-12-24",
        "skill1": skills[0].skill_id, "skill2": skills[1].skill_id, "skill3": skills[2].skill_id,
    }
    r = auth_client(hm_user).post("/api/requirements/", payload, format="json")
    assert r.status_code == 201
    # Required by → Target Close.
    assert r.data["target_fill_date"] == "2026-12-24"
    # Created is a system timestamp, present and NOT the user's Required-by date.
    assert r.data["created_on"] is not None
    assert r.data["req_date"] != "2026-12-24"

    # Editing Required by updates only the target close; Created never changes.
    # (Compare DB-persisted values from GET on both sides — the create RESPONSE
    # carries the un-rounded in-memory created_on, but the column is timestamp(0).)
    req_id = r.data["req_id"]
    before = auth_client(hm_user).get(f"/api/requirements/{req_id}/").data
    r2 = auth_client(hm_user).patch(
        f"/api/requirements/{req_id}/", {"target_fill_date": "2027-01-15"}, format="json")
    assert r2.status_code == 200
    after = auth_client(hm_user).get(f"/api/requirements/{req_id}/").data
    assert after["target_fill_date"] == "2027-01-15"   # only the target close moved
    assert after["created_on"] == before["created_on"]  # Created never changes
    assert after["req_date"] == before["req_date"]


# --- Role-based data visibility (RBAC) ---------------------------------------

def _other(role_code, exclude_pk):
    from admin_module.models import UserMaster
    return UserMaster.objects.filter(role__role_code=role_code, is_active=True).exclude(pk=exclude_pk).first()


def test_recruiter_sees_only_assigned_requirements(auth_client, hm_user, recruiter_user):
    other_rec = _other("REC", recruiter_user.pk)
    mine = create_requirement(validated_data=_req_data(), user=hm_user)
    theirs = create_requirement(validated_data=_req_data(), user=hm_user)
    assign_requirement(requirement=mine, recruiter=recruiter_user, user=hm_user)
    assign_requirement(requirement=theirs, recruiter=other_rec, user=hm_user)

    client = auth_client(recruiter_user)
    ids = {r["req_id"] for r in client.get("/api/requirements/").data["results"]}
    assert mine.req_id in ids            # own requirement is visible
    assert theirs.req_id not in ids      # another recruiter's is hidden from the list

    # Direct API access to another recruiter's data is blocked (404, not just hidden).
    assert client.get(f"/api/requirements/{theirs.req_id}/").status_code == 404
    assert client.get(f"/api/requirements/{theirs.req_id}/positions/").status_code == 404


def test_hm_sees_only_owned_requirements(auth_client, hm_user):
    other_hm = _other("HM", hm_user.pk)
    mine = create_requirement(validated_data=_req_data(), user=hm_user)
    theirs = create_requirement(validated_data=_req_data(), user=other_hm)
    ids = {r["req_id"] for r in auth_client(hm_user).get("/api/requirements/").data["results"]}
    assert mine.req_id in ids
    assert theirs.req_id not in ids
    assert auth_client(hm_user).get(f"/api/requirements/{theirs.req_id}/").status_code == 404


# --- Server-side deep-link filters (pagination feature) ---------------------
# These filters used to run client-side over the first 100 rows; now they run in
# the queryset so lists + counts are correct at any scale.
def test_requirement_list_status_active_excludes_terminal(auth_client, admin_user):
    rows = auth_client(admin_user).get(
        "/api/requirements/", {"status": "active", "page_size": 100}).data["results"]
    terminal = {"CLOSE_FILLED", "CLOSE_LOST", "CANCELLED"}
    assert all(r["req_status_code"] not in terminal for r in rows)


def test_requirement_list_missing_recruiter(auth_client, admin_user, hm_user):
    unassigned = create_requirement(validated_data=_req_data(), user=hm_user)  # no recruiter
    rows = auth_client(admin_user).get(
        "/api/requirements/", {"missing": "recruiter", "page_size": 100}).data["results"]
    assert unassigned.req_id in {r["req_id"] for r in rows}
    assert all(r["recruiter"] is None for r in rows)


def test_requirement_search_by_client_name(auth_client, admin_user, hm_user):
    client = ClientMaster.objects.first()
    req = create_requirement(
        validated_data={**_req_data(), "client": client, "jd_role_name": "ZZ Client Search Role"},
        user=hm_user)
    rows = auth_client(admin_user).get(
        "/api/requirements/", {"search": client.client_name, "page_size": 100}).data["results"]
    assert req.req_id in {r["req_id"] for r in rows}


def test_admin_sees_all_requirements(auth_client, admin_user, hm_user, recruiter_user):
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    assign_requirement(requirement=req, recruiter=recruiter_user, user=hm_user)
    ids = {r["req_id"] for r in auth_client(admin_user).get("/api/requirements/").data["results"]}
    assert req.req_id in ids  # admin is unrestricted
    assert auth_client(admin_user).get(f"/api/requirements/{req.req_id}/").status_code == 200


# --- Event-driven status workflow --------------------------------------------

def _link_first_candidate(req, recruiter, mobile="9000007001"):
    from candidates.services import upsert_candidate
    from pipeline.services import review_candidate
    cand = upsert_candidate(
        data={"candidate_name": "L", "mobile": mobile, "email": f"{mobile}@example.com",
              "is_willing_to_relocate": False},
        user=recruiter,
    )["candidate"]
    return review_candidate(requirement=req, candidate=cand, decision="SHORTLISTED",
                            comments="", user=recruiter)


def test_first_candidate_link_moves_requirement_to_open(hm_user, recruiter_user):
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    assign_requirement(requirement=req, recruiter=recruiter_user, user=hm_user)
    req.refresh_from_db()
    assert req.req_status.status_code == "ASSIGNED"
    _link_first_candidate(req, recruiter_user)
    req.refresh_from_db()
    assert req.req_status.status_code == "OPEN"  # first candidate linked → Open


def test_status_not_settable_via_create_or_update(auth_client, hm_user):
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    assert req.req_status.status_code == "NEW"  # create always → New
    # req_status is not a writable field — a PATCH attempt is silently ignored.
    r = auth_client(hm_user).patch(
        f"/api/requirements/{req.req_id}/", {"req_status": 99, "jd_role_name": "Changed"}, format="json")
    assert r.status_code == 200
    req.refresh_from_db()
    assert req.req_status.status_code == "NEW" and req.jd_role_name == "Changed"


def test_manual_hold_and_resume(auth_client, hm_user):
    """Hold requires a mandatory reason and inactivates the open seats; Resume
    (reason optional) restores them and reopens the requirement."""
    from admin_module.models import RequirementPosition
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)  # 2 open seats
    open_requirement_on_first_link(req, hm_user)  # → Open
    client = auth_client(hm_user)
    # Hold without a reason is rejected.
    assert client.post(f"/api/requirements/{req.req_id}/set-status/",
                       {"to_status": "HOLD"}, format="json").status_code == 400
    assert client.post(f"/api/requirements/{req.req_id}/set-status/",
                       {"to_status": "HOLD", "reason": "Budget freeze"}, format="json").data["req_status_code"] == "HOLD"
    # Open seats became Inactive (system).
    codes = {s.position_status.status_code for s in RequirementPosition.objects.filter(req=req)}
    assert codes == {"INACTIVE"}
    # Resume → Open, and the auto-inactivated seats return to Open.
    assert client.post(f"/api/requirements/{req.req_id}/set-status/",
                       {"to_status": "OPEN"}, format="json").data["req_status_code"] == "OPEN"
    codes = {s.position_status.status_code for s in RequirementPosition.objects.filter(req=req)}
    assert codes == {"OPEN"}


def test_cancel_requirement_is_explicit_and_requires_reason(auth_client, hm_user):
    """Cancel is an explicit HM action → CANCELLED (never auto Close Lost) and
    requires a reason; open seats become Inactive."""
    from admin_module.models import RequirementPosition
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)  # 2 unfilled seats
    open_requirement_on_first_link(req, hm_user)
    client = auth_client(hm_user)
    assert client.post(f"/api/requirements/{req.req_id}/set-status/",
                       {"to_status": "CANCELLED"}, format="json").status_code == 400  # reason required
    r = client.post(f"/api/requirements/{req.req_id}/set-status/",
                    {"to_status": "CANCELLED", "reason": "Role withdrawn"}, format="json")
    assert r.status_code == 200 and r.data["req_status_code"] == "CANCELLED"
    assert {s.position_status.status_code for s in RequirementPosition.objects.filter(req=req)} == {"INACTIVE"}


def test_cancelling_all_positions_does_not_cancel_requirement(hm_user):
    """Requirement and position lifecycles are independent — cancelling every
    seat must NOT auto-cancel the requirement (only an explicit HM/Admin cancel
    can). The requirement stays exactly where it was."""
    from admin_module.models import RequirementPosition
    from core.constants import PositionStatus
    from requirements.positions import set_position_status
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)  # 2 seats
    open_requirement_on_first_link(req, hm_user)  # → Open
    for seat in RequirementPosition.objects.filter(req=req):
        set_position_status(position=seat, to_status_code=PositionStatus.CANCELLED, user=hm_user)
    req.refresh_from_db()
    assert req.req_status.status_code == "OPEN"  # unchanged — never auto-Cancelled


def test_hm_can_hold_assigned_requirement(auth_client, hm_user, recruiter_user):
    """Active states (Assigned included) all allow Hold — assignment doesn't
    strip the HM's lifecycle control."""
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    assign_requirement(requirement=req, recruiter=recruiter_user, user=hm_user)  # → Assigned
    req.refresh_from_db()
    assert req.req_status.status_code == "ASSIGNED"
    r = auth_client(hm_user).post(f"/api/requirements/{req.req_id}/set-status/",
                                  {"to_status": "HOLD", "reason": "On hold"}, format="json")
    assert r.status_code == 200 and r.data["req_status_code"] == "HOLD"


def test_hm_can_cancel_partial_filled_requirement(auth_client, hm_user):
    """A Partial Filled requirement can be cancelled → CANCELLED. The FILLED seat
    is preserved; only the open seat becomes Inactive (Rule 8)."""
    from admin_module.models import RequirementPosition
    from core.constants import PositionStatus
    from requirements.positions import set_position_status
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)  # 2 seats
    open_requirement_on_first_link(req, hm_user)
    seat = RequirementPosition.objects.filter(req=req).order_by("position_no").first()
    set_position_status(position=seat, to_status_code=PositionStatus.FILLED, user=hm_user)  # → Partial Filled
    req.refresh_from_db()
    assert req.req_status.status_code == "PARTIAL_FILLED"
    r = auth_client(hm_user).post(f"/api/requirements/{req.req_id}/set-status/",
                                  {"to_status": "CANCELLED", "reason": "Client paused"}, format="json")
    assert r.status_code == 200 and r.data["req_status_code"] == "CANCELLED"
    codes = sorted(s.position_status.status_code for s in RequirementPosition.objects.filter(req=req))
    assert codes == ["FILLED", "INACTIVE"]  # filled preserved, open → inactive


@pytest.mark.parametrize("from_open,to_status", [
    (True, "CLOSE_FILLED"),   # system-calculated, never manual
    (True, "PARTIAL_FILLED"), # system-calculated
    (False, "HOLD"),          # cannot Hold a New requirement
])
def test_illegal_manual_transitions_rejected(auth_client, hm_user, from_open, to_status):
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    if from_open:
        open_requirement_on_first_link(req, hm_user)
    r = auth_client(hm_user).post(f"/api/requirements/{req.req_id}/set-status/",
                                  {"to_status": to_status}, format="json")
    assert r.status_code == 400


def test_recruiter_cannot_change_requirement_status(auth_client, hm_user, recruiter_user):
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    assign_requirement(requirement=req, recruiter=recruiter_user, user=hm_user)
    r = auth_client(recruiter_user).post(f"/api/requirements/{req.req_id}/set-status/",
                                         {"to_status": "HOLD"}, format="json")
    assert r.status_code == 403  # recruiters may not change requirement status


def test_close_lost_is_terminal(auth_client, hm_user):
    """Closed Lost is an explicit HM action (reason required) and is TERMINAL —
    it cannot be reopened."""
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    open_requirement_on_first_link(req, hm_user)
    client = auth_client(hm_user)
    r = client.post(f"/api/requirements/{req.req_id}/set-status/",
                    {"to_status": "CLOSE_LOST", "reason": "Lost to competitor"}, format="json")
    assert r.status_code == 200 and r.data["req_status_code"] == "CLOSE_LOST"
    # Reopen is rejected — Closed Lost is terminal.
    assert client.post(f"/api/requirements/{req.req_id}/set-status/",
                       {"to_status": "OPEN"}, format="json").status_code == 400


def test_reopen_cancelled_requirement(auth_client, hm_user):
    from admin_module.models import ReqStatusMaster
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    req.req_status = ReqStatusMaster.objects.get(status_code="CANCELLED")
    req.save(update_fields=["req_status"])
    r = auth_client(hm_user).post(f"/api/requirements/{req.req_id}/set-status/",
                                  {"to_status": "OPEN"}, format="json")
    assert r.status_code == 200 and r.data["req_status_code"] == "OPEN"


def test_assign_endpoint_is_admin_only(auth_client, admin_user, hm_user, recruiter_user):
    """Assign/reassign a recruiter is Admin-only — HM and Recruiter get 403."""
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    body = {"recruiter": recruiter_user.user_id}
    assert auth_client(hm_user).post(
        f"/api/requirements/{req.req_id}/assign/", body, format="json").status_code == 403
    assert auth_client(recruiter_user).post(
        f"/api/requirements/{req.req_id}/assign/", body, format="json").status_code == 403
    ok = auth_client(admin_user).post(f"/api/requirements/{req.req_id}/assign/", body, format="json")
    assert ok.status_code == 200 and ok.data["recruiter"] == recruiter_user.user_id


def test_admin_cannot_edit_or_change_status(auth_client, admin_user, hm_user):
    """RBAC: edit + lifecycle transitions are Hiring-Manager-only; Admin → 403."""
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    open_requirement_on_first_link(req, hm_user)  # → Open
    client = auth_client(admin_user)
    assert client.patch(f"/api/requirements/{req.req_id}/",
                        {"jd_role_name": "X"}, format="json").status_code == 403
    assert client.post(f"/api/requirements/{req.req_id}/set-status/",
                       {"to_status": "HOLD"}, format="json").status_code == 403
    req.refresh_from_db()
    assert req.req_status.status_code == "OPEN" and req.jd_role_name != "X"  # unchanged


def test_hm_cannot_assign_recruiter(auth_client, hm_user, recruiter_user):
    """RBAC: assignment is Admin-only; Hiring Manager → 403."""
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    r = auth_client(hm_user).post(f"/api/requirements/{req.req_id}/assign/",
                                  {"recruiter": recruiter_user.user_id}, format="json")
    assert r.status_code == 403


def test_assign_requirement_sets_status_and_recruiter(hm_user, recruiter_user):
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    assign_requirement(requirement=req, recruiter=recruiter_user, user=hm_user)
    req.refresh_from_db()
    assert req.recruiter_id == recruiter_user.user_id
    assert req.req_status.status_code == "ASSIGNED"
    assert req.assigned_date is not None


# --- Positions (redesign phase 3): each requirement materialises N seats, and
#     requirement status is a rollup of seat statuses. --------------------------

def test_create_requirement_materialises_positions(hm_user):
    from admin_module.models import RequirementPosition
    req = create_requirement(validated_data=_req_data(), user=hm_user)  # positions_open=2
    seats = list(RequirementPosition.objects.filter(req=req).order_by("position_no"))
    assert [s.position_no for s in seats] == [1, 2]
    assert all(s.position_status.status_code == "OPEN" for s in seats)


def test_requirement_status_rolls_up_from_positions(hm_user):
    from admin_module.models import RequirementPosition
    from requirements.positions import set_position_status
    from core.constants import PositionStatus
    req = create_requirement(validated_data=_req_data(), user=hm_user)  # 2 seats
    seats = list(RequirementPosition.objects.filter(req=req).order_by("position_no"))

    set_position_status(position=seats[0], to_status_code=PositionStatus.FILLED, user=hm_user)
    req.refresh_from_db()
    assert req.req_status.status_code == "PARTIAL_FILLED"
    assert req.positions_filled == 1

    set_position_status(position=seats[1], to_status_code=PositionStatus.FILLED, user=hm_user)
    req.refresh_from_db()
    assert req.req_status.status_code == "CLOSE_FILLED"
    assert req.positions_filled == 2


def test_positions_endpoint_lists_seats(auth_client, hm_user):
    req = create_requirement(validated_data=_req_data(), user=hm_user)  # 2 seats
    resp = auth_client(hm_user).get(f"/api/requirements/{req.req_id}/positions/")
    assert resp.status_code == 200
    assert len(resp.data) == 2
    assert all(row["position_status_code"] == "OPEN" for row in resp.data)


def test_position_status_is_hm_only(auth_client, admin_user, hm_user, recruiter_user):
    """Manual seat management is Hiring-Manager-only — Recruiter AND Admin are
    read-only (403); only HM can change a position's status."""
    from admin_module.models import RequirementPosition
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    seat = RequirementPosition.objects.filter(req=req).order_by("position_no").first()
    body = {"position_id": seat.position_id, "to_status": "HOLD"}
    assert auth_client(recruiter_user).post(
        f"/api/requirements/{req.req_id}/set-position-status/", body, format="json").status_code == 403
    assert auth_client(admin_user).post(
        f"/api/requirements/{req.req_id}/set-position-status/", body, format="json").status_code == 403
    ok = auth_client(hm_user).post(
        f"/api/requirements/{req.req_id}/set-position-status/", body, format="json")
    assert ok.status_code == 200
    assert ok.data["req_status_code"] == "NEW"  # position change never sets a manual req status


def _seat(req):
    from admin_module.models import RequirementPosition
    return RequirementPosition.objects.filter(req=req).order_by("position_no").first()


def test_position_manual_transitions_and_reopen(auth_client, hm_user):
    """HM: Open→Hold→Open, Open→Cancelled, and Reopen (Cancelled→Open)."""
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    client = auth_client(hm_user)

    def setp(code):
        return client.post(f"/api/requirements/{req.req_id}/set-position-status/",
                           {"position_id": _seat(req).position_id, "to_status": code}, format="json")

    assert setp("HOLD").status_code == 200 and _seat(req).position_status.status_code == "HOLD"
    assert setp("OPEN").status_code == 200 and _seat(req).position_status.status_code == "OPEN"
    assert setp("CANCELLED").status_code == 200 and _seat(req).position_status.status_code == "CANCELLED"
    assert setp("OPEN").status_code == 200 and _seat(req).position_status.status_code == "OPEN"  # reopen


def test_position_cannot_be_manually_filled(auth_client, hm_user):
    """A seat can never be set to Filled manually (only a candidate Joining fills it)."""
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    r = auth_client(hm_user).post(f"/api/requirements/{req.req_id}/set-position-status/",
                                  {"position_id": _seat(req).position_id, "to_status": "FILLED"}, format="json")
    assert r.status_code == 400
    assert _seat(req).position_status.status_code == "OPEN"


def test_filled_position_is_terminal(auth_client, hm_user):
    """Filled is terminal — it can't be manually moved to Hold/Cancel/Open."""
    from core.constants import PositionStatus
    from requirements.positions import set_position_status
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    set_position_status(position=_seat(req), to_status_code=PositionStatus.FILLED, user=hm_user)  # auto-fill path
    for code in ("HOLD", "CANCELLED", "OPEN"):
        r = auth_client(hm_user).post(f"/api/requirements/{req.req_id}/set-position-status/",
                                      {"position_id": _seat(req).position_id, "to_status": code}, format="json")
        assert r.status_code == 400, code
    assert _seat(req).position_status.status_code == "FILLED"


def test_manual_hold_survives_rollup(hm_user):
    from admin_module.models import RequirementPosition, ReqStatusMaster
    from requirements.positions import set_position_status, recompute_requirement
    from core.constants import PositionStatus, ReqStatus
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    # A human puts the whole requirement on Hold.
    req.req_status = ReqStatusMaster.objects.get(status_code=ReqStatus.HOLD)
    req.save(update_fields=["req_status"])
    seats = list(RequirementPosition.objects.filter(req=req).order_by("position_no"))
    set_position_status(position=seats[0], to_status_code=PositionStatus.FILLED, user=hm_user)
    req.refresh_from_db()
    # Rollup must NOT override a manual Hold.
    assert req.req_status.status_code == "HOLD"


# ---------------------------------------------------------------------------
# Requirement/Position workflow enhancement (migration 0020) — new rules
# ---------------------------------------------------------------------------
def _seat_codes(req):
    from admin_module.models import RequirementPosition
    return sorted(
        (s.position_status.status_code if s.position_status_id else "OPEN")
        for s in RequirementPosition.objects.filter(req=req)
    )


def test_hold_preserves_manual_and_filled_seats(auth_client, hm_user):
    """Requirement Hold inactivates only OPEN seats; Filled and manually-Held seats
    are preserved. Resume reopens only the auto-inactivated ones (Rules 4/5/8)."""
    from admin_module.models import RequirementPosition
    from core.constants import PositionStatus
    from requirements.positions import change_position_status, set_position_status
    from requirements.services import open_requirement_on_first_link
    data = _req_data(); data["positions_open"] = 3
    req = create_requirement(validated_data=data, user=hm_user)
    open_requirement_on_first_link(req, hm_user)
    seats = list(RequirementPosition.objects.filter(req=req).order_by("position_no"))
    set_position_status(position=seats[0], to_status_code=PositionStatus.FILLED, user=hm_user)
    change_position_status(position=seats[1], to_status_code=PositionStatus.HOLD, user=hm_user)
    client = auth_client(hm_user)
    client.post(f"/api/requirements/{req.req_id}/set-status/", {"to_status": "HOLD", "reason": "freeze"}, format="json")
    assert _seat_codes(req) == ["FILLED", "HOLD", "INACTIVE"]
    client.post(f"/api/requirements/{req.req_id}/set-status/", {"to_status": "OPEN"}, format="json")
    assert _seat_codes(req) == ["FILLED", "HOLD", "OPEN"]  # manual hold NOT auto-reopened


def test_reopen_cancelled_restores_only_auto_seats(auth_client, hm_user):
    from admin_module.models import RequirementPosition
    from core.constants import PositionStatus
    from requirements.positions import change_position_status
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)  # 2 seats
    open_requirement_on_first_link(req, hm_user)
    seats = list(RequirementPosition.objects.filter(req=req).order_by("position_no"))
    change_position_status(position=seats[0], to_status_code=PositionStatus.CANCELLED, user=hm_user)
    client = auth_client(hm_user)
    client.post(f"/api/requirements/{req.req_id}/set-status/", {"to_status": "CANCELLED", "reason": "x"}, format="json")
    assert _seat_codes(req) == ["CANCELLED", "INACTIVE"]
    r = client.post(f"/api/requirements/{req.req_id}/set-status/", {"to_status": "OPEN"}, format="json")
    assert r.data["req_status_code"] == "OPEN"
    assert _seat_codes(req) == ["CANCELLED", "OPEN"]  # manual cancel stays


def test_add_positions_only_on_active(auth_client, hm_user):
    from admin_module.models import RequirementPosition
    from core.constants import PositionStatus
    from requirements.positions import set_position_status
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)  # 2 seats, New
    client = auth_client(hm_user)
    assert client.post(f"/api/requirements/{req.req_id}/add-positions/", {"count": 2}, format="json").status_code == 200
    assert RequirementPosition.objects.filter(req=req).count() == 4
    open_requirement_on_first_link(req, hm_user)
    for s in RequirementPosition.objects.filter(req=req):
        set_position_status(position=s, to_status_code=PositionStatus.FILLED, user=hm_user)
    req.refresh_from_db()
    assert req.req_status.status_code == "CLOSE_FILLED"
    # Adding to a Filled requirement is blocked (Additional Rule).
    assert client.post(f"/api/requirements/{req.req_id}/add-positions/", {"count": 1}, format="json").status_code == 400


def test_add_positions_forbidden_for_recruiter(auth_client, hm_user, recruiter_user):
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    assign_requirement(requirement=req, recruiter=recruiter_user, user=hm_user)
    assert auth_client(recruiter_user).post(
        f"/api/requirements/{req.req_id}/add-positions/", {"count": 1}, format="json").status_code == 403


def test_delete_position_guarded(auth_client, hm_user):
    from admin_module.models import RequirementPosition
    from core.constants import PositionStatus
    from requirements.positions import set_position_status
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)  # 2 seats
    open_requirement_on_first_link(req, hm_user)
    seats = list(RequirementPosition.objects.filter(req=req).order_by("position_no"))
    set_position_status(position=seats[0], to_status_code=PositionStatus.FILLED, user=hm_user)
    client = auth_client(hm_user)
    assert client.post(f"/api/requirements/{req.req_id}/delete-position/",
                       {"position_id": seats[0].position_id}, format="json").status_code == 400  # filled -> guard
    assert client.post(f"/api/requirements/{req.req_id}/delete-position/",
                       {"position_id": seats[1].position_id}, format="json").status_code == 200
    assert RequirementPosition.objects.filter(req=req).count() == 1


def test_manual_inactive_is_rejected(auth_client, hm_user):
    from admin_module.models import RequirementPosition
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    open_requirement_on_first_link(req, hm_user)
    seat = RequirementPosition.objects.filter(req=req).first()
    assert auth_client(hm_user).post(
        f"/api/requirements/{req.req_id}/set-position-status/",
        {"position_id": seat.position_id, "to_status": "INACTIVE"}, format="json").status_code == 400


def test_expired_overlay_makes_requirement_read_only(auth_client, hm_user):
    import datetime
    from admin_module.models import RequirementPosition
    from requirements.services import open_requirement_on_first_link
    data = _req_data(); data["target_fill_date"] = datetime.date(2020, 1, 1)
    req = create_requirement(validated_data=data, user=hm_user)
    open_requirement_on_first_link(req, hm_user)
    client = auth_client(hm_user)
    detail = client.get(f"/api/requirements/{req.req_id}/").data
    assert detail["is_expired"] is True and detail["expired_on"] is not None
    seat = RequirementPosition.objects.filter(req=req).first()
    assert client.post(f"/api/requirements/{req.req_id}/set-status/",
                       {"to_status": "HOLD", "reason": "x"}, format="json").status_code == 400
    assert client.post(f"/api/requirements/{req.req_id}/set-position-status/",
                       {"position_id": seat.position_id, "to_status": "HOLD"}, format="json").status_code == 400
    assert client.post(f"/api/requirements/{req.req_id}/add-positions/", {"count": 1}, format="json").status_code == 400
    assert client.patch(f"/api/requirements/{req.req_id}/", {"jd_role_name": "X"}, format="json").status_code == 400
    r = client.patch(f"/api/requirements/{req.req_id}/", {"target_fill_date": "2030-12-31"}, format="json")
    assert r.status_code == 200
    assert client.get(f"/api/requirements/{req.req_id}/").data["is_expired"] is False


def test_recruiter_blocked_on_held_requirement(auth_client, hm_user, recruiter_user):
    from candidates.services import upsert_candidate
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    assign_requirement(requirement=req, recruiter=recruiter_user, user=hm_user)
    open_requirement_on_first_link(req, hm_user)
    auth_client(hm_user).post(f"/api/requirements/{req.req_id}/set-status/",
                              {"to_status": "HOLD", "reason": "x"}, format="json")
    cand = upsert_candidate(
        data={"candidate_name": "T", "mobile": "9000022441", "email": "t22441@x.com",
              "is_willing_to_relocate": False}, user=recruiter_user)["candidate"]
    r = auth_client(recruiter_user).post(
        "/api/pipeline/review/",
        {"requirement": req.req_id, "candidate": cand.cv_id, "decision": "SHORTLISTED"}, format="json")
    assert r.status_code == 400  # recruitment paused while on Hold


def test_status_history_is_recorded(auth_client, hm_user):
    from requirements.services import open_requirement_on_first_link
    req = create_requirement(validated_data=_req_data(), user=hm_user)
    open_requirement_on_first_link(req, hm_user)
    client = auth_client(hm_user)
    client.post(f"/api/requirements/{req.req_id}/set-status/", {"to_status": "HOLD", "reason": "audit me"}, format="json")
    rows = client.get(f"/api/requirements/{req.req_id}/status-history/").data
    hold = [r for r in rows if r["entity_type"] == "REQUIREMENT" and r["new_status"] == "HOLD"]
    assert hold and hold[0]["reason"] == "audit me" and hold[0]["change_type"] == "MANUAL"
    assert any(r["entity_type"] == "POSITION" and r["new_status"] == "INACTIVE"
               and r["change_type"] == "AUTO" for r in rows)
