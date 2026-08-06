"""Database reset → restore the seeded demo BASELINE (dev/test only).

Restores the system to the exact state a recruiter needs to test the full
recruitment lifecycle from the beginning:

  * demo requirements exist and are **Open**; all positions **Open** (0 filled);
  * demo candidates exist at **New CV** with their **own** skills (never copied
    from a requirement);
  * candidates are put **under review** for requirements via explicit
    `candidate_requirement_review` tags (the Review Pool) — NO `jd_cv_mapping`
    (nobody has been shortlisted yet);
  * NO screenings, interviews, activity/communication logs, status history,
    outcomes, or closed requirements/positions.

Design (approved):
  * **Transactional-only reset (Option A).** Master/reference data is preserved;
    existing masters are never modified. The demo entities the baseline needs
    (clients, client managers, users, skills, locations, domains) are ensured via
    get_or_create — created only if missing, never overwritten.
  * The 15 transactional tables are emptied with a single
    `TRUNCATE … RESTART IDENTITY` (FK-closed set — verified: no master→transactional
    FK — so no CASCADE needed), then the baseline is rebuilt. All in one atomic
    transaction; idempotent (safe to run repeatedly).
  * No filesystem cleanup — the app stores no uploaded files.

Reuses `seed_demo`'s data definitions so there is a single source of demo data.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.db import connection, transaction
from django.utils import timezone

from admin_module.models import (
    CandidateMaster,
    CandidateRequirementReview,
    CandidateSkill,
    CandidateStatusMaster,
    ClientManagerMaster,
    ClientMaster,
    DomainMaster,
    LocationMaster,
    NoticePeriodMaster,
    PositionStatusMaster,
    PriorityMaster,
    ReqStatusMaster,
    ReqTypeMaster,
    RequirementPosition,
    RequirementTracker,
    RoleMaster,
    SkillMaster,
    SourceMaster,
    UserMaster,
    WorkModeMaster,
)
from admin_module.management.commands.seed_demo import (
    CANDIDATES,
    CLIENT_MANAGERS,
    CLIENTS,
    DOMAIN_SKILLS,
    EXTRA_CANDIDATES,
    LOCATIONS,
    MODE_POOL,
    NP_POOL,
    PASSWORD,
    REQUIREMENTS,
    SKILLS,
    SOURCE_POOL,
    TEAM,
    _email,
    _mobile,
)
from admin_module.management.commands.seed_demo import EMPLOYERS, QUALIFICATIONS
from core.constants import CandidateStatus, PositionStatus, ReqStatus, ReviewStatus

# The 15 transactional tables emptied on reset (child→parent order for the DELETE
# fallback; TRUNCATE resolves intra-set FKs itself). This set is FK-CLOSED: no
# preserved master references any of these, so TRUNCATE needs no CASCADE.
TRANSACTIONAL_TABLES = [
    "candidate_requirement_review",
    "status_change_history",
    "screening",
    "requirement_position",
    "candidate_profile_audit",
    "candidate_duplicate_review",
    "candidate_skill",
    "candidate_interaction",
    "communication_log",
    "cv_document",
    "activity_log",
    "jd_cv_mapping",
    "candidate_master",
    "bulk_import_batch",
    "requirement_tracker",
]


def clear_transactional_data():
    """Empty every transactional table + reset identities. Masters untouched."""
    tables = ", ".join(f"ats.{t}" for t in TRANSACTIONAL_TABLES)
    with connection.cursor() as cursor:
        cursor.execute(f"TRUNCATE TABLE {tables} RESTART IDENTITY")


def _ensure_demo_masters(user, now):
    """Ensure the demo master/reference entities the baseline references EXIST,
    without modifying any that are already present (Option A). Returns the lookup
    maps used by the builder. Reference lookups seeded by `ats insert data 2.sql`
    (notice periods, work modes, sources, priorities, req types, statuses) must
    already exist."""
    roles = {r.role_code: r for r in RoleMaster.objects.all()}

    clients = {}
    for code, name, industry in CLIENTS:
        obj, _ = ClientMaster.objects.get_or_create(
            client_code=code,
            defaults={"client_name": name, "industry": industry, "is_active": True, "created_on": now},
        )
        clients[name] = obj

    domains = {}
    for _n, domain in SKILLS:
        if domain not in domains:
            obj, _ = DomainMaster.objects.get_or_create(
                domain_name=domain, defaults={"is_active": True, "created_on": now})
            domains[domain] = obj
    skills = {}
    for name, domain in SKILLS:
        obj, _ = SkillMaster.objects.get_or_create(
            skill_name=name, defaults={"domain": domains[domain], "is_active": True, "created_on": now})
        skills[name] = obj

    locations = {}
    for city, state in LOCATIONS:
        obj, _ = LocationMaster.objects.get_or_create(
            city=city, state=state, defaults={"country": "India", "is_active": True, "created_on": now})
        locations[city] = obj

    hashed = make_password(PASSWORD)
    users = {}
    for username, full_name, email, mobile, role_code in TEAM:
        obj, _ = UserMaster.objects.get_or_create(
            username=username,
            defaults={"full_name": full_name, "email": email, "mobile": mobile,
                      "role": roles[role_code], "is_active": True,
                      "password_hash": hashed, "created_on": now},
        )
        users[username] = obj

    for mgr_name, client_code, designation in CLIENT_MANAGERS:
        client = next(c for c in clients.values() if c.client_code == client_code)
        first = mgr_name.lower().split()[0]
        domain = client.client_name.lower().split()[0]
        ClientManagerMaster.objects.get_or_create(
            client=client, manager_name=mgr_name,
            defaults={"email": f"{first}.{client_code.lower()}@{domain}.com",
                      "designation": designation, "is_active": True, "created_on": now},
        )

    return {
        "clients": clients, "skills": skills, "locations": locations, "users": users,
        "notice": {n.np_name: n for n in NoticePeriodMaster.objects.all()},
        "modes": {m.work_mode_name: m for m in WorkModeMaster.objects.all()},
        "sources": {s.source_name: s for s in SourceMaster.objects.all()},
        "priorities": {p.priority_name: p for p in PriorityMaster.objects.all()},
        "req_types": {t.req_type_code: t for t in ReqTypeMaster.objects.all()},
        "req_status": {s.status_code: s for s in ReqStatusMaster.objects.all()},
        "pos_status": {s.status_code: s for s in PositionStatusMaster.objects.all()},
        "candidate_status": {s.status_code: s for s in CandidateStatusMaster.objects.all()},
    }


def build_demo_baseline(user):
    """Rebuild the initial-state demo transactional data. Assumes the transactional
    tables were just cleared. Returns a summary dict."""
    now = timezone.now()
    m = _ensure_demo_masters(user, now)
    open_status = m["req_status"][ReqStatus.OPEN]
    open_seat = m["pos_status"][PositionStatus.OPEN]
    new_cv = m["candidate_status"][CandidateStatus.NEW_CV]

    # --- Requirements (all OPEN) + Open seats -------------------------------- #
    req_by_domain = {}
    for ri, spec in enumerate(REQUIREMENTS, start=1):
        client = m["clients"][spec["client"]]
        mgr = ClientManagerMaster.objects.filter(client=client).first()
        req_date = (now - timedelta(days=10)).date()
        req = RequirementTracker.objects.create(
            req_tracker_no=f"REQ-2026-{ri:03d}",
            jd_serial_number=f"JD-2026-{ri:05d}",
            client_req_id=f"{client.client_code}-{1000 + ri}",
            client=client, client_mgr=mgr,
            hiring_mgr=m["users"][spec["hm"]], recruiter=m["users"][spec["recruiter"]],
            req_type=m["req_types"][spec["type"]], jd_role_name=spec["role"],
            location=m["locations"][spec["city"]],
            exp_min=Decimal(spec["exp"][0]), exp_max=Decimal(spec["exp"][1]),
            jd_rate_lpa=Decimal(spec["rate"]), np=m["notice"][spec["np"]],
            req_status=open_status, priority=m["priorities"][spec["priority"]],
            positions_open=spec["open"], positions_filled=0,
            skill1=m["skills"][spec["skills"][0]], skill2=m["skills"][spec["skills"][1]],
            skill3=m["skills"][spec["skills"][2]],
            req_date=req_date, assigned_date=req_date,
            target_fill_date=(now + timedelta(days=45)).date(),  # never expired
            created_by=m["users"][spec["hm"]], created_on=now,
            jd_text=spec["jd"], is_active=True,
        )
        RequirementPosition.objects.bulk_create([
            RequirementPosition(req=req, position_no=pi, position_status=open_seat,
                                is_active=True, created_by=user, created_on=now)
            for pi in range(1, spec["open"] + 1)
        ])
        req_by_domain[spec["domain"]] = req

    # --- Candidates (New CV) + their OWN skills ------------------------------ #
    candidates = []
    for i, (name, domain, exp_min, exp_max, ctc_cur, ctc_exp, city) in enumerate(CANDIDATES + EXTRA_CANDIDATES):
        cand = CandidateMaster.objects.create(
            candidate_status=new_cv, cv_serial=f"CV-{i + 1:06d}",
            candidate_name=name, mobile=_mobile(i), email=_email(name, i),
            exp_min=Decimal(exp_min), exp_max=Decimal(exp_max),
            current_location=m["locations"].get(city), preferred_location=m["locations"].get(city),
            notice_period=m["notice"].get(NP_POOL[i % len(NP_POOL)]),
            work_mode=m["modes"].get(MODE_POOL[i % len(MODE_POOL)]),
            current_company=EMPLOYERS[i % len(EMPLOYERS)],
            current_ctc_lpa=Decimal(ctc_cur), expected_ctc_lpa=Decimal(ctc_exp),
            highest_qualification=QUALIFICATIONS[i % len(QUALIFICATIONS)],
            source=m["sources"].get(SOURCE_POOL[i % len(SOURCE_POOL)]),
            is_duplicate=False, is_willing_to_relocate=bool(i % 2),
            uploaded_by=user, is_active=True, created_by=user, created_on=now,
        )
        # Real skills from the candidate's domain (their OWN profile), never the req.
        CandidateSkill.objects.bulk_create([
            CandidateSkill(candidate=cand, skill=m["skills"][s], created_on=now)
            for s in DOMAIN_SKILLS.get(domain, [])
        ])
        candidates.append((cand, domain))

    # --- Review Pool: tag each candidate to the requirement of their domain --- #
    tags = 0
    for cand, domain in candidates:
        req = req_by_domain.get(domain)
        if req is None:
            continue
        CandidateRequirementReview.objects.create(
            candidate=cand, req=req, status=ReviewStatus.ACTIVE,
            tagged_by=user, tagged_on=now, created_on=now,
        )
        tags += 1

    return {
        "requirements": len(REQUIREMENTS),
        "candidates": len(candidates),
        "review_tags": tags,
    }


@transaction.atomic
def reset_to_baseline(user):
    """Atomic reset: clear all transactional data, then rebuild the initial-state
    demo baseline (masters preserved). Idempotent."""
    clear_transactional_data()
    summary = build_demo_baseline(user)
    return summary
