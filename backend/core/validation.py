"""
Centralised master-data validation & normalisation.

WHY: every master screen (skills, locations, users, …) needs the same hygiene —
trim/clean input, reject bad formats, and refuse case-/space-insensitive
duplicates. Putting it in one place (instead of per-serializer) keeps behaviour
identical across all 12 masters and makes it the single source of truth that the
frontend mirrors.

The `MASTER_RULES` registry below is keyed by db_table and declares, per master:
  normalize : {field: mode}   mode ∈ {None, "upper", "title", "trim"}
  email     : [fields]        must look like an email
  phone     : [fields]        must be a valid Indian mobile
  code      : [fields]        letters/digits/-/_ only
  unique    : [fields]        each must be unique (normalised, case-insensitive)
  unique_together : [(f, …)]  the combination must be unique
"""
import re
import unicodedata
from difflib import SequenceMatcher

# Invisible / zero-width characters that should never survive into stored data.
_INVISIBLE = {ord(c): None for c in "​‌‍⁠﻿"}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[6-9]\d{9}$")  # Indian mobile: 10 digits, starts 6-9
CODE_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# Allowed character sets per "name kind". Each must start with an
# alphanumeric, so leading separators/symbols are rejected outright.
_NAME_PATTERNS = {
    # Places: letters, spaces, hyphens, apostrophes only (no digits/symbols).
    "place": re.compile(r"^[A-Za-z][A-Za-z '\-]*$"),
    # People: letters + spaces/hyphen/apostrophe/period (initials).
    "person": re.compile(r"^[A-Za-z][A-Za-z '.\-]*$"),
    # Login handles: letters, digits, dot, underscore, hyphen.
    "handle": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*$"),
    # Technical skills: covers "Node.js", "C++", "C#", "A/B Testing".
    "skill": re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .+#/'\-]*$"),
    # Letters + spaces only (e.g. Priority).
    "alpha": re.compile(r"^[A-Za-z][A-Za-z ]*$"),
    # Letters, spaces, hyphen & ampersand (Work Mode / Req Type / Req Status).
    "alphaamp": re.compile(r"^[A-Za-z][A-Za-z &\-]*$"),
    # General labels/names: "30 Days", "Larsen & Toubro", "OK to Proceed".
    "label": re.compile(r"^[A-Za-z0-9][A-Za-z0-9 &/().,'\-]*$"),
}
_HAS_LETTER = re.compile(r"[A-Za-z]")
_SPACE_AROUND_HYPHEN = re.compile(r"\s-|-\s")


def validate_name(value, kind="label"):
    """Validate a human-facing name/label. Returns an error message or None.
    Rejects: no-letter values ("12345", "@@@"), random symbols, leading/
    trailing hyphens, double hyphens ("N--ashik"), spaced hyphens, and any
    character outside the kind's allowed set."""
    s = (value or "").strip()
    if not s:
        return None  # emptiness is handled by the required-field check
    if not _HAS_LETTER.search(s):
        return "Must contain letters; numbers or symbols alone aren't allowed."
    if "--" in s:
        return "Remove the repeated hyphen."
    if s.startswith("-") or s.endswith("-"):
        return "Cannot start or end with a hyphen."
    if _SPACE_AROUND_HYPHEN.search(s):
        return "A hyphen must join words directly, with no spaces around it."
    if not _NAME_PATTERNS.get(kind, _NAME_PATTERNS["label"]).match(s):
        return "Contains invalid characters."
    return None


# Canonical capitalisation for common technical terms / abbreviations, keyed by
# their normalised (collapsed, lower-cased) form. Looked up before Title Case so
# these are never mangled (e.g. "github" -> "GitHub", not "Github").
CANONICAL = {
    "sql": "SQL", "mysql": "MySQL", "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "mongodb": "MongoDB", "github": "GitHub", "gitlab": "GitLab",
    "power bi": "Power BI", "powerbi": "Power BI", "ms excel": "MS Excel",
    "aws": "AWS", "azure": "Azure", "gcp": "GCP",
    "react": "React", "reactjs": "ReactJS", "react.js": "ReactJS",
    "node.js": "Node.js", "nodejs": "Node.js", "node js": "Node.js",
    "javascript": "JavaScript", "typescript": "TypeScript",
    "html": "HTML", "css": "CSS", "scss": "SCSS",
    "rest api": "REST API", "rest apis": "REST APIs", "graphql": "GraphQL",
    "ui/ux": "UI/UX", "ui": "UI", "ux": "UX",
    ".net": ".NET", "php": "PHP", "json": "JSON", "xml": "XML",
    "api": "API", "apis": "APIs", "devops": "DevOps", "ci/cd": "CI/CD",
    "ios": "iOS",
}


