"""
Seed realistic, production-quality demo data for the Speegile ATS.

Populates the full recruiter workflow with authentic Indian business data —
real names, IT companies, cities, professional emails, valid mobile numbers,
believable experience/CTC/notice, and a pipeline spread across every stage so
every screen (dashboards, review pool, JD compose/preview, tracker, screening
board) has meaningful content.

Idempotent: master/reference rows are upserted by natural key; transactional
rows (candidates, requirements, mappings, logs) are cleared and rebuilt on each
run. Demo logins keep the shared password.

    python manage.py seed_demo
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from admin_module.models import (
    ActivityLog,
    CandidateInteraction,
    CandidateMaster,
    CandidateSkill,
    ClientManagerMaster,
    ClientMaster,
    CommunicationLog,
    CvDocument,
    ApplicationStatusMaster,
    CandidateStatusMaster,
    DomainMaster,
    JdCvMapping,
    LocationMaster,
    PositionStatusMaster,
    RequirementPosition,
    NoticePeriodMaster,
    PriorityMaster,
    RejectionReasonMaster,
    RequirementTracker,
    ReqTypeMaster,
    RoleMaster,
    Screening,
    ScreeningModeMaster,
    SkillMaster,
    SourceMaster,
    UserMaster,
    WorkModeMaster,
)
from core.constants import ApplicationStatus, CandidateStatus, InteractionType, ReqStatus, Roles

PASSWORD = "Speegile@123"

# --------------------------------------------------------------------------- #
#  Master / reference data (idempotent, upserted by natural key)
# --------------------------------------------------------------------------- #

# Clients — well-known Indian IT services firms.
CLIENTS = [
    ("TCS", "Tata Consultancy Services", "IT Services"),
    ("INFY", "Infosys", "IT Services"),
    ("WIP", "Wipro", "IT Services"),
    ("HCL", "HCL Technologies", "IT Services"),
    ("TECHM", "Tech Mahindra", "IT Services"),
    ("LTIM", "LTIMindtree", "IT Services"),
    ("COG", "Cognizant", "IT Services"),
    ("CAP", "Capgemini India", "Consulting"),
    ("ACC", "Accenture India", "Consulting"),
    ("PERSIS", "Persistent Systems", "Product Engineering"),
]

# Client managers — one realistic SPOC per client (name, client_code, designation).
CLIENT_MANAGERS = [
    ("Anand Krishnan", "TCS", "Talent Acquisition Lead"),
    ("Meera Subramanian", "INFY", "Senior TA Partner"),
    ("Rohit Bhatt", "WIP", "Recruitment Manager"),
    ("Shalini Pillai", "HCL", "TA Specialist"),
    ("Karthik Iyer", "TECHM", "Hiring Lead"),
    ("Nisha Agarwal", "LTIM", "Talent Partner"),
    ("Vivek Saxena", "COG", "Staffing Manager"),
    ("Pooja Nair", "CAP", "TA Lead"),
    ("Rahul Khanna", "ACC", "Recruitment Lead"),
    ("Sneha Joshi", "PERSIS", "People Partner"),
]

# Skills (skill_name, domain). Existing ones are upserted; the rest are added.
SKILLS = [
    ("Python", "Programming"), ("Java", "Programming"), ("JavaScript", "Programming"),
    ("TypeScript", "Programming"), ("SQL", "Database"), ("PostgreSQL", "Database"),
    ("MongoDB", "Database"), ("ReactJS", "Frontend"), ("Angular", "Frontend"),
    ("Node.js", "Backend"), ("Django", "Backend"), ("Spring Boot", "Backend"),
    ("Microservices", "Architecture"), ("REST APIs", "Backend"), ("AWS", "Cloud"),
    ("Docker", "DevOps"), ("Kubernetes", "DevOps"), ("Jenkins", "DevOps"),
    ("Selenium", "Testing"), ("Power BI", "Analytics"), ("Tableau", "Analytics"),
    ("Excel", "Analytics"), ("Data Analysis", "Analytics"), ("Machine Learning", "Data Science"),
    ("Git", "Tools"),
]

# Locations (city, state) — major Indian tech hubs.
LOCATIONS = [
    ("Mumbai", "Maharashtra"), ("Pune", "Maharashtra"), ("Nagpur", "Maharashtra"),
    ("Bangalore", "Karnataka"), ("Hyderabad", "Telangana"), ("Chennai", "Tamil Nadu"),
    ("Delhi", "Delhi"), ("Noida", "Uttar Pradesh"), ("Gurugram", "Haryana"),
    ("Ahmedabad", "Gujarat"), ("Kolkata", "West Bengal"),
]

# Additional team members (username, full_name, email, mobile, role_code).
TEAM = [
    ("priya.sharma", "Priya Sharma", "priya.sharma@speegile.com", "9820011001", Roles.ADMIN),
    ("ankit.desai", "Ankit Desai", "ankit.desai@speegile.com", "9820011004", Roles.HIRING_MANAGER),
    ("kavya.nair", "Kavya Nair", "kavya.nair@speegile.com", "9820011005", Roles.HIRING_MANAGER),
    ("vikram.reddy", "Vikram Reddy", "vikram.reddy@speegile.com", "9820011006", Roles.HIRING_MANAGER),
    ("rajeev.mehta", "Rajeev Mehta", "rajeev.mehta@speegile.com", "9820011002", Roles.RECRUITER),
    ("sneha.kulkarni", "Sneha Kulkarni", "sneha.kulkarni@speegile.com", "9820011007", Roles.RECRUITER),
    ("arjun.menon", "Arjun Menon", "arjun.menon@speegile.com", "9820011008", Roles.RECRUITER),
]

EMAIL_DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "rediffmail.com"]
EMPLOYERS = [
    "Tata Consultancy Services", "Infosys", "Wipro", "HCL Technologies", "Tech Mahindra",
    "Cognizant", "Capgemini", "Accenture", "LTIMindtree", "Persistent Systems",
    "Mphasis", "Coforge", "Birlasoft", "Zensar Technologies",
]
QUALIFICATIONS = [
    "B.E. Computer Science", "B.Tech Information Technology", "B.Tech CSE", "MCA",
    "B.Sc Computer Science", "M.Tech CSE", "BCA", "M.Sc Information Technology", "MBA Systems",
]

# Skill bundles per domain — every candidate in a domain matches the requirement.
DOMAIN_SKILLS = {
    "java": ["Java", "Spring Boot", "Microservices"],
    "react": ["ReactJS", "JavaScript", "TypeScript"],
    "fullstack": ["ReactJS", "Node.js", "SQL"],
    "python": ["Python", "Django", "PostgreSQL"],
    "data": ["SQL", "Power BI", "Excel"],
    "ba": ["SQL", "Excel", "Data Analysis"],
    "devops": ["AWS", "Docker", "Kubernetes"],
    "qa": ["Selenium", "Java", "SQL"],
    "dataeng": ["Python", "SQL", "AWS"],
}

# Candidates: (name, domain, exp_min, exp_max, ctc_current, ctc_expected, city)
CANDIDATES = [
    # Java
    ("Rahul Sharma", "java", 6, 9, 16, 24, "Pune"),
    ("Amit Verma", "java", 5, 8, 13, 20, "Pune"),
    ("Karan Mehta", "java", 7, 10, 20, 30, "Mumbai"),
    ("Sandeep Joshi", "java", 4, 7, 11, 17, "Nagpur"),
    ("Pooja Deshpande", "java", 6, 9, 15, 23, "Pune"),
    # React
    ("Priya Patel", "react", 3, 6, 9, 15, "Bangalore"),
    ("Neha Gupta", "react", 4, 7, 12, 18, "Bangalore"),
    ("Rohan Kulkarni", "react", 2, 5, 7, 12, "Pune"),
    ("Ananya Rao", "react", 5, 8, 14, 21, "Hyderabad"),
    # Full stack
    ("Vivek Menon", "fullstack", 4, 7, 12, 19, "Noida"),
    ("Shreya Banerjee", "fullstack", 5, 8, 14, 22, "Kolkata"),
    ("Aditya Nair", "fullstack", 3, 6, 10, 16, "Bangalore"),
    # Python
    ("Sneha Iyer", "python", 3, 7, 11, 18, "Pune"),
    ("Divya Krishnan", "python", 4, 6, 12, 18, "Chennai"),
    ("Manoj Pillai", "python", 5, 8, 15, 23, "Hyderabad"),
    # Data analyst
    ("Meghna Reddy", "data", 2, 5, 7, 13, "Hyderabad"),
    ("Suresh Babu", "data", 3, 6, 9, 15, "Chennai"),
    ("Kavita Singh", "data", 4, 7, 11, 17, "Gurugram"),
    # Business analyst
    ("Manish Agarwal", "ba", 5, 8, 14, 21, "Gurugram"),
    ("Ritu Sharma", "ba", 4, 7, 12, 18, "Delhi"),
    ("Deepak Nair", "ba", 6, 9, 17, 25, "Mumbai"),
    # DevOps
    ("Arjun Pillai", "devops", 5, 8, 16, 25, "Chennai"),
    ("Nikhil Shetty", "devops", 4, 7, 13, 20, "Bangalore"),
    ("Faisal Khan", "devops", 6, 9, 18, 27, "Hyderabad"),
    # QA
    ("Swati Joshi", "qa", 3, 6, 8, 14, "Mumbai"),
    ("Rohit Choudhary", "qa", 4, 7, 11, 17, "Pune"),
    # Data engineering
    ("Ankita Bose", "dataeng", 5, 9, 16, 26, "Bangalore"),
    ("Harish Menon", "dataeng", 6, 9, 19, 28, "Bangalore"),
    # A couple flagged as fake during screening (realistic noise)
    ("Sumit Yadav", "java", 8, 12, 28, 42, "Delhi"),
    ("Ramesh Gupta", "data", 1, 3, 4, 9, "Noida"),
]

# Fresh, unmapped candidates (~2 per domain) — they stay New-CV and populate each
# requirement's "New CVs to review" pool so the review screen looks realistic.
EXTRA_CANDIDATES = [
    ("Vishal Rane", "java", 5, 8, 13, 20, "Pune"),
    ("Gaurav Saxena", "java", 4, 7, 11, 17, "Noida"),
    ("Tanvi Shah", "react", 3, 6, 9, 15, "Ahmedabad"),
    ("Akash Jain", "react", 4, 7, 12, 18, "Bangalore"),
    ("Nandini Pillai", "fullstack", 4, 7, 13, 20, "Chennai"),
    ("Sahil Kapoor", "fullstack", 3, 6, 10, 16, "Gurugram"),
    ("Pallavi Naik", "python", 4, 7, 12, 19, "Pune"),
    ("Imran Sheikh", "python", 5, 8, 15, 22, "Hyderabad"),
    ("Sneha Pawar", "data", 2, 5, 7, 13, "Mumbai"),
    ("Yash Agrawal", "data", 3, 6, 9, 15, "Kolkata"),
    ("Komal Bhise", "ba", 4, 7, 12, 18, "Pune"),
    ("Rohan Desai", "ba", 5, 8, 15, 22, "Mumbai"),
    ("Aniket Patil", "devops", 4, 7, 14, 21, "Pune"),
    ("Zoya Khan", "devops", 5, 8, 16, 24, "Bangalore"),
    ("Preeti Kulkarni", "qa", 3, 6, 8, 14, "Nagpur"),
    ("Varun Malhotra", "qa", 4, 7, 11, 17, "Delhi"),
    ("Sanya Mehra", "dataeng", 5, 8, 16, 25, "Bangalore"),
    ("Ravi Varma", "dataeng", 6, 9, 19, 28, "Hyderabad"),
]

# Requirements: dict per requisition. `pipeline` maps candidate name → stage.
NEW = CandidateStatus.NEW_CV
REQUIREMENTS = [
    {
        "client": "Tata Consultancy Services", "type": "FTE", "role": "Senior Java Developer",
        "city": "Pune", "exp": (6, 10), "rate": 24, "np": "30 Days", "priority": "High",
        "status": ReqStatus.OPEN, "open": 2, "domain": "java",
        "skills": ["Java", "Spring Boot", "Microservices"],
        "recruiter": "rajeev.mehta", "hm": "ankit.desai",
        "jd": ("Seeking a Senior Java Developer to design and build scalable "
               "microservices for a large banking client. Strong Spring Boot, REST "
               "and SQL experience required; exposure to cloud deployment a plus."),
        "pipeline": {
            "Rahul Sharma": ApplicationStatus.OK_TO_PROCEED,
            "Karan Mehta": ApplicationStatus.SCREENING_SCHEDULED,
            "Pooja Deshpande": ApplicationStatus.JD_EMAIL_SENT,
            "Amit Verma": ApplicationStatus.SHORTLISTED,
            "Sumit Yadav": CandidateStatus.FAKE,
        },
    },
    {
        "client": "Infosys", "type": "FTE", "role": "React Developer",
        "city": "Bangalore", "exp": (3, 6), "rate": 16, "np": "60 Days", "priority": "High",
        "status": ReqStatus.OPEN, "open": 3, "domain": "react",
        "skills": ["ReactJS", "JavaScript", "TypeScript"],
        "recruiter": "sneha.kulkarni", "hm": "kavya.nair",
        "jd": ("React Developer for a digital commerce platform. Build responsive UIs "
               "with React, TypeScript and modern tooling. Collaborate closely with "
               "design and backend teams in an agile setup."),
        "pipeline": {
            "Neha Gupta": ApplicationStatus.SCREENING_SCHEDULED,
            "Ananya Rao": ApplicationStatus.JD_EMAIL_SENT,
            "Priya Patel": ApplicationStatus.SHORTLISTED,
            "Rohan Kulkarni": ApplicationStatus.NOT_SUITABLE,
        },
    },
    {
        "client": "Wipro", "type": "TPR", "role": "Data Analyst",
        "city": "Hyderabad", "exp": (2, 5), "rate": 13, "np": "Immediate", "priority": "Medium",
        "status": ReqStatus.OPEN, "open": 2, "domain": "data",
        "skills": ["SQL", "Power BI", "Excel"],
        "recruiter": "rajeev.mehta", "hm": "vikram.reddy",
        "jd": ("Data Analyst to build dashboards and reports for a retail analytics "
               "team. Strong SQL and Power BI skills; ability to translate business "
               "questions into data insights."),
        "pipeline": {
            "Meghna Reddy": ApplicationStatus.OK_TO_PROCEED,
            "Suresh Babu": ApplicationStatus.SHORTLISTED,
            "Kavita Singh": ApplicationStatus.JD_EMAIL_SENT,
            "Ramesh Gupta": ApplicationStatus.REJECTED,
        },
    },
    {
        "client": "HCL Technologies", "type": "FTE", "role": "DevOps Engineer",
        "city": "Chennai", "exp": (4, 8), "rate": 22, "np": "30 Days", "priority": "High",
        "status": ReqStatus.OPEN, "open": 2, "domain": "devops",
        "skills": ["AWS", "Docker", "Kubernetes"],
        "recruiter": "sneha.kulkarni", "hm": "ankit.desai",
        "jd": ("DevOps Engineer to own CI/CD pipelines and container orchestration on "
               "AWS. Hands-on with Docker, Kubernetes and infrastructure automation."),
        "pipeline": {
            "Arjun Pillai": ApplicationStatus.SCREENING_SCHEDULED,
            "Faisal Khan": ApplicationStatus.SHORTLISTED,
            "Nikhil Shetty": ApplicationStatus.JD_EMAIL_SENT,
        },
    },
    {
        "client": "Tech Mahindra", "type": "FTE", "role": "Python Backend Developer",
        "city": "Pune", "exp": (3, 7), "rate": 18, "np": "45 Days", "priority": "Medium",
        "status": ReqStatus.OPEN, "open": 2, "domain": "python",
        "skills": ["Python", "Django", "PostgreSQL"],
        "recruiter": "arjun.menon", "hm": "kavya.nair",
        "jd": ("Python Backend Developer to build REST APIs with Django and PostgreSQL "
               "for a logistics product. Clean, testable code and good API design "
               "sensibilities expected."),
        "pipeline": {
            "Sneha Iyer": ApplicationStatus.SHORTLISTED,
            "Divya Krishnan": ApplicationStatus.SHORTLISTED,
            "Manoj Pillai": ApplicationStatus.JD_EMAIL_SENT,
        },
    },
    {
        "client": "LTIMindtree", "type": "TPR", "role": "QA Automation Engineer",
        "city": "Mumbai", "exp": (3, 6), "rate": 15, "np": "30 Days", "priority": "Medium",
        "status": ReqStatus.OPEN, "open": 1, "domain": "qa",
        "skills": ["Selenium", "Java", "SQL"],
        "recruiter": "rajeev.mehta", "hm": "vikram.reddy",
        "jd": ("QA Automation Engineer to design and maintain Selenium test suites for "
               "a web application. Java scripting and SQL validation experience needed."),
        "pipeline": {
            "Swati Joshi": ApplicationStatus.DROPPED,
            "Rohit Choudhary": ApplicationStatus.SHORTLISTED,
        },
    },
    {
        "client": "Cognizant", "type": "FTE", "role": "Business Analyst",
        "city": "Gurugram", "exp": (4, 8), "rate": 19, "np": "60 Days", "priority": "Medium",
        "status": ReqStatus.OPEN, "open": 1, "domain": "ba",
        "skills": ["SQL", "Excel", "Data Analysis"],
        "recruiter": "sneha.kulkarni", "hm": "ankit.desai",
        "jd": ("Business Analyst to bridge business and engineering for an insurance "
               "client. Requirements gathering, SQL-based analysis and stakeholder "
               "communication are key."),
        "pipeline": {
            "Manish Agarwal": ApplicationStatus.JD_EMAIL_SENT,
            "Ritu Sharma": ApplicationStatus.NO_RESPONSE,
        },
    },
    {
        "client": "Capgemini India", "type": "FTE", "role": "Full Stack Developer",
        "city": "Noida", "exp": (4, 7), "rate": 20, "np": "30 Days", "priority": "High",
        "status": ReqStatus.OPEN, "open": 2, "domain": "fullstack",
        "skills": ["ReactJS", "Node.js", "SQL"],
        "recruiter": "arjun.menon", "hm": "kavya.nair",
        "jd": ("Full Stack Developer (React + Node.js) for a SaaS product. Comfortable "
               "across the stack, from UI components to API endpoints and SQL queries."),
        "pipeline": {
            "Vivek Menon": ApplicationStatus.SHORTLISTED,
            "Shreya Banerjee": ApplicationStatus.JD_EMAIL_SENT,
        },
    },
    {
        "client": "Accenture India", "type": "FTE", "role": "Senior Data Engineer",
        "city": "Bangalore", "exp": (5, 9), "rate": 28, "np": "90 Days", "priority": "Low",
        "status": ReqStatus.ASSIGNED, "open": 1, "domain": "dataeng",
        "skills": ["Python", "SQL", "AWS"],
        "recruiter": "rajeev.mehta", "hm": "vikram.reddy",
        "jd": ("Senior Data Engineer to build data pipelines on AWS for an analytics "
               "platform. Strong Python and SQL; experience with large-scale data "
               "processing preferred."),
        "pipeline": {
            "Harish Menon": ApplicationStatus.SHORTLISTED,
        },
    },
]

# Notice / work-mode / source pools to vary candidate profiles deterministically.
NP_POOL = ["Immediate", "15 Days", "30 Days", "45 Days", "60 Days", "90 Days"]
MODE_POOL = ["Work From Office", "Hybrid", "Work From Home"]
SOURCE_POOL = ["Naukri", "LinkedIn", "Referral", "Apna Jobs"]
CV_SUFFIXES = ["Resume", "CV", "Profile", "Resume_2026"]
REJECTION_FOR = {
    ApplicationStatus.NOT_SUITABLE: "Skills mismatch",
    ApplicationStatus.REJECTED: "Failed screening",
    ApplicationStatus.DROPPED: "Candidate not interested",
    ApplicationStatus.NO_RESPONSE: "Unreachable",
}

# Post-split model: a pipeline dict value that is an OUTCOME maps to (the stage it
# was recorded at, the outcome). Stage values map to themselves (no outcome yet).
_OUTCOME_PRIOR_STAGE = {
    ApplicationStatus.NOT_SUITABLE: ApplicationStatus.SHORTLISTED,
    ApplicationStatus.REJECTED: ApplicationStatus.SCREENING_SCHEDULED,
    ApplicationStatus.DROPPED: ApplicationStatus.JD_EMAIL_SENT,
    ApplicationStatus.NO_RESPONSE: ApplicationStatus.JD_EMAIL_SENT,
}
_ADVANCE_OUTCOME = {ApplicationStatus.OK_TO_PROCEED: ApplicationStatus.PASSED}


def _email(name, i):
    first, *rest = name.lower().split()
    last = rest[-1] if rest else "candidate"
    return f"{first}.{last}@{EMAIL_DOMAINS[i % len(EMAIL_DOMAINS)]}"


def _mobile(i):
    prefix = [98, 99, 97, 96, 91, 90, 88, 87, 80, 79, 76, 73, 70, 63][i % 14]
    return f"{prefix}{30000000 + i:08d}"


class Command(BaseCommand):
    help = "Seed realistic Indian demo data across the full recruiter workflow."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        now = timezone.now()
        self.stdout.write("Seeding master / reference data…")

        roles = {r.role_code: r for r in RoleMaster.objects.all()}

        # --- Clients ---
        clients = {}
        for code, name, industry in CLIENTS:
            obj, _ = ClientMaster.objects.update_or_create(
                client_code=code,
                defaults={"client_name": name, "industry": industry, "is_active": True,
                          "created_on": now},
            )
            clients[name] = obj

        # --- Domains (classification master) + Skills ---
        domains = {}
        for _name, domain in SKILLS:
            if domain not in domains:
                obj, _ = DomainMaster.objects.update_or_create(
                    domain_name=domain,
                    defaults={"is_active": True, "created_on": now},
                )
                domains[domain] = obj
        skills = {}
        for name, domain in SKILLS:
            obj, _ = SkillMaster.objects.update_or_create(
                skill_name=name,
                defaults={"domain": domains[domain], "is_active": True, "created_on": now},
            )
            skills[name] = obj

        # --- Locations ---
        locations = {}
        for city, state in LOCATIONS:
            obj, _ = LocationMaster.objects.update_or_create(
                city=city, state=state,
                defaults={"country": "India", "is_active": True, "created_on": now},
            )
            locations[city] = obj

        # --- Notice / work-mode / source / priority / req-type / screening lookups ---
        notice = {n.np_name: n for n in NoticePeriodMaster.objects.all()}
        modes = {m.work_mode_name: m for m in WorkModeMaster.objects.all()}
        sources = {s.source_name: s for s in SourceMaster.objects.all()}
        priorities = {p.priority_name: p for p in PriorityMaster.objects.all()}
        req_types = {t.req_type_code: t for t in ReqTypeMaster.objects.all()}
        screening_modes = list(ScreeningModeMaster.objects.filter(is_active=True))
        rejection_reasons = {r.reason_name: r for r in RejectionReasonMaster.objects.all()}
        candidate_status = {s.status_code: s for s in CandidateStatusMaster.objects.all()}
        app_stage = {s.status_code: s for s in ApplicationStatusMaster.objects.all()}
        from admin_module.models import ReqStatusMaster
        req_status = {s.status_code: s for s in ReqStatusMaster.objects.all()}
        pos_status = {s.status_code: s for s in PositionStatusMaster.objects.all()}

        # --- Team (users) ---
        hashed = make_password(PASSWORD)
        users = {}
        for username, full_name, email, mobile, role_code in TEAM:
            obj, _ = UserMaster.objects.update_or_create(
                username=username,
                defaults={"full_name": full_name, "email": email, "mobile": mobile,
                          "role": roles[role_code], "is_active": True,
                          "password_hash": hashed, "created_on": now},
            )
            users[username] = obj
        admin_user = users["priya.sharma"]

        # --- Client managers (after clients exist) ---
        for mgr_name, client_code, designation in CLIENT_MANAGERS:
            client = next(c for c in clients.values() if c.client_code == client_code)
            first = mgr_name.lower().split()[0]
            domain = client.client_name.lower().split()[0]
            ClientManagerMaster.objects.update_or_create(
                client=client, manager_name=mgr_name,
                defaults={"email": f"{first}.{client_code.lower()}@{domain}.com",
                          "designation": designation, "is_active": True, "created_on": now},
            )

        # --- Clean junk + transactional data (rebuilt below) ---
        self.stdout.write("Clearing previous transactional + test data…")
        ActivityLog.objects.all().delete()  # FK → requirement_tracker / candidate_master
        Screening.objects.all().delete()  # FK → jd_cv_mapping / screening_mode_master
        RequirementPosition.objects.all().delete()  # FK → requirement_tracker / jd_cv_mapping
        CommunicationLog.objects.all().delete()
        CandidateInteraction.objects.all().delete()
        from admin_module.models import CandidateDuplicateReview
        CandidateDuplicateReview.objects.all().delete()  # FK → candidate_master
        JdCvMapping.objects.all().delete()
        CandidateSkill.objects.all().delete()
        CvDocument.objects.all().delete()
        CandidateMaster.objects.all().delete()
        RequirementTracker.objects.all().delete()
        ClientManagerMaster.objects.filter(manager_name="ZZ POC").delete()
        ClientMaster.objects.filter(client_code="ZZT").delete()

        # --- Candidates + skills + CV documents ---
        self.stdout.write("Creating candidates…")
        candidates = {}
        for i, (name, domain, exp_min, exp_max, ctc_cur, ctc_exp, city) in enumerate(CANDIDATES + EXTRA_CANDIDATES):
            cand = CandidateMaster.objects.create(
                candidate_status=candidate_status[NEW],  # refined after mappings
                cv_serial=f"CV-{i + 1:06d}",
                candidate_name=name,
                mobile=_mobile(i),
                email=_email(name, i),
                exp_min=Decimal(exp_min), exp_max=Decimal(exp_max),
                current_location=locations.get(city),
                preferred_location=locations.get(city),
                notice_period=notice.get(NP_POOL[i % len(NP_POOL)]),
                work_mode=modes.get(MODE_POOL[i % len(MODE_POOL)]),
                current_company=EMPLOYERS[i % len(EMPLOYERS)],
                current_ctc_lpa=Decimal(ctc_cur), expected_ctc_lpa=Decimal(ctc_exp),
                highest_qualification=QUALIFICATIONS[i % len(QUALIFICATIONS)],
                source=sources.get(SOURCE_POOL[i % len(SOURCE_POOL)]),
                is_duplicate=False, is_willing_to_relocate=bool(i % 2),
                uploaded_by=users["rajeev.mehta"], is_active=True,
                created_by=users["rajeev.mehta"],
                created_on=now - timedelta(days=30 - (i % 25)),
            )
            candidates[name] = cand

            for skill_name in DOMAIN_SKILLS[domain]:
                CandidateSkill.objects.create(candidate=cand, skill=skills[skill_name], created_on=cand.created_on)

            fname = f"{name.replace(' ', '_')}_{CV_SUFFIXES[i % len(CV_SUFFIXES)]}.pdf"
            CvDocument.objects.create(
                candidate=cand, file_name=fname, stored_file_name=f"{cand.cv_serial}_{fname}",
                file_path=f"uploads/cvs/{cand.cv_serial}_{fname}", file_type="application/pdf",
                file_size=180_000 + i * 4096, active_version=True,
                upload_date=cand.created_on, uploaded_by=users["rajeev.mehta"],
            )

        # --- Requirements + pipeline ---
        self.stdout.write("Creating requirements + pipeline…")
        # Requirement status is DERIVED from the lifecycle (never hardcoded) using
        # the SAME production functions, so the seed can't produce impossible
        # combinations (e.g. Open with 1/2 filled). Manual states stay explicit.
        from requirements.positions import MANUAL_REQ_STATES, recompute_requirement
        from requirements.services import open_requirement_on_first_link

        mapped_names, fake_names, joined_names = set(), set(), set()
        for ri, req in enumerate(REQUIREMENTS, start=1):
            recruiter = users[req["recruiter"]]
            hm = users[req["hm"]]
            client = clients[req["client"]]
            mgr = ClientManagerMaster.objects.filter(client=client).first()
            req_date = (now - timedelta(days=40 - ri * 3)).date()
            # Only Hold/Cancelled/Close-Lost are honoured as explicit manual states;
            # everything else is derived after positions/candidates are seeded.
            manual_status = req["status"] if req["status"] in MANUAL_REQ_STATES else None
            base_status = req_status[manual_status] if manual_status else req_status[ReqStatus.ASSIGNED]

            r = RequirementTracker.objects.create(
                req_tracker_no=f"REQ-2026-{ri:03d}",
                jd_serial_number=f"JD-2026-{ri:05d}",
                client_req_id=f"{client.client_code}-{1000 + ri}",
                client=client, client_mgr=mgr, hiring_mgr=hm, recruiter=recruiter,
                req_type=req_types[req["type"]], jd_role_name=req["role"],
                location=locations[req["city"]],
                exp_min=Decimal(req["exp"][0]), exp_max=Decimal(req["exp"][1]),
                jd_rate_lpa=Decimal(req["rate"]), np=notice[req["np"]],
                req_status=base_status, priority=priorities[req["priority"]],
                positions_open=req["open"], positions_filled=0,
                skill1=skills[req["skills"][0]], skill2=skills[req["skills"][1]],
                skill3=skills[req["skills"][2]],
                req_date=req_date, assigned_date=req_date + timedelta(days=1),
                target_fill_date=req_date + timedelta(days=45),
                created_by=hm, created_on=now - timedelta(days=40 - ri * 3),
                jd_text=req["jd"], is_active=True,
            )

            # Materialise all seats as Open. The ones that are actually filled are
            # linked below to the candidate who filled them — a Filled seat must
            # ALWAYS reference its candidate (mirrors the real Join flow).
            RequirementPosition.objects.bulk_create([
                RequirementPosition(
                    req=r, position_no=pi, position_status=pos_status["OPEN"],
                    is_active=True, created_by=hm, created_on=r.created_on,
                )
                for pi in range(1, req["open"] + 1)
            ])

            to_fill = []  # OK-to-Proceed mappings → seeded as Joined, each fills a seat
            for ci, (cand_name, stage) in enumerate(req["pipeline"].items()):
                cand = candidates[cand_name]
                created_on = r.created_on + timedelta(days=2 + ci)

                # Fake is a candidate-level disposition, not a pipeline stage —
                # no application mapping is created for it.
                if stage == CandidateStatus.FAKE:
                    fake_names.add(cand_name)
                    CandidateInteraction.objects.create(
                        candidate=cand, req=r, interaction_type=InteractionType.STATUS_CHANGE,
                        comment=f"Marked Fake during review for {r.req_tracker_no}.",
                        created_by=recruiter, created_on=created_on,
                    )
                    continue

                screening_dt = screening_mode = rejection = None
                if stage == ApplicationStatus.SCREENING_SCHEDULED:
                    screening_dt = now + timedelta(days=2 + ci, hours=3)
                    screening_mode = screening_modes[ci % len(screening_modes)]
                elif stage == ApplicationStatus.OK_TO_PROCEED:
                    screening_dt = now - timedelta(days=3)
                    screening_mode = screening_modes[ci % len(screening_modes)]
                elif stage in REJECTION_FOR:
                    rejection = rejection_reasons.get(REJECTION_FOR[stage])

                # Split STAGE vs OUTCOME: a closing outcome sits at its prior stage
                # with latest_outcome set + is_closed; OK to Proceed records the
                # PASSED outcome; plain stages carry no outcome yet.
                is_closing = stage in _OUTCOME_PRIOR_STAGE
                stage_code = _OUTCOME_PRIOR_STAGE.get(stage, stage)
                outcome_code = stage if is_closing else _ADVANCE_OUTCOME.get(stage)
                mapping = JdCvMapping.objects.create(
                    req=r, candidate=cand, application_stage=app_stage[stage_code],
                    latest_outcome=app_stage.get(outcome_code) if outcome_code else None,
                    is_closed=is_closing,
                    closed_on=created_on if is_closing else None,
                    closed_by=recruiter if is_closing else None,
                    screening_mode=screening_mode, screening_datetime=screening_dt,
                    rejection_reason=rejection,
                    comments=f"{cand_name} for {req['role']} ({client.client_name}).",
                    is_active=True, created_by=recruiter, created_on=created_on,
                    updated_by=recruiter, updated_on=created_on,
                )
                if stage == ApplicationStatus.OK_TO_PROCEED:
                    to_fill.append(mapping)
                CandidateInteraction.objects.create(
                    candidate=cand, req=r, interaction_type=InteractionType.STATUS_CHANGE,
                    comment=f"Marked {app_stage[stage].status_name} for {r.req_tracker_no}.",
                    created_by=recruiter, created_on=created_on,
                )
                mapped_names.add(cand_name)

                # JD email already went out for these stages → log it (rendered).
                if stage in {ApplicationStatus.JD_EMAIL_SENT, ApplicationStatus.SCREENING_SCHEDULED,
                             ApplicationStatus.OK_TO_PROCEED, ApplicationStatus.NO_RESPONSE, ApplicationStatus.DROPPED,
                             ApplicationStatus.REJECTED}:
                    subject, body = self._render_jd(r, cand, recruiter)
                    CommunicationLog.objects.create(
                        candidate=cand, req=r, channel="EMAIL", recipient=cand.email,
                        subject=subject, body=body, status="SENT",
                        sent_by=recruiter, sent_on=created_on + timedelta(hours=2),
                    )

            # Fill seats from the OK-to-Proceed candidates: seed each as Joined and
            # link it to an open seat, exactly like the real Join flow — so every
            # Filled position references the candidate who filled it.
            seats = list(RequirementPosition.objects.filter(req=r).order_by("position_no"))
            joined_on = now - timedelta(days=2)
            for seat, mapping in zip(seats, to_fill):
                # Joined = closing outcome at the Awaiting Joining stage.
                mapping.application_stage = app_stage[ApplicationStatus.AWAITING_JOINING]
                mapping.latest_outcome = app_stage[ApplicationStatus.JOINED]
                mapping.is_closed = True
                mapping.closed_on = joined_on
                mapping.closed_by = recruiter
                mapping.joined_date = joined_on.date()
                mapping.updated_by = recruiter
                mapping.updated_on = joined_on
                mapping.save(update_fields=["application_stage", "latest_outcome", "is_closed",
                                            "closed_on", "closed_by", "joined_date", "updated_by", "updated_on"])
                joined_names.add(mapping.candidate.candidate_name)
                seat.position_status = pos_status["FILLED"]
                seat.filled_by_mapping = mapping
                seat.updated_by = recruiter
                seat.updated_on = joined_on
                seat.save(update_fields=["position_status", "filled_by_mapping", "updated_by", "updated_on"])

            # Derive the requirement status exactly as production would: first
            # candidate linked → Open, then the positions rollup → Partial/Close
            # Filled (recompute also refreshes the positions_open/filled cache).
            # Manual states (Hold/Cancelled) stay as explicitly set above.
            if not manual_status:
                if JdCvMapping.objects.filter(req=r).exists():
                    open_requirement_on_first_link(r, recruiter)
                recompute_requirement(r, recruiter)

        # --- Refine candidate global statuses: mapped → Saved, joined → Joined,
        #     fake → Fake, rest → New CV (joined/fake applied last, they win) ---
        for name in mapped_names:
            CandidateMaster.objects.filter(pk=candidates[name].pk).update(candidate_status=candidate_status[CandidateStatus.SAVED])
        for name in joined_names:
            CandidateMaster.objects.filter(pk=candidates[name].pk).update(candidate_status=candidate_status[CandidateStatus.JOINED])
        for name in fake_names:
            CandidateMaster.objects.filter(pk=candidates[name].pk).update(candidate_status=candidate_status[CandidateStatus.FAKE])

        # --- Activity feed (audit log) from the seeded history ---
        ActivityLog.objects.bulk_create(
            [
                ActivityLog(
                    activity_type="requirement_created",
                    summary=f"Requirement opened: {r.jd_role_name} · {r.client.client_name}",
                    req=r, actor=r.created_by, created_on=r.created_on,
                )
                for r in RequirementTracker.objects.select_related("client", "created_by").all()
            ]
            + [
                ActivityLog(
                    activity_type="candidate_added",
                    summary=f"Candidate added: {c.candidate_name}",
                    candidate=c, actor=c.uploaded_by, created_on=c.created_on,
                )
                for c in CandidateMaster.objects.select_related("uploaded_by").all()
            ]
        )

        # --- Summary ---
        new_pool = CandidateMaster.objects.filter(candidate_status__status_code=NEW).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {CandidateMaster.objects.count()} candidates "
            f"({new_pool} in the New-CV review pool), {RequirementTracker.objects.count()} requirements, "
            f"{JdCvMapping.objects.count()} pipeline rows, {CommunicationLog.objects.count()} JD emails logged, "
            f"{ClientMaster.objects.exclude(client_code='ZZT').count()} clients, {UserMaster.objects.count()} users."
        ))
        self.stdout.write(self.style.SUCCESS(f"All demo logins share password: {PASSWORD}"))

    def _render_jd(self, requirement, candidate, user):
        """Render the JD email via the same path the live send uses, so the
        tracker shows genuine messages. Falls back gracefully if no template."""
        try:
            from pipeline.services import get_jd_template, render_jd_email
            template = get_jd_template()
            return render_jd_email(
                template, requirement,
                candidate_name=candidate.candidate_name, sender_name=user.full_name,
            )
        except Exception:  # noqa: BLE001 - template optional for the log
            return (f"Job Opportunity: {requirement.jd_role_name} at {requirement.client.client_name}",
                    f"Dear {candidate.candidate_name},\n\nWe have an opportunity matching your profile.")
