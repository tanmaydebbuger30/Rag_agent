from pathlib import Path
import yaml

from backend.app.ingestion.ecfr_parser import CONTROLS_PATH, marker_level


def load_controls():
    return yaml.safe_load(CONTROLS_PATH.read_text(encoding="utf-8"))

def test_marker_level_roman_vs_letter():
    assert marker_level("i", ["a", "2"]) == 3 # roman numeral under a number
    assert marker_level("i", []) == 1 # letter i at the top level
    assert marker_level("b", ["a", "2", "iv"]) == 1 # regression: the and / or bug


def test_exactly_five_in_scope_controls():
    controls = load_controls()

    assert len(controls) == 5 # check there are exact 5 controls
    actual_ids = []
    expected_ids = [
    "164.312(a)(1)",
    "164.312(a)(2)(i)",
    "164.312(a)(2)(ii)",
    "164.312(a)(2)(iii)",
    "164.312(a)(2)(iv)"
    ]
    for control in controls:
        actual_ids.append(control["control_id"])
    assert actual_ids == expected_ids    


def test_requirements_types():
    controls = load_controls()
    types = {c["control_id"]: c["requirement_type"] for c in controls}
    expected_types = {
    "164.312(a)(1)": "required",
    "164.312(a)(2)(i)": "required",
    "164.312(a)(2)(ii)": "required",
    "164.312(a)(2)(iii)": "addressable",
    "164.312(a)(2)(iv)": "addressable"
    }
    assert types == expected_types

def test_requirement_text_is_verbatim():
    controls = load_controls()
    by_id = {c["control_id"]: c for c in controls}

    assert by_id["164.312(a)(2)(i)"]["requirement_text"] ==(
        "Assign a unique name and/or number for identifying and tracking user identity."
    )