def _title_token(word):
    """Capitalise one token, preserving acronyms and intentional internal caps
    so "HCL", "ReactJS", "LTIMindtree" and "iOS" survive Title Casing."""
    if not word:
        return word
    if word.isupper():
        # short all-caps = acronym (HCL/AWS/SQL); long all-caps = SHOUTING -> fix.
        return word if len(word) <= 4 else word[:1] + word[1:].lower()
    if word[1:] != word[1:].lower():
        return word  # has an internal capital (ReactJS) -> assume intentional
    return word[:1].upper() + word[1:]


def title_case(s):
    """Title Case with canonical/acronym awareness (see _title_token + CANONICAL)."""
    return " ".join(_title_token(w) for w in s.split(" "))


def strict_title_case(s):
    """Force proper Title Case for place names: lower-case everything, then
    capitalise the first letter of each word — including after hyphens and
    apostrophes. Fixes inconsistent capitalisation ("mUMBAI"->"Mumbai",
    "INdia"->"India", "o'fallon"->"O'Fallon", "dadra-nagar"->"Dadra-Nagar")."""
    return re.sub(r"(^|[ '\-])([a-z])", lambda m: m.group(1) + m.group(2).upper(), s.lower())


def normalize_text(value, mode=None):
    """Clean a text value: drop invisible chars, NFKC-normalise, convert
    non-breaking spaces, collapse internal whitespace, trim. `mode` applies an
    optional transform: "upper", "title" (proper-case), or "trim" (preserve
    internal whitespace/newlines — for descriptions)."""
    if value is None:
        return None
    s = str(value).translate(_INVISIBLE)
    s = unicodedata.normalize("NFKC", s).replace(" ", " ")
    if mode == "trim":
        return s.strip()
    s = re.sub(r"\s+", " ", s).strip()
    if mode == "upper":
        return s.upper()
    if mode == "title_strict":
        return strict_title_case(s)
    if mode == "title":
        # Canonical term (GitHub, Power BI…) wins; otherwise Title Case.
        return CANONICAL.get(s.casefold(), title_case(s))
    return s


def normalize_key(value):
    """Comparison key for duplicate detection: normalised + case-folded."""
    n = normalize_text(value)
    return n.casefold() if n else ""


def generate_code(name):
    """Derive a stable UPPER_SNAKE identifier from a display name.
    'Screening Scheduled' -> 'SCREENING_SCHEDULED'; 'JD Email Sent' ->
    'JD_EMAIL_SENT'; 'Work From Home' -> 'WORK_FROM_HOME'. Non-alphanumeric runs
    collapse to a single underscore; leading/trailing underscores are trimmed."""
    s = normalize_text(str(name or "")).upper()
    s = re.sub(r"[^A-Z0-9]+", "_", s)
    return s.strip("_")


def similarity(a, b):
    """0..1 similarity between two labels (normalised, case-insensitive)."""
    return SequenceMatcher(None, normalize_key(a), normalize_key(b)).ratio()


