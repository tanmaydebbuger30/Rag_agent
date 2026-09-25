# Electronic Code of Federal Regulations.
import re
import xml.etree.ElementTree as ET
from pathlib import Path

XML_PATH = Path("data/raw/regulatory/ecfr_45_164_subpartC.xml")

MARKERS_RE = re.compile(r"^((?:\([A-Za-z0-9]+\))+)\s*") # matches "(a)(1) or "i" at the start


def find_section(root,section_number):
    for el in root.iter("DIV8"):
        if el.get("N") == section_number:
            return el

    raise ValueError(f"Section {section_number} not found in XML")


def paragraph_parts(p):

    """
    split one <P> intpo (markerts, italic_title, body_text)
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
    
# print(marker_level("a", []))             # expect 1
# print(marker_level("1", ["a"]))          # expect 2
# print(marker_level("i", ["a", "2"]))     # expect 3
# print(marker_level("i", []))             # expectx 1
# print(marker_level("A", ["a","2","i"]))  # expect 4
# print(marker_level("b", ["a","2","iv"])) # expect 1  ← the bug-2 case

def main():
    root = ET.parse(XML_PATH).getroot()
    section_number = "164.312"
    section = find_section(root, section_number)

    stack = []
    
    for p in section.findall("P"):
        markers, title, body = paragraph_parts(p)

        if not markers:
            continue
        for marker in markers:
            level = marker_level(marker,stack)
            stack = stack[:level -1]
            stack.append(marker)
        
        full_id = section_number + "".join(f"({m})" for m in stack)
        print(f"{full_id:<22} {title}")
    



if __name__ == "__main__":
    main()