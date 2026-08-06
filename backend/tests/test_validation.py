"""
Unit tests for the centralised master-data normalisation & duplicate-key logic
(core.validation). Pure functions — no database needed.
"""
import pytest

from core.validation import normalize_key, normalize_text, validate_name


@pytest.mark.parametrize("raw,expected", [
    # whitespace + Title Case for general text
    ("machine learning", "Machine Learning"),
    ("  pune  ", "Pune"),
    ("work   from   home", "Work From Home"),
    # canonical technical terms (never blindly Title-cased)
    ("sql", "SQL"),
    ("mysql", "MySQL"),
    ("postgresql", "PostgreSQL"),
    ("github", "GitHub"),
    ("GITHUB", "GitHub"),
    ("power bi", "Power BI"),
    ("ms excel", "MS Excel"),
    ("aws", "AWS"),
    ("react", "React"),
    ("node.js", "Node.js"),
    ("javascript", "JavaScript"),
    ("typescript", "TypeScript"),
    ("html", "HTML"),
    ("rest api", "REST API"),
    ("ui/ux", "UI/UX"),
    # acronyms / intentional capitals survive
    ("HCL Technologies", "HCL Technologies"),
    ("LTIMindtree", "LTIMindtree"),
    ("OK to Proceed", "OK To Proceed"),
])
def test_title_normalization(raw, expected):
    assert normalize_text(raw, "title") == expected


@pytest.mark.parametrize("raw,expected", [
    ("india", "India"),
    ("mUMBAI", "Mumbai"),
    ("new delhi", "New Delhi"),
    ("o'fallon", "O'Fallon"),
    ("dadra-nagar haveli", "Dadra-Nagar Haveli"),
    ("INdia", "India"),
    ("INDIA", "India"),
])
def test_place_strict_title_case(raw, expected):
    assert normalize_text(raw, "title_strict") == expected


@pytest.mark.parametrize("kind,value,ok", [
    ("place", "New Delhi", True), ("place", "Mumbai1", False), ("place", "Pune@", False),
    ("alpha", "High", True), ("alpha", "High-Priority", False), ("alpha", "High1", False),
    ("alphaamp", "Work From Home", True), ("alphaamp", "R&D", True),
    ("alphaamp", "Contract / Hire", False), ("alphaamp", "Full Time 1", False),
])
def test_field_character_rules(kind, value, ok):
    assert (validate_name(value, kind) is None) is ok


def test_codes_uppercased_and_descriptions_preserved():
    assert normalize_text("fte", "upper") == "FTE"
    assert normalize_text("  keeps   inner\nlines ", "trim") == "keeps   inner\nlines"


@pytest.mark.parametrize("a,b", [
    ("GitHub", "  github "),
    ("GITHUB", "gitHub"),
    ("Machine Learning", "machine   learning"),
    (" MACHINE LEARNING", "Machine Learning"),
])
def test_duplicate_keys_match(a, b):
    """Case-, whitespace- and normalisation-insensitive duplicate detection."""
    assert normalize_key(a) == normalize_key(b)


def test_distinct_values_do_not_collide():
    assert normalize_key("Machine Learning") != normalize_key("Deep Learning")


@pytest.mark.parametrize("bad", ["N--ashik", "-Pune", "Pune-", "@@@@", "12345", "Navi - Mumbai"])
def test_invalid_place_names_rejected(bad):
    assert validate_name(bad, "place") is not None


@pytest.mark.parametrize("good", ["Navi-Mumbai", "Navi Mumbai", "Bengaluru", "O'Brien"])
def test_valid_place_names_accepted(good):
    assert validate_name(good, "place") is None