# --------------------------------------------------------------------------- #
#  Per-master rules (keyed by db_table). Masters absent here still get safe
#  whitespace trimming via the default in apply_normalization().
# --------------------------------------------------------------------------- #
MASTER_RULES = {
    "user_master": {
        "normalize": {"full_name": "title", "username": None},
        "names": {"full_name": "person", "username": "handle"},
        "email": ["email"], "phone": ["mobile"],
        "unique": ["username", "email"],
    },
    "skill_master": {
        # Domain is now a FK (domain_id) to domain_master, not free text.
        "normalize": {"skill_name": "title"},
        "names": {"skill_name": "skill"},
        "unique": ["skill_name"],
    },
    "domain_master": {
        # Classification labels: "Data & Analytics", "UI/UX Design", etc. — the
        # "label" rule allows letters/digits/spaces and & / ( ) . , ' - .
        "normalize": {"domain_name": "title"},
        "names": {"domain_name": "label"},
        "unique": ["domain_name"],
    },
    "candidate_status_master": {
        "normalize": {"status_name": "title", "status_code": "upper"},
        "names": {"status_name": "label"}, "code": ["status_code"],
        "unique": ["status_name", "status_code"],
        "auto_code": {"field": "status_code", "source": "status_name"},
    },
    "application_status_master": {
        "normalize": {"status_name": "title", "status_code": "upper"},
        "names": {"status_name": "label"}, "code": ["status_code"],
        "unique": ["status_name", "status_code"],
        "auto_code": {"field": "status_code", "source": "status_name"},
    },
    "position_status_master": {
        "normalize": {"status_name": "title", "status_code": "upper"},
        "names": {"status_name": "label"}, "code": ["status_code"],
        "unique": ["status_name", "status_code"],
        "auto_code": {"field": "status_code", "source": "status_name"},
    },
    "location_master": {
        # state/country are now picked from controlled dropdowns (official names
        # like "Delhi (NCT)" / "Jammu and Kashmir" contain chars the place rule
        # rejects), so they're trimmed-only, not char-validated/recased. City is
        # still free-text → keep place validation + strict Title Case.
        "normalize": {"city": "title_strict", "state": "trim", "country": "trim"},
        "names": {"city": "place"},
        "unique_together": [("city", "state", "country")],
    },
    "source_master": {
        "normalize": {"source_name": "title", "source_type": "title"},
        "names": {"source_name": "label", "source_type": "label"},
        "unique": ["source_name"],
    },
    "notice_period_master": {
        "normalize": {"np_name": "title"},
        "names": {"np_name": "label"},
        "unique": ["np_name"],
    },
    "work_mode_master": {
        "normalize": {"work_mode_code": "upper", "work_mode_name": "title"},
        "names": {"work_mode_name": "alphaamp"},
        "code": ["work_mode_code"],
        "unique": ["work_mode_code", "work_mode_name"],
        "auto_code": {"field": "work_mode_code", "source": "work_mode_name"},
    },
    "priority_master": {
        "normalize": {"priority_name": "title", "description": "trim"},
        "names": {"priority_name": "alpha"},
        "unique": ["priority_name"],
    },
    "screening_mode_master": {
        "normalize": {"mode_name": "title", "mode_code": "upper", "description": "trim"},
        "names": {"mode_name": "label"},
        "code": ["mode_code"],
        "unique": ["mode_name", "mode_code"],
        "auto_code": {"field": "mode_code", "source": "mode_name"},
    },
    "rejection_reason_master": {
        "normalize": {"reason_name": "title", "reason_code": "upper", "description": "trim"},
        "names": {"reason_name": "label"},
        "code": ["reason_code"],
        "unique": ["reason_name", "reason_code"],
        "auto_code": {"field": "reason_code", "source": "reason_name"},
    },
    "req_type_master": {
        "normalize": {"req_type_code": "upper", "req_type_name": "title", "description": "trim"},
        "names": {"req_type_name": "alphaamp"},
        "code": ["req_type_code"],
        "unique": ["req_type_code", "req_type_name"],
        "auto_code": {"field": "req_type_code", "source": "req_type_name"},
    },
    "req_status_master": {
        "normalize": {"status_name": "title", "status_code": "upper", "description": "trim"},
        "names": {"status_name": "alphaamp"},
        "code": ["status_code"],
        "unique": ["status_name", "status_code"],
        "auto_code": {"field": "status_code", "source": "status_name"},
    },
    "client_master": {
        "normalize": {"client_code": "upper", "client_name": "title", "industry": "title"},
        "names": {"client_name": "label", "industry": "label"},
        "code": ["client_code"],
        "unique": ["client_code", "client_name"],
        "auto_code": {"field": "client_code", "source": "client_name"},
    },
    "client_manager_master": {
        "normalize": {"manager_name": "title", "designation": "title", "department": "title"},
        "names": {"manager_name": "person", "designation": "label", "department": "label"},
        "email": ["email"], "phone": ["mobile"],
        "unique_together": [("client", "email")],
    },
    "email_template_master": {
        "normalize": {"template_code": "upper", "name": "title", "subject": None},  # body left intact
        "names": {"name": "label"},
        "code": ["template_code"],
        "unique": ["template_code"],
    },
}


def rules_for(db_table):
    return MASTER_RULES.get(db_table, {})


def apply_normalization(db_table, data):
    """Normalise the configured fields in a validated_data dict (in place-ish);
    returns the same dict. Fields not in the registry are left untouched."""
    rules = rules_for(db_table)
    for field, mode in rules.get("normalize", {}).items():
        if field in data and data[field] is not None:
            data[field] = normalize_text(data[field], mode)
    for field in rules.get("email", []):
        if data.get(field):
            data[field] = normalize_text(data[field], "trim").lower()
    for field in rules.get("phone", []):  # trim before the 10-digit check
        if data.get(field):
            data[field] = normalize_text(data[field], "trim")
    return data


def validate_formats(db_table, data, required_blank_fields=()):
    """Return a {field: message} dict of format errors (empty = valid).
    `required_blank_fields` are fields that became empty after normalisation."""
    rules = rules_for(db_table)
    errors = {}
    for field in required_blank_fields:
        errors[field] = "This field is required."
    for field in rules.get("email", []):
        val = data.get(field)
        if val and not EMAIL_RE.match(val):
            errors[field] = "Enter a valid email address."
    for field in rules.get("phone", []):
        val = data.get(field)
        if val and not PHONE_RE.match(str(val)):
            errors[field] = "Enter a valid 10-digit mobile number (starts 6-9)."
    for field in rules.get("code", []):
        val = data.get(field)
        if val and not CODE_RE.match(str(val)):
            errors[field] = "Use only letters, numbers, hyphen or underscore."
    for field, kind in rules.get("names", {}).items():
        if field in errors:
            continue
        msg = validate_name(data.get(field), kind)
        if msg:
            errors[field] = msg
    return errors
