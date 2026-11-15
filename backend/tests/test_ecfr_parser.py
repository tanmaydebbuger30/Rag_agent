from pathlib import Path
import yaml

from backend.app.ingestion.ecfr_parser import CONTROLS_PATH, marker_level, parse_controls


def load_controls():
    return yaml.safe_load(CONTROLS_PATH.read_text(encoding="utf-8"))

def test_marker_level_roman_vs_letter():
    assert marker_level("i", ["a", "2"]) == 3 # roman numeral under a number
    assert marker_level("i", []) == 1 # letter i at the top level
    assert marker_level("b", ["a", "2", "iv"]) == 1 # regression: the and / or bug


def test_in_scope_controls():
    controls = load_controls()

    actual_ids = [control["control_id"] for control in controls]
    expected_ids = [
    "164.312(a)(1)",
    "164.312(a)(2)(i)",
    "164.312(a)(2)(ii)",
    "164.312(a)(2)(iii)",
    "164.312(a)(2)(iv)",
    "164.308(a)(2)",
    "164.308(a)(6)(i)",
    "164.308(a)(6)(ii)",
    "164.308(a)(8)",
    ]
    assert actual_ids == expected_ids


def test_requirements_types():
    controls = load_controls()
    types = {c["control_id"]: c["requirement_type"] for c in controls}
    expected_types = {
    "164.312(a)(1)": "required",
    "164.312(a)(2)(i)": "required",
    "164.312(a)(2)(ii)": "required",
    "164.312(a)(2)(iii)": "addressable",
    "164.312(a)(2)(iv)": "addressable",
    "164.308(a)(2)": "required",
    "164.308(a)(6)(i)": "required",
    "164.308(a)(6)(ii)": "required",
    "164.308(a)(8)": "required",
    }
    assert types == expected_types


def test_administrative_section_parses():
    """Regression: 164.308 has untitled paragraphs ("(a) A covered entity ... must:") and
    "Implementation specifications. Implement:" headings, which used to crash the parser."""
    by_id = {c.control_id: c for c in parse_controls("164.308")}
    assert by_id["164.308(a)(1)(i)"].control_name == "Security Management Process"
    assert by_id["164.308(a)(6)(ii)"].parent_id == "164.308(a)(6)(i)"
    assert by_id["164.308(a)(2)"].safeguard_category == "Administrative"
    assert not any("Implementation Specifications" in c.control_name for c in by_id.values())


def test_paragraph_b_is_not_a_child_of_paragraph_a():
    """Regression: 164.308(b)(1) has no "Standard:" label and was attached to (a)(8)."""
    b1 = {c.control_id: c for c in parse_controls("164.308")}["164.308(b)(1)"]
    assert b1.level == "standard" and b1.parent_id is None and b1.in_scope_v1 is False


def test_requirement_text_is_verbatim():
    controls = load_controls()
    by_id = {c["control_id"]: c for c in controls}

    assert by_id["164.312(a)(2)(i)"]["requirement_text"] ==(
        "Assign a unique name and/or number for identifying and tracking user identity."
    )




