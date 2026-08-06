"""Bulk candidate upload — mentor-approved Naukri "Candidate Details" template.

Covers parsing (header auto-detect, decorative/insights rows ignored), value
parsers (experience / salary / age+DOB / qualification), the curated location
alias map + unmapped-location preservation, preferred-location → notes, resume
title/comments → notes, multi-number cells, validation (required / email /
mobile / in-file duplicate), the validate-only preview, and import (valid-only,
duplicate routing) — all without touching existing duplicate detection.
"""
import io
import datetime

import openpyxl
import pytest
from django.utils import timezone

from admin_module.models import BulkImportBatch, CandidateMaster, CandidateStatusMaster, LocationMaster, SourceMaster
from candidates import services
from candidates.services import (
    CREATED,
    confirm_import_batch,
    fail_stale_import_batches,
    import_candidates_excel,
    preview_candidates_excel,
    purge_stale_draft_batches,
    rollback_import_batch,
    upsert_candidate,
)

pytestmark = pytest.mark.django_db

# Full mentor template header set (col A "#" through Comment 5).
HEADERS = [
    "#", "Candidate Name", "Resume Title", "Contact No.", "Email", "Work Exp",
    "Annual Salary", "Current Location", "Preferred Location", "Current Employer",
    "Designation", "U.G. Course", "P. G. Course", "Post P. G. Course",
    "Age/Date of Birth", "Postal Address",
    "Comment 1", "Comment 2", "Comment 3", "Comment 4", "Comment 5",
]


