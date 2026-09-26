# Electronic Code of Federal Regulations.
import yaml
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from backend.app.schemas.regulatory import Control

XML_PATH = Path("data/raw/regulatory/ecfr_45_164_subpartC.xml")
CONTROLS_PATH = Path("data/frameworks/hipaa_security_rule/controls.yaml")

MARKERS_RE = re.compile(r"^((?:\([A-Za-z0-9]+\))+)\s*") # matches "(a)(1) or "i" at the start


def find_section(root,section_number):
    for el in root.iter("DIV8"):
        if el.get("N") == section_number:
            return el

    raise ValueError(f"Section {section_number} not found in XML")


def paragraph_parts(p):

    """
    split one <P> into (markers, italic_title, body_text)
    """

    full_text = "".join(p.itertext()).strip()
    italic = p.find("I")
    title = italic.text.strip() if italic is not None and italic.text else None

    body = italic.tail.strip() if italic is not None and italic.tail else ""

    m = MARKERS_RE.match(full_text)
    markers = re.findall(r"\(([^)]+)\)", m.group(1)) if m else []

    return markers, title, body

ROMAN_RE = re.compile(r"^[ivxl]+$")   # i, ii, iii, iv, v, ... x, xi ...

def marker_level(marker, stack):
    """ return the outline level of a marker: 1= a, 2 = 1, 3 = i, 4 = A"""
    if marker.isdigit():
        return 2

    elif marker != marker.lower():
        return 4

    elif ROMAN_RE.match(marker) and len(stack) in (2,3):
        return 3
    
    else:
        return 1


def parse_title(title):
    """Turn a raw italic title into (control_name, level, requirement_type)"""

    name = title.strip()

    if name.startswith("Standard:"):
        level = "standard"
    else:
        level = "implementation_specification"

    
    if "(Required)" in name:
        requirement_type = "required"
    
    elif "(Addressable)" in name:
        requirement_type = "addressable"

    else:
        requirement_type = "required"

    name = name.replace("Standard:", "")
    name = name.replace("Implementation specification:", "")
    name = name.replace("(Required)", "")
    name = name.replace("(Addressable)", "")
    name = name.rstrip(".")
    name = name.strip()
    SMALL_WORDS = {"and", "or", "to", "of", "the", "a", "an", "in", "for"}
    words = name.title().split()
    name = " ".join(
        w.lower() if i > 0 and w.lower() in SMALL_WORDS else w
        for i, w in enumerate(words)
    )

   

    return name, level, requirement_type



            

def main():
    root = ET.parse(XML_PATH).getroot()
    section_number = "164.312"
    section = find_section(root, section_number)

    stack = []
    controls = []               # all Control objects end up here
    current_standard = None     # the most recent standard we saw
    IN_SCOPE_V1 = {"164.312(a)(1)"} # the standard we assess in v1

    
    for p in section.findall("P"):
        markers, title, body = paragraph_parts(p)

        if not markers:
            continue
        for marker in markers:
            depth = marker_level(marker,stack)
            stack = stack[:depth -1]
            stack.append(marker)
        
        full_id = section_number + "".join(f"({m})" for m in stack)
        if not body and title.endswith(":"):
            continue                          # heading, e.g. "Implementation specifications:"

        name, level, req_type = parse_title(title)
        
        if level == "standard":
            parent_id = None
            current_standard = full_id 
        else:
            parent_id = current_standard


        in_scope = (full_id in IN_SCOPE_V1) or (parent_id in IN_SCOPE_V1)

        control = Control(
            framework="HIPAA",
            section=section_number,
            control_id=full_id,
            parent_id=parent_id,
            control_name=name,
            level=level,
            requirement_type=req_type,
            safeguard_category="Technical",
            requirement_text=body,
            citation=f"45 CFR § {full_id}",
            in_scope_v1=in_scope,
        )
        controls.append(control)

    in_scope_controls = [c.model_dump() for c in controls if c.in_scope_v1]

    CONTROLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONTROLS_PATH.open("w", encoding="Utf-8") as f:
        yaml.safe_dump(in_scope_controls, f, sort_keys=False, allow_unicode=True)
    print(f"Wrote {len(in_scope_controls)} controls to {CONTROLS_PATH}")


if __name__ == "__main__":
    main()