def make_xlsx(rows, *, header_row=5, sheet_name="Candidate Details",
              add_insights=True, headers=HEADERS, blank_rows_between=False):
    """Build an in-memory .xlsx mirroring the Naukri export layout: a decorative
    title above, the header at `header_row`, then data rows. `rows` are dicts
    keyed by header label."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    if header_row >= 3:
        ws.cell(row=header_row - 2, column=1, value="Downloaded from Test on 03 Oct 2025")
    for j, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=j, value=h)
    r = header_row + 1
    for row in rows:
        for j, h in enumerate(headers, start=1):
            ws.cell(row=r, column=j, value=row.get(h))
        r += 2 if blank_rows_between else 1  # optional interleaved blank rows
    if add_insights:
        ws2 = wb.create_sheet("Candidate insights")
        ws2.cell(row=5, column=2, value="Candidate Insights on N Downloaded Profiles")
        ws2.cell(row=7, column=2, value="Median Salary")
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio


def _row(**kw):
    base = {"Candidate Name": "Test User", "Contact No.": "9111100000", "Email": "t@example.com"}
    base.update(kw)
    return base


# --- Parsing / structure -----------------------------------------------------

def test_header_autodetect_and_insights_ignored(recruiter_user):
    f = make_xlsx([_row(**{"Candidate Name": "Asha Rao", "Contact No.": "9111100101", "Email": "asha@ex.com"})])
    rep = preview_candidates_excel(file=f)
    assert rep["ok"] and rep["header_row"] == 5
    assert rep["summary"]["total"] == 1  # only the data sheet's single row
    assert rep["rows"][0]["excel_row"] == 6  # data starts right after the header


def test_empty_and_decorative_rows_skipped(recruiter_user):
    f = make_xlsx(
        [_row(**{"Contact No.": "9111100201", "Email": "a@ex.com"}),
         _row(**{"Contact No.": "9111100202", "Email": "b@ex.com"})],
        blank_rows_between=True,
    )
    rep = preview_candidates_excel(file=f)
    assert rep["summary"]["total"] == 2  # interleaved blank rows ignored


def test_missing_header_returns_error(recruiter_user):
    wb = openpyxl.Workbook()
    wb.active.append(["totally", "unrelated", "columns"])
    bio = io.BytesIO(); wb.save(bio); bio.seek(0)
    rep = preview_candidates_excel(file=bio)
    assert rep["ok"] is False and "header" in rep["error"].lower()


# --- Value parsers -----------------------------------------------------------

def test_experience_salary_agedob_parsed(recruiter_user):
    f = make_xlsx([_row(**{
        "Candidate Name": "Suraj Kumar", "Contact No.": "9111100301", "Email": "suraj@ex.com",
        "Work Exp": "7Y 7 M", "Annual Salary": "INR 7.2 L", "Age/Date of Birth": "32 y\n(09 Sep 1993)",
    })])
    rep = import_candidates_excel(file=f, user=recruiter_user)
    assert rep["created"] == 1
    c = CandidateMaster.objects.get(mobile="9111100301")
    assert float(c.exp_min) == 7.6 and float(c.exp_max) == 7.6
    assert float(c.current_ctc_lpa) == 7.2
    assert c.age_at_import == 32
    assert c.date_of_birth == datetime.date(1993, 9, 9)


def test_usd_and_zero_salary_left_blank_with_warning(recruiter_user):
    f = make_xlsx([_row(**{"Contact No.": "9111100302", "Email": "u@ex.com", "Annual Salary": "USD 0.0 L"})])
    rep = preview_candidates_excel(file=f)
    row = rep["rows"][0]
    assert row["status"] == "VALID"
    assert any("not in INR" in w for w in row["warnings"])
    import_candidates_excel(file=make_xlsx([_row(**{"Contact No.": "9111100302", "Email": "u@ex.com", "Annual Salary": "USD 0.0 L"})]), user=recruiter_user)
    assert CandidateMaster.objects.get(mobile="9111100302").current_ctc_lpa is None


def test_qualification_highest_picked(recruiter_user):
    f = make_xlsx([_row(**{"Contact No.": "9111100303", "Email": "q@ex.com",
                           "U.G. Course": "B.tech/b.e.", "P. G. Course": "Mca"})])
    import_candidates_excel(file=f, user=recruiter_user)
    assert CandidateMaster.objects.get(mobile="9111100303").highest_qualification == "Mca"


# --- Location handling -------------------------------------------------------

def test_location_alias_resolves(recruiter_user):
    assert LocationMaster.objects.filter(city__iexact="Bangalore").exists()  # seed precondition
    f = make_xlsx([_row(**{"Contact No.": "9111100401", "Email": "loc1@ex.com", "Current Location": "Bengaluru"})])
    import_candidates_excel(file=f, user=recruiter_user)
    c = CandidateMaster.objects.get(mobile="9111100401")
    assert c.current_location is not None and c.current_location.city.lower() == "bangalore"
    assert not c.current_location_text  # resolved → no raw fallback


def test_location_matching_normalizes_and_disambiguates(recruiter_user):
    """Reconciliation normalizes the imported city (trim, collapse spaces, NFKC,
    case-insensitive) and auto-maps ONLY when the active match is unique; a
    same-named city in another state is left unmapped unless the state is given."""
    from candidates.services import _resolve_location
    from admin_module.models import LocationMaster

    blr = LocationMaster.objects.filter(city__iexact="Bangalore", is_active=True).first()
    assert blr  # seed precondition

    # Whitespace / case / a trailing non-breaking space all resolve to the city.
    for raw in ["  bangalore  ", "BANGALORE", "Bangalore ", "\tBangalore "]:
        obj, _ = _resolve_location(raw)
        assert obj is not None and obj.location_id == blr.location_id, raw

    # A second active 'Bangalore' in another state makes the bare city ambiguous:
    # no auto-map — but supplying the state disambiguates to the right row.
    other = LocationMaster.objects.create(
        city=blr.city, state="Tamil Nadu", country=blr.country, is_active=True)
    assert _resolve_location("Bangalore")[0] is None
    assert _resolve_location(f"Bangalore, {blr.state}")[0].location_id == blr.location_id
    assert _resolve_location("Bangalore, Tamil Nadu")[0].location_id == other.location_id


def test_alias_never_overrides_a_city_present_in_master(recruiter_user):
    """Regression: an imported city that IS in the master must resolve to that row
    even when it is also an alias key. 'Gurugram' exists in the master but was an
    alias key → it got rewritten to 'Gurgaon' (absent) and wrongly kept unmapped."""
    from candidates.services import _resolve_location, _CITY_ALIASES, _norm_header
    from admin_module.models import LocationMaster

    loc, _created = LocationMaster.objects.get_or_create(
        city="Gurugram", state="Haryana", country="India", defaults={"is_active": True})
    if not loc.is_active:
        loc.is_active = True
        loc.save()
    # Precondition: the literal city is an alias key (so the old code rewrote it).
    assert _norm_header("Gurugram") in _CITY_ALIASES

    for raw in ["Gurugram", "gurugram", "  Gurugram ", "Gurugram, Haryana, India"]:
        obj, _ = _resolve_location(raw)
        assert obj is not None and obj.location_id == loc.location_id, raw


def test_unmapped_location_preserved_with_warning(recruiter_user):
    f = make_xlsx([_row(**{"Contact No.": "9111100402", "Email": "loc2@ex.com", "Current Location": "Faridabad"})])
    rep = preview_candidates_excel(file=f)
    assert rep["rows"][0]["status"] == "VALID"
    assert any("Faridabad" in w and "Location Master" in w for w in rep["rows"][0]["warnings"])
    import_candidates_excel(file=make_xlsx([_row(**{"Contact No.": "9111100402", "Email": "loc2@ex.com", "Current Location": "Faridabad"})]), user=recruiter_user)
    c = CandidateMaster.objects.get(mobile="9111100402")
    assert c.current_location is None and c.current_location_text == "Faridabad"  # not discarded


def test_preferred_location_first_kept_rest_in_notes(recruiter_user):
    f = make_xlsx([_row(**{"Contact No.": "9111100403", "Email": "pref@ex.com",
                           "Preferred Location": "Bangalore,Pune,Remote"})])
    import_candidates_excel(file=f, user=recruiter_user)
    c = CandidateMaster.objects.get(mobile="9111100403")
    assert c.preferred_location is not None and c.preferred_location.city.lower() == "bangalore"
    assert "Other preferred locations: Pune, Remote" in (c.additional_notes or "")


# --- Notes assembly ----------------------------------------------------------

def test_resume_title_and_comments_in_notes(recruiter_user):
    f = make_xlsx([_row(**{"Contact No.": "9111100501", "Email": "notes@ex.com",
                           "Resume Title": "RN dev 5y", "Comment 1": "Immediate joiner", "Comment 3": "Referred"})])
    import_candidates_excel(file=f, user=recruiter_user)
    notes = CandidateMaster.objects.get(mobile="9111100501").additional_notes or ""
    assert "Resume title: RN dev 5y" in notes
    assert "Comment 1: Immediate joiner" in notes and "Comment 3: Referred" in notes


# --- Validation --------------------------------------------------------------

def test_missing_required_is_invalid(recruiter_user):
    f = make_xlsx([_row(**{"Candidate Name": "No Email", "Contact No.": "9111100601", "Email": ""})])
    rep = preview_candidates_excel(file=f)
    assert rep["rows"][0]["status"] == "INVALID"
    assert any("Email is required" in e for e in rep["rows"][0]["errors"])


def test_invalid_email_and_mobile_are_invalid(recruiter_user):
    f = make_xlsx([_row(**{"Candidate Name": "Bad", "Contact No.": "12345", "Email": "not-an-email"})])
    rep = preview_candidates_excel(file=f)
    errs = rep["rows"][0]["errors"]
    assert rep["rows"][0]["status"] == "INVALID"
    assert any("mobile" in e.lower() for e in errs) and any("email" in e.lower() for e in errs)


def test_multiple_mobiles_uses_first_valid_with_warning(recruiter_user):
    f = make_xlsx([_row(**{"Contact No.": "8946943098\n8946943098", "Email": "multi@ex.com"})])
    rep = preview_candidates_excel(file=f)
    assert rep["rows"][0]["status"] == "VALID" and rep["rows"][0]["mobile"] == "8946943098"
    assert any("Multiple contact numbers" in w for w in rep["rows"][0]["warnings"])


def test_in_file_duplicate_mobile_is_invalid(recruiter_user):
    f = make_xlsx([
        _row(**{"Contact No.": "9111100701", "Email": "one@ex.com"}),
        _row(**{"Contact No.": "9111100701", "Email": "two@ex.com"}),
    ])
    rep = preview_candidates_excel(file=f)
    assert rep["rows"][0]["status"] == "VALID"
    assert rep["rows"][1]["status"] == "INVALID"
    assert any("within the file" in e for e in rep["rows"][1]["errors"])


def test_invalid_rows_do_not_block_valid_rows(recruiter_user):
    f = make_xlsx([
        _row(**{"Candidate Name": "Good", "Contact No.": "9111100801", "Email": "good@ex.com"}),
        _row(**{"Candidate Name": "Bad", "Contact No.": "9111100802", "Email": "bad"}),
        _row(**{"Candidate Name": "Also Good", "Contact No.": "9111100803", "Email": "good2@ex.com"}),
    ])
    rep = import_candidates_excel(file=f, user=recruiter_user)
    assert rep["created"] == 2 and len(rep["skipped"]) == 1
    assert CandidateMaster.objects.filter(mobile__in=["9111100801", "9111100803"]).count() == 2
    assert not CandidateMaster.objects.filter(mobile="9111100802").exists()


# --- Duplicate detection (existing rules, unchanged) -------------------------

def test_same_mobile_email_updates_existing(recruiter_user):
    upsert_candidate(data={"candidate_name": "Existing", "mobile": "9111100901",
                           "email": "dup@ex.com", "is_willing_to_relocate": False}, user=recruiter_user)
    f = make_xlsx([_row(**{"Candidate Name": "Updated Name", "Contact No.": "9111100901",
                           "Email": "dup@ex.com", "Current Employer": "NewCo"})])
    rep = import_candidates_excel(file=f, user=recruiter_user)
    assert rep["updated"] == 1 and rep["created"] == 0
    assert CandidateMaster.objects.get(mobile="9111100901").current_company == "NewCo"


def test_same_mobile_different_email_routes_to_review_not_created(recruiter_user):
    upsert_candidate(data={"candidate_name": "Existing", "mobile": "9111100902",
                           "email": "orig@ex.com", "is_willing_to_relocate": False}, user=recruiter_user)
    before = CandidateMaster.objects.count()
    f = make_xlsx([_row(**{"Candidate Name": "Clash", "Contact No.": "9111100902", "Email": "different@ex.com"})])
    rep = import_candidates_excel(file=f, user=recruiter_user)
    assert rep["created"] == 0 and len(rep["possible_duplicates"]) == 1
    assert CandidateMaster.objects.count() == before  # nothing new created


# --- Source ------------------------------------------------------------------

def test_source_applied_to_imported_rows(recruiter_user):
    src = SourceMaster.objects.filter(source_name__iexact="Naukri").first()
    f = make_xlsx([_row(**{"Contact No.": "9111101001", "Email": "src@ex.com"})])
    import_candidates_excel(file=f, user=recruiter_user, source=src)
    assert CandidateMaster.objects.get(mobile="9111101001").source_id == src.source_id


def test_preview_does_not_write(recruiter_user):
    before = CandidateMaster.objects.count()
    f = make_xlsx([_row(**{"Contact No.": "9111101101", "Email": "prev@ex.com"})])
    preview_candidates_excel(file=f)
    assert CandidateMaster.objects.count() == before


# --- Feature 1: email duplicate validation -----------------------------------

def test_email_used_by_different_candidate_is_invalid(recruiter_user):
    # An existing candidate owns an email; a NEW mobile reusing that email is a
    # conflict (email is UNIQUE) → INVALID with a friendly message, not a DB error.
    upsert_candidate(data={"candidate_name": "Owner", "mobile": "9111102001",
                           "email": "shared@ex.com", "is_willing_to_relocate": False}, user=recruiter_user)
    f = make_xlsx([_row(**{"Candidate Name": "Clash", "Contact No.": "9111102002", "Email": "shared@ex.com"})])
    rep = preview_candidates_excel(file=f)
    row = rep["rows"][0]
    assert row["status"] == "INVALID"
    assert any("Email already used by" in e for e in row["errors"])


def test_email_conflict_not_created_on_import(recruiter_user):
    upsert_candidate(data={"candidate_name": "Owner", "mobile": "9111102003",
                           "email": "shared2@ex.com", "is_willing_to_relocate": False}, user=recruiter_user)
    before = CandidateMaster.objects.count()
    f = make_xlsx([_row(**{"Candidate Name": "Clash", "Contact No.": "9111102004", "Email": "shared2@ex.com"})])
    rep = import_candidates_excel(file=f, user=recruiter_user)
    assert rep["created"] == 0 and len(rep["skipped"]) == 1
    assert any("Email already used by" in e for e in rep["skipped"][0]["errors"])
    assert CandidateMaster.objects.count() == before  # nothing created
    assert not CandidateMaster.objects.filter(mobile="9111102004").exists()


def test_email_conflict_is_case_insensitive(recruiter_user):
    upsert_candidate(data={"candidate_name": "Owner", "mobile": "9111102005",
                           "email": "casecheck@ex.com", "is_willing_to_relocate": False}, user=recruiter_user)
    f = make_xlsx([_row(**{"Contact No.": "9111102006", "Email": "CaseCheck@EX.com"})])
    rep = preview_candidates_excel(file=f)
    assert rep["rows"][0]["status"] == "INVALID"


def test_in_file_duplicate_email_is_invalid(recruiter_user):
    f = make_xlsx([
        _row(**{"Contact No.": "9111102007", "Email": "dupe@ex.com"}),
        _row(**{"Contact No.": "9111102008", "Email": "dupe@ex.com"}),
    ])
    rep = preview_candidates_excel(file=f)
    assert rep["rows"][0]["status"] == "VALID"
    assert rep["rows"][1]["status"] == "INVALID"
    assert any("Duplicate Email within the file" in e for e in rep["rows"][1]["errors"])


def test_same_candidate_email_update_is_not_email_conflict(recruiter_user):
    # Same mobile + same email = an UPDATE of that candidate — must NOT be flagged
    # as an email conflict.
    upsert_candidate(data={"candidate_name": "Owner", "mobile": "9111102009",
                           "email": "owner9@ex.com", "is_willing_to_relocate": False}, user=recruiter_user)
    f = make_xlsx([_row(**{"Candidate Name": "Owner Updated", "Contact No.": "9111102009",
                           "Email": "owner9@ex.com", "Current Employer": "NewCo"})])
    rep = import_candidates_excel(file=f, user=recruiter_user)
    assert rep["updated"] == 1 and rep["created"] == 0
    assert CandidateMaster.objects.get(mobile="9111102009").current_company == "NewCo"


# --- Feature 2: import batch tracking, audit & rollback ----------------------

def test_import_creates_batch_and_stamps_created(recruiter_user):
    f = make_xlsx([_row(**{"Contact No.": "9111200001", "Email": "b1@ex.com"}),
                   _row(**{"Contact No.": "9111200002", "Email": "b2@ex.com"})])
    rep = import_candidates_excel(file=f, user=recruiter_user)
    assert rep["created"] == 2 and "batch_id" in rep
    batch = BulkImportBatch.objects.get(batch_id=rep["batch_id"])
    assert batch.status == "COMPLETED"
    assert batch.total_rows == 2 and batch.created_count == 2
    assert batch.file_hash and len(batch.row_report) == 2
    for m in ("9111200001", "9111200002"):
        assert CandidateMaster.objects.get(mobile=m).import_batch_id == batch.batch_id


def test_updated_candidates_are_not_stamped_with_batch(recruiter_user):
    upsert_candidate(data={"candidate_name": "Old", "mobile": "9111200003",
                           "email": "upd@ex.com", "is_willing_to_relocate": False}, user=recruiter_user)
    f = make_xlsx([_row(**{"Contact No.": "9111200003", "Email": "upd@ex.com", "Current Employer": "NewCo"})])
    rep = import_candidates_excel(file=f, user=recruiter_user)
    assert rep["updated"] == 1
    assert CandidateMaster.objects.get(mobile="9111200003").import_batch_id is None


def test_rollback_removes_untouched_keeps_worked(recruiter_user):
    f = make_xlsx([_row(**{"Contact No.": "9111200010", "Email": "r1@ex.com"}),
                   _row(**{"Contact No.": "9111200011", "Email": "r2@ex.com"})])
    rep = import_candidates_excel(file=f, user=recruiter_user)
    batch = BulkImportBatch.objects.get(batch_id=rep["batch_id"])
    # Mark one as "worked" (status moved off NEW_CV) → must be kept.
    worked = CandidateMaster.objects.get(mobile="9111200010")
    worked.candidate_status = CandidateStatusMaster.objects.get(status_code="SAVED")
    worked.save(update_fields=["candidate_status"])

    result = rollback_import_batch(batch=batch, user=recruiter_user)
    assert result["removed_count"] == 1 and result["kept_count"] == 1
    batch.refresh_from_db()
    assert batch.status == "ROLLED_BACK"
    assert CandidateMaster.objects.get(mobile="9111200011").is_active is False  # untouched → removed
    assert CandidateMaster.objects.get(mobile="9111200010").is_active is True   # worked → kept


def test_import_batch_list_and_report_endpoints(auth_client, recruiter_user):
    f = make_xlsx([_row(**{"Contact No.": "9111200020", "Email": "h1@ex.com"})])
    rep = import_candidates_excel(file=f, user=recruiter_user)
    client = auth_client(recruiter_user)
    lst = client.get("/api/import-batches/")
    assert lst.status_code == 200 and lst.data["count"] >= 1
    dl = client.get(f"/api/import-batches/{rep['batch_id']}/report/")
    assert dl.status_code == 200 and "spreadsheetml" in dl["Content-Type"]


def test_rollback_endpoint_and_list_exclusion(auth_client, recruiter_user):
    f = make_xlsx([_row(**{"Contact No.": "9111200022", "Email": "perm@ex.com"})])
    rep = import_candidates_excel(file=f, user=recruiter_user)
    client = auth_client(recruiter_user)  # the uploader may roll back their own batch
    resp = client.post(f"/api/import-batches/{rep['batch_id']}/rollback/")
    assert resp.status_code == 200 and resp.data["removed_count"] == 1
    # rolled-back (inactive) candidate drops out of the database list…
    ids = {c["mobile"] for c in client.get("/api/candidates/?status=ALL").data["results"]}
    assert "9111200022" not in ids
    # …but stays reachable by id (detail), and a second rollback is rejected.
    again = client.post(f"/api/import-batches/{rep['batch_id']}/rollback/")
    assert again.status_code == 400


# --- Feature 2 refinements: graceful failure + stale recovery ----------------

def _boom(*args, **kwargs):
    raise RuntimeError("boom")


def test_batch_marked_failed_on_unexpected_error(recruiter_user, monkeypatch):
    # An unexpected error escaping the row loop must mark the batch FAILED (never
    # leave it PENDING) and re-raise.
    monkeypatch.setattr(services, "_classify_row", _boom)
    f = make_xlsx([_row(**{"Contact No.": "9111203001", "Email": "fail@ex.com"})])
    with pytest.raises(RuntimeError):
        import_candidates_excel(file=f, user=recruiter_user)
    b = BulkImportBatch.objects.filter(uploaded_by=recruiter_user).order_by("-batch_id").first()
    assert b is not None and b.status == "FAILED"
    assert "boom" in (b.error_message or "")


def test_fail_stale_pending_batches(recruiter_user):
    old = BulkImportBatch.objects.create(
        status="PENDING", uploaded_by=recruiter_user,
        created_on=timezone.now() - datetime.timedelta(hours=2))
    fresh = BulkImportBatch.objects.create(
        status="PENDING", uploaded_by=recruiter_user, created_on=timezone.now())
    n = fail_stale_import_batches(older_than_minutes=30)
    assert n >= 1
    old.refresh_from_db(); fresh.refresh_from_db()
    assert old.status == "FAILED" and "stale" in (old.error_message or "").lower()
    assert fresh.status == "PENDING"  # too recent → untouched


def test_lifecycle_maintenance_reports_stale_batches(recruiter_user):
    from candidates.services import run_lifecycle_maintenance
    BulkImportBatch.objects.create(
        status="PENDING", uploaded_by=recruiter_user,
        created_on=timezone.now() - datetime.timedelta(hours=2))
    summary = run_lifecycle_maintenance()
    assert "stale_import_batches_failed" in summary and summary["stale_import_batches_failed"] >= 1


def test_mark_failed_endpoint_admin_only(auth_client, recruiter_user, admin_user):
    b = BulkImportBatch.objects.create(status="PENDING", uploaded_by=recruiter_user, created_on=timezone.now())
    # A non-admin (even the uploader) cannot mark-failed.
    assert auth_client(recruiter_user).post(f"/api/import-batches/{b.batch_id}/mark-failed/").status_code == 403
    # Admin can.
    assert auth_client(admin_user).post(f"/api/import-batches/{b.batch_id}/mark-failed/").status_code == 200
    b.refresh_from_db(); assert b.status == "FAILED"
    # A non-PENDING batch → 400.
    assert auth_client(admin_user).post(f"/api/import-batches/{b.batch_id}/mark-failed/").status_code == 400


def test_rollback_reports_updated_not_reversed(recruiter_user):
    upsert_candidate(data={"candidate_name": "Old", "mobile": "9111203010",
                           "email": "upd2@ex.com", "is_willing_to_relocate": False}, user=recruiter_user)
    f = make_xlsx([
        _row(**{"Contact No.": "9111203011", "Email": "new3@ex.com"}),           # created
        _row(**{"Contact No.": "9111203010", "Email": "upd2@ex.com", "Current Employer": "X"}),  # updated
    ])
    rep = import_candidates_excel(file=f, user=recruiter_user)
    assert rep["created"] == 1 and rep["updated"] == 1
    batch = BulkImportBatch.objects.get(batch_id=rep["batch_id"])
    result = rollback_import_batch(batch=batch, user=recruiter_user)
    assert result["removed_count"] == 1              # only the created candidate
    assert result["updated_not_reversed"] == 1       # the updated one is kept, reported


# --- Feature 3: location reconciliation --------------------------------------

def test_unmapped_summary_and_reconcile(recruiter_user):
    from candidates.services import unmapped_location_summary, reconcile_location
    import_candidates_excel(file=make_xlsx([
        _row(**{"Contact No.": "9111300001", "Email": "u1@ex.com", "Current Location": "Faridabad"}),
        _row(**{"Contact No.": "9111300002", "Email": "u2@ex.com", "Current Location": "Faridabad"}),
    ]), user=recruiter_user)
    summary = unmapped_location_summary()
    far = next((r for r in summary if r["text"] == "Faridabad"), None)
    assert far is not None and far["count"] >= 2

    loc = LocationMaster.objects.filter(city__iexact="Bangalore").first()
    n = reconcile_location(text="Faridabad", location=loc, user=recruiter_user)
    assert n >= 2
    for m in ("9111300001", "9111300002"):
        c = CandidateMaster.objects.get(mobile=m)
        assert c.current_location_id == loc.location_id and not c.current_location_text


def test_reconcile_only_touches_fk_null_rows(recruiter_user):
    from candidates.services import reconcile_location
    # A candidate already linked to a city (FK set) must NOT be re-mapped.
    loc_pune = LocationMaster.objects.filter(city__iexact="Pune").first()
    upsert_candidate(data={"candidate_name": "Mapped", "mobile": "9111300003", "email": "m@ex.com",
                           "current_location": loc_pune, "is_willing_to_relocate": False}, user=recruiter_user)
    loc_blr = LocationMaster.objects.filter(city__iexact="Bangalore").first()
    # No unmapped rows with text "Pune" → nothing reconciled, mapped row untouched.
    n = reconcile_location(text="Pune", location=loc_blr, user=recruiter_user)
    assert n == 0
    assert CandidateMaster.objects.get(mobile="9111300003").current_location_id == loc_pune.location_id


def test_verify_update_clears_unmapped_text(recruiter_user):
    from candidates.services import verify_and_update_candidate
    import_candidates_excel(file=make_xlsx([
        _row(**{"Contact No.": "9111300010", "Email": "v@ex.com", "Current Location": "Faridabad"})
    ]), user=recruiter_user)
    c = CandidateMaster.objects.get(mobile="9111300010")
    assert c.current_location_text == "Faridabad" and c.current_location is None
    loc = LocationMaster.objects.filter(city__iexact="Pune").first()
    verify_and_update_candidate(candidate=c, validated_data={"current_location": loc, "verified": False},
                                user=recruiter_user)
    c.refresh_from_db()
    assert c.current_location_id == loc.location_id and not c.current_location_text


def test_unmapped_locations_and_reconcile_endpoints(auth_client, recruiter_user):
    import_candidates_excel(file=make_xlsx([
        _row(**{"Contact No.": "9111300020", "Email": "e@ex.com", "Current Location": "Faridabad"})
    ]), user=recruiter_user)
    client = auth_client(recruiter_user)
    resp = client.get("/api/candidates/unmapped-locations/")
    assert resp.status_code == 200 and any(r["text"] == "Faridabad" for r in resp.data)

    loc = LocationMaster.objects.filter(city__iexact="Bangalore").first()
    r2 = client.post("/api/candidates/reconcile-location/",
                     {"text": "Faridabad", "location_id": loc.location_id}, format="json")
    assert r2.status_code == 200 and r2.data["reconciled"] >= 1
    assert CandidateMaster.objects.get(mobile="9111300020").current_location_id == loc.location_id
    # missing args → 400
    assert client.post("/api/candidates/reconcile-location/", {"text": ""}, format="json").status_code == 400


# --- Feature 4: performance (N+1) + limits -----------------------------------

def test_preview_query_count_is_bounded(recruiter_user, django_assert_max_num_queries):
    # N+1 fix: classification is a fixed handful of queries (location cache + two
    # bounded index queries) regardless of row count — never one lookup per row.
    rows = [_row(**{"Contact No.": f"9114000{i:03d}", "Email": f"q{i}@ex.com"}) for i in range(8)]
    f = make_xlsx(rows)
    with django_assert_max_num_queries(5):
        rep = preview_candidates_excel(file=f)
    assert rep["summary"]["total"] == 8 and rep["summary"]["valid"] == 8


def test_row_limit_rejects_oversized_file(recruiter_user, monkeypatch):
    from candidates import services as svc
    monkeypatch.setattr(svc, "BULK_MAX_ROWS", 2)
    f = make_xlsx([_row(**{"Contact No.": f"9114100{i:02d}", "Email": f"r{i}@ex.com"}) for i in range(3)])
    rep = preview_candidates_excel(file=f)
    assert rep["ok"] is False and "row" in rep["error"].lower()
    # import is capped the same way
    f2 = make_xlsx([_row(**{"Contact No.": f"9114100{i:02d}", "Email": f"r{i}@ex.com"}) for i in range(3)])
    rep2 = import_candidates_excel(file=f2, user=recruiter_user)
    assert rep2["ok"] is False and rep2["created"] == 0


def test_file_size_limit_rejects_large_upload(auth_client, recruiter_user, settings):
    settings.BULK_MAX_BYTES = 10  # tiny cap → any real .xlsx is rejected
    f = make_xlsx([_row(**{"Contact No.": "9114200001", "Email": "big@ex.com"})])
    f.name = "test.xlsx"
    resp = auth_client(recruiter_user).post("/api/candidates/bulk-upload/", {"file": f}, format="multipart")
    assert resp.status_code == 400 and "too large" in str(resp.data).lower()


def test_index_classification_matches_mobile_and_email_rules(recruiter_user):
    # Parity check for the in-memory index: create / update / duplicate / email-conflict
    # all classify exactly as the mobile+email rules require.
    upsert_candidate(data={"candidate_name": "Up", "mobile": "9114300001", "email": "up@ex.com",
                           "is_willing_to_relocate": False}, user=recruiter_user)   # → UPDATE target
    upsert_candidate(data={"candidate_name": "Dp", "mobile": "9114300002", "email": "dp@ex.com",
                           "is_willing_to_relocate": False}, user=recruiter_user)   # → DUPLICATE target
    upsert_candidate(data={"candidate_name": "Ec", "mobile": "9114300003", "email": "ec@ex.com",
                           "is_willing_to_relocate": False}, user=recruiter_user)   # → email owner
    f = make_xlsx([
        _row(**{"Contact No.": "9114300099", "Email": "fresh@ex.com"}),                 # VALID (new)
        _row(**{"Contact No.": "9114300001", "Email": "up@ex.com"}),                    # UPDATE (same mobile+email)
        _row(**{"Contact No.": "9114300002", "Email": "different@ex.com"}),             # DUPLICATE (same mobile, diff email)
        _row(**{"Contact No.": "9114300098", "Email": "ec@ex.com"}),                    # INVALID (email taken)
    ])
    rows = {r["mobile"]: r["status"] for r in preview_candidates_excel(file=f)["rows"]}
    assert rows["9114300099"] == "VALID"
    assert rows["9114300001"] == "UPDATE"
    assert rows["9114300002"] == "DUPLICATE"
    assert rows["9114300098"] == "INVALID"


# --- Validation Summary counters: every scenario -----------------------------

def _summary(f):
    return preview_candidates_excel(file=f)["summary"]


def _invariant(s):
    """The status buckets partition every data row exactly once."""
    assert s["valid"] + s["update"] + s["duplicate"] + s["invalid"] == s["total"]


def test_summary_all_valid_file(recruiter_user):
    f = make_xlsx([_row(**{"Contact No.": f"9115100{i:03d}", "Email": f"v{i}@ex.com"}) for i in range(5)])
    s = _summary(f)
    assert (s["total"], s["valid"], s["update"], s["duplicate"], s["invalid"]) == (5, 5, 0, 0, 0)
    _invariant(s)


def test_summary_reimport_same_file_counts_all_as_updates(recruiter_user):
    rows = [_row(**{"Candidate Name": "A", "Contact No.": f"9115200{i:03d}", "Email": f"u{i}@ex.com"})
            for i in range(4)]
    import_candidates_excel(file=make_xlsx(rows), user=recruiter_user)  # they now exist
    s = _summary(make_xlsx(rows))                                        # same file again
    assert (s["total"], s["valid"], s["update"], s["duplicate"], s["invalid"]) == (4, 0, 4, 0, 0)
    _invariant(s)


def test_summary_db_duplicate_same_mobile_different_email(recruiter_user):
    upsert_candidate(data={"candidate_name": "X", "mobile": "9115300001", "email": "x@ex.com",
                           "is_willing_to_relocate": False}, user=recruiter_user)
    s = _summary(make_xlsx([_row(**{"Contact No.": "9115300001", "Email": "y@ex.com"})]))
    assert (s["total"], s["duplicate"], s["valid"], s["invalid"]) == (1, 1, 0, 0)
    _invariant(s)


def test_summary_intra_file_duplicate_mobile_blocks_second_row(recruiter_user):
    rep = preview_candidates_excel(file=make_xlsx([
        _row(**{"Contact No.": "9115400001", "Email": "a1@ex.com"}),
        _row(**{"Contact No.": "9115400001", "Email": "a2@ex.com"}),  # same mobile within the file
    ]))
    s = rep["summary"]
    assert (s["total"], s["valid"], s["invalid"]) == (2, 1, 0 + 1)
    assert rep["rows"][1]["status"] == "INVALID"
    assert any("Duplicate Contact No. within the file" in e for e in rep["rows"][1]["errors"])
    _invariant(s)


def test_summary_same_candidate_twice_in_file(recruiter_user):
    # Identical mobile AND email twice → first imports, second blocked as in-file dup.
    rep = preview_candidates_excel(file=make_xlsx([
        _row(**{"Contact No.": "9115450001", "Email": "twice@ex.com"}),
        _row(**{"Contact No.": "9115450001", "Email": "twice@ex.com"}),
    ]))
    s = rep["summary"]
    assert (s["total"], s["valid"], s["invalid"]) == (2, 1, 1)
    _invariant(s)


def test_summary_intra_file_duplicate_email_blocks_second_row(recruiter_user):
    rep = preview_candidates_excel(file=make_xlsx([
        _row(**{"Contact No.": "9115500001", "Email": "same@ex.com"}),
        _row(**{"Contact No.": "9115500002", "Email": "same@ex.com"}),  # same email within the file
    ]))
    s = rep["summary"]
    assert (s["total"], s["valid"], s["invalid"]) == (2, 1, 1)
    assert any("Duplicate Email within the file" in e for e in rep["rows"][1]["errors"])
    _invariant(s)


def test_summary_validation_error_row_is_invalid(recruiter_user):
    # A row with data but no mobile/email → blocked (invalid), not skipped.
    rep = preview_candidates_excel(file=make_xlsx([
        _row(**{"Candidate Name": "No Contact", "Contact No.": "", "Email": ""}),
    ]))
    s = rep["summary"]
    assert (s["total"], s["invalid"], s["valid"]) == (1, 1, 0)
    assert rep["rows"][0]["errors"]
    _invariant(s)


def test_summary_warning_only_row_still_valid_and_counted(recruiter_user):
    rep = preview_candidates_excel(file=make_xlsx([
        _row(**{"Contact No.": "9115700001", "Email": "w@ex.com", "Current Location": "Faridabad"}),
    ]))
    s = rep["summary"]
    assert (s["total"], s["valid"], s["invalid"]) == (1, 1, 0)
    assert s["warnings"] == 1 and rep["rows"][0]["warnings"]  # warning surfaced, row still importable
    _invariant(s)


def test_summary_row_with_warning_and_error_counts_in_both(recruiter_user):
    # Row 2 has an in-file duplicate error AND a location warning → invalid + warned.
    rep = preview_candidates_excel(file=make_xlsx([
        _row(**{"Contact No.": "9115800001", "Email": "e1@ex.com"}),
        _row(**{"Contact No.": "9115800001", "Email": "e2@ex.com", "Current Location": "Faridabad"}),
    ]))
    s = rep["summary"]
    assert s["invalid"] == 1 and s["warnings"] >= 1
    assert rep["rows"][1]["status"] == "INVALID" and rep["rows"][1]["warnings"]
    _invariant(s)


def test_summary_mixed_file_partitions_correctly(recruiter_user):
    upsert_candidate(data={"candidate_name": "Upd", "mobile": "9115900001", "email": "upd@ex.com",
                           "is_willing_to_relocate": False}, user=recruiter_user)  # UPDATE target
    upsert_candidate(data={"candidate_name": "Dup", "mobile": "9115900002", "email": "dup@ex.com",
                           "is_willing_to_relocate": False}, user=recruiter_user)  # DUPLICATE target
    rep = preview_candidates_excel(file=make_xlsx([
        _row(**{"Contact No.": "9115900010", "Email": "new1@ex.com"}),                       # VALID
        _row(**{"Contact No.": "9115900011", "Email": "new2@ex.com", "Current Location": "Faridabad"}),  # VALID + warn
        _row(**{"Contact No.": "9115900001", "Email": "upd@ex.com"}),                         # UPDATE
        _row(**{"Contact No.": "9115900002", "Email": "other@ex.com"}),                       # DUPLICATE
        _row(**{"Candidate Name": "Bad", "Contact No.": "", "Email": ""}),                    # INVALID
    ]))
    s = rep["summary"]
    assert (s["total"], s["valid"], s["update"], s["duplicate"], s["invalid"]) == (5, 2, 1, 1, 1)
    assert s["warnings"] == 1
    _invariant(s)


def test_import_skips_duplicates_from_created_count(recruiter_user):
    upsert_candidate(data={"candidate_name": "Ex", "mobile": "9116000001", "email": "ex@ex.com",
                           "is_willing_to_relocate": False}, user=recruiter_user)
    rep = import_candidates_excel(file=make_xlsx([
        _row(**{"Contact No.": "9116000099", "Email": "fresh@ex.com"}),   # created
        _row(**{"Contact No.": "9116000001", "Email": "diff@ex.com"}),    # duplicate → review, NOT created
    ]), user=recruiter_user)
    assert rep["created"] == 1 and len(rep["possible_duplicates"]) == 1


# --- Feature 4 review: unreadable file → clean error (not a 500) -------------

def test_corrupt_file_returns_clean_error(recruiter_user):
    bad = io.BytesIO(b"this is not an xlsx file")
    rep = preview_candidates_excel(file=bad)
    assert rep["ok"] is False and "valid .xlsx" in rep["error"].lower()
    bad2 = io.BytesIO(b"this is not an xlsx file")
    rep2 = import_candidates_excel(file=bad2, user=recruiter_user)
    assert rep2["ok"] is False and rep2["created"] == 0


def test_corrupt_file_via_api_is_400_not_500(auth_client, recruiter_user):
    bad = io.BytesIO(b"garbage"); bad.name = "test.xlsx"
    resp = auth_client(recruiter_user).post("/api/candidates/bulk-preview/", {"file": bad}, format="multipart")
    assert resp.status_code == 400 and "valid .xlsx" in str(resp.data).lower()


# --- Feature 5 (5b/5c/5e/5f): warnings, header variants, dup-file, DOB sanity -

def test_truncation_warnings(recruiter_user):
    f = make_xlsx([_row(**{
        "Candidate Name": "N" * 120, "Contact No.": "9115000001", "Email": "trunc@ex.com",
        "Current Employer": "C" * 130, "Designation": "D" * 130,
    })])
    warns = preview_candidates_excel(file=f)["rows"][0]["warnings"]
    assert any("Candidate Name truncated" in w for w in warns)
    assert any("Current Employer truncated" in w for w in warns)
    assert any("Designation truncated" in w for w in warns)


def test_header_variant_mobile_number(recruiter_user):
    # "Mobile Number" / "E-mail" now recognized (5c).
    headers = ["Candidate Name", "Mobile Number", "E-mail"]
    f = make_xlsx([{"Candidate Name": "Var Iant", "Mobile Number": "9115000010", "E-mail": "var@ex.com"}],
                  headers=headers, header_row=1, add_insights=False)
    rep = preview_candidates_excel(file=f)
    assert rep["ok"] and rep["summary"]["total"] == 1 and rep["rows"][0]["status"] == "VALID"
    assert rep["rows"][0]["mobile"] == "9115000010"


def test_dob_sanity_future_and_implausible(recruiter_user):
    f = make_xlsx([
        _row(**{"Contact No.": "9115000020", "Email": "fut@ex.com", "Age/Date of Birth": "5 y\n(09 Sep 2099)"}),
    ])
    rep = preview_candidates_excel(file=f)
    row = rep["rows"][0]
    assert any("future" in w.lower() or "implausible" in w.lower() for w in row["warnings"])
    # DOB dropped; import stores no DOB.
    import_candidates_excel(
        file=make_xlsx([_row(**{"Contact No.": "9115000020", "Email": "fut@ex.com",
                                "Age/Date of Birth": "5 y\n(09 Sep 2099)"})]),
        user=recruiter_user)
    assert CandidateMaster.objects.get(mobile="9115000020").date_of_birth is None


def test_duplicate_file_warning(recruiter_user):
    f1 = make_xlsx([_row(**{"Contact No.": "9115000030", "Email": "df@ex.com"})])
    raw = f1.getvalue()
    import_candidates_excel(file=io.BytesIO(raw), user=recruiter_user)  # first import (COMPLETED)
    # Preview the SAME bytes → duplicate_file flagged.
    prev = preview_candidates_excel(file=io.BytesIO(raw))
    assert prev["duplicate_file"] is not None and prev["duplicate_file"]["batch_id"] >= 1
    # A different file → no flag.
    other = make_xlsx([_row(**{"Contact No.": "9115000031", "Email": "other@ex.com"})])
    assert preview_candidates_excel(file=other)["duplicate_file"] is None


# --- Feature 5a: preview draft → import confirm -------------------------------

def test_preview_creates_draft_and_confirm_imports(recruiter_user):
    f = make_xlsx([_row(**{"Contact No.": "9116000001", "Email": "d1@ex.com",
                           "Current Location": "Bengaluru", "Work Exp": "3Y 0 M"})])
    prev = preview_candidates_excel(file=f, user=recruiter_user)
    assert prev["ok"] and prev["batch_id"]
    draft = BulkImportBatch.objects.get(batch_id=prev["batch_id"])
    assert draft.status == "DRAFT"
    # Confirm — NO file, imports the exact validated dataset.
    rep = confirm_import_batch(batch=draft, user=recruiter_user)
    assert rep["created"] == 1
    c = CandidateMaster.objects.get(mobile="9116000001")
    assert c.current_location is not None and c.current_location.city.lower() == "bangalore"  # FK round-tripped
    assert float(c.exp_min) == 3.0
    draft.refresh_from_db()
    assert draft.status == "COMPLETED" and c.import_batch_id == draft.batch_id


def test_preview_without_user_creates_no_draft(recruiter_user):
    before = BulkImportBatch.objects.count()
    preview_candidates_excel(file=make_xlsx([_row(**{"Contact No.": "9116000005", "Email": "nd@ex.com"})]))
    assert BulkImportBatch.objects.count() == before  # no draft when user is None


def test_repreview_supersedes_prior_draft(recruiter_user):
    raw = make_xlsx([_row(**{"Contact No.": "9116000010", "Email": "s@ex.com"})]).getvalue()
    p1 = preview_candidates_excel(file=io.BytesIO(raw), user=recruiter_user)
    p2 = preview_candidates_excel(file=io.BytesIO(raw), user=recruiter_user)
    assert not BulkImportBatch.objects.filter(batch_id=p1["batch_id"]).exists()  # superseded
    assert BulkImportBatch.objects.filter(batch_id=p2["batch_id"], status="DRAFT").exists()


def test_confirm_respects_db_changes_since_preview(recruiter_user):
    # A row VALID at preview becomes an UPDATE if that candidate exists by confirm
    # time — the DB remains authoritative (draft data is not blindly created).
    prev = preview_candidates_excel(
        file=make_xlsx([_row(**{"Contact No.": "9116000030", "Email": "t@ex.com"})]), user=recruiter_user)
    upsert_candidate(data={"candidate_name": "Pre", "mobile": "9116000030", "email": "t@ex.com",
                           "is_willing_to_relocate": False}, user=recruiter_user)
    draft = BulkImportBatch.objects.get(batch_id=prev["batch_id"])
    rep = confirm_import_batch(batch=draft, user=recruiter_user)
    assert rep["updated"] == 1 and rep["created"] == 0


def test_purge_stale_drafts(recruiter_user):
    old = BulkImportBatch.objects.create(status="DRAFT", uploaded_by=recruiter_user,
                                         created_on=timezone.now() - datetime.timedelta(hours=48))
    fresh = BulkImportBatch.objects.create(status="DRAFT", uploaded_by=recruiter_user, created_on=timezone.now())
    n = purge_stale_draft_batches(older_than_hours=24)
    assert n >= 1
    assert not BulkImportBatch.objects.filter(batch_id=old.batch_id).exists()
    assert BulkImportBatch.objects.filter(batch_id=fresh.batch_id).exists()


def test_preview_then_confirm_via_api_and_draft_consumed(auth_client, recruiter_user):
    client = auth_client(recruiter_user)
    f = make_xlsx([_row(**{"Contact No.": "9116000020", "Email": "api@ex.com"})]); f.name = "test.xlsx"
    prev = client.post("/api/candidates/bulk-preview/", {"file": f}, format="multipart")
    assert prev.status_code == 200 and prev.data["batch_id"]
    bid = prev.data["batch_id"]
    conf = client.post("/api/candidates/bulk-upload/", {"batch_id": bid}, format="multipart")
    assert conf.status_code == 200 and conf.data["created"] == 1
    assert CandidateMaster.objects.filter(mobile="9116000020").exists()
    # Draft consumed (now COMPLETED) → a second confirm is rejected.
    assert client.post("/api/candidates/bulk-upload/", {"batch_id": bid}, format="multipart").status_code == 400


def test_import_history_excludes_drafts(auth_client, recruiter_user):
    BulkImportBatch.objects.create(status="DRAFT", uploaded_by=recruiter_user,
                                   created_on=timezone.now(), file_name="draft.xlsx")
    resp = auth_client(recruiter_user).get("/api/import-batches/")
    assert resp.status_code == 200 and all(r["status"] != "DRAFT" for r in resp.data["results"])


def test_confirm_twice_is_rejected(recruiter_user):
    prev = preview_candidates_excel(
        file=make_xlsx([_row(**{"Contact No.": "9116000040", "Email": "tw@ex.com"})]), user=recruiter_user)
    draft = BulkImportBatch.objects.get(batch_id=prev["batch_id"])
    r1 = confirm_import_batch(batch=draft, user=recruiter_user)
    assert r1["created"] == 1
    r2 = confirm_import_batch(batch=draft, user=recruiter_user)  # stale draft → claim fails
    assert r2["ok"] is False and "already used" in r2["error"].lower()
    assert CandidateMaster.objects.filter(mobile="9116000040").count() == 1  # no double import


# --- Negative-test audit: adversarial / misuse scenarios ---------------------

def test_hm_cannot_use_bulk_endpoints(auth_client, hm_user):
    client = auth_client(hm_user)
    f = make_xlsx([_row(**{"Contact No.": "9117000001", "Email": "hm@ex.com"})]); f.name = "t.xlsx"
    assert client.post("/api/candidates/bulk-preview/", {"file": f}, format="multipart").status_code == 403
    f2 = make_xlsx([_row(**{"Contact No.": "9117000002", "Email": "hm2@ex.com"})]); f2.name = "t.xlsx"
    assert client.post("/api/candidates/bulk-upload/", {"file": f2}, format="multipart").status_code == 403
    assert client.get("/api/candidates/unmapped-locations/").status_code == 403
    assert client.post("/api/candidates/reconcile-location/",
                       {"text": "X", "location_id": 1}, format="json").status_code == 403


def test_unauthenticated_bulk_is_rejected(api):
    f = make_xlsx([_row()]); f.name = "t.xlsx"
    assert api.post("/api/candidates/bulk-preview/", {"file": f}, format="multipart").status_code in (401, 403)


def test_cannot_confirm_another_users_draft(auth_client, recruiter_user, admin_user):
    prev = preview_candidates_excel(
        file=make_xlsx([_row(**{"Contact No.": "9117000010", "Email": "own@ex.com"})]), user=admin_user)
    bid = prev["batch_id"]
    resp = auth_client(recruiter_user).post("/api/candidates/bulk-upload/", {"batch_id": bid}, format="multipart")
    assert resp.status_code == 403
    assert BulkImportBatch.objects.get(batch_id=bid).status == "DRAFT"  # untouched


def test_recruiter_cannot_access_another_users_batch(auth_client, recruiter_user, admin_user):
    rep = import_candidates_excel(
        file=make_xlsx([_row(**{"Contact No.": "9117000020", "Email": "rp@ex.com"})]), user=admin_user)
    bid = rep["batch_id"]
    client = auth_client(recruiter_user)
    assert client.get(f"/api/import-batches/{bid}/report/").status_code == 404       # scoped out
    assert client.post(f"/api/import-batches/{bid}/rollback/").status_code == 404


def test_superseded_draft_confirm_is_rejected(auth_client, recruiter_user):
    raw = make_xlsx([_row(**{"Contact No.": "9117000030", "Email": "sup@ex.com"})]).getvalue()
    p1 = preview_candidates_excel(file=io.BytesIO(raw), user=recruiter_user)
    preview_candidates_excel(file=io.BytesIO(raw), user=recruiter_user)  # supersedes p1's draft
    resp = auth_client(recruiter_user).post("/api/candidates/bulk-upload/",
                                            {"batch_id": p1["batch_id"]}, format="multipart")
    assert resp.status_code == 400  # p1 draft no longer exists → graceful


def test_retry_direct_import_does_not_duplicate(recruiter_user):
    # Retrying the same file (e.g. after a lost response) updates, never duplicates.
    raw = make_xlsx([_row(**{"Contact No.": "9117000040", "Email": "retry@ex.com"})]).getvalue()
    import_candidates_excel(file=io.BytesIO(raw), user=recruiter_user)
    import_candidates_excel(file=io.BytesIO(raw), user=recruiter_user)  # retry
    assert CandidateMaster.objects.filter(mobile="9117000040").count() == 1


def test_interrupted_import_persists_progress(recruiter_user, monkeypatch):
    # Simulate a crash partway through: rows imported before the failure must be
    # reflected in the batch counts (not left at 0), and total_rows recorded upfront.
    real = services._classify_row
    calls = {"n": 0}

    def flaky(p, index):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("boom mid-import")
        return real(p, index)

    monkeypatch.setattr(services, "_classify_row", flaky)
    f = make_xlsx([_row(**{"Contact No.": f"911800000{i}", "Email": f"p{i}@ex.com"}) for i in range(4)])
    with pytest.raises(RuntimeError):
        import_candidates_excel(file=f, user=recruiter_user)

    b = BulkImportBatch.objects.filter(uploaded_by=recruiter_user).order_by("-batch_id").first()
    assert b is not None and b.status == "FAILED"
    assert b.total_rows == 4          # recorded before the loop
    assert b.created_count == 2       # rows 1-2 imported before the crash on row 3
    # Partial success preserved: those two candidates really exist.
    assert CandidateMaster.objects.filter(mobile__in=["9118000000", "9118000001"]).count() == 2


def test_periodic_checkpoint_flushes_counts(recruiter_user, monkeypatch):
    # With a tiny flush interval, counts are checkpointed mid-run — assert the last
    # checkpoint (before a crash) persisted, independent of the finalize save.
    monkeypatch.setattr(services, "PROGRESS_FLUSH_EVERY", 1)
    real = services._classify_row
    calls = {"n": 0}

    def flaky(p, index):
        calls["n"] += 1
        if calls["n"] == 4:
            raise RuntimeError("boom after checkpoints")
        return real(p, index)

    monkeypatch.setattr(services, "_classify_row", flaky)
    f = make_xlsx([_row(**{"Contact No.": f"911810000{i}", "Email": f"c{i}@ex.com"}) for i in range(5)])
    with pytest.raises(RuntimeError):
        import_candidates_excel(file=f, user=recruiter_user)
    b = BulkImportBatch.objects.filter(uploaded_by=recruiter_user).order_by("-batch_id").first()
    assert b.created_count == 3  # rows 1-3 checkpointed before the crash on row 4
