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


def main():
    root = ET.parse(XML_PATH).getroot()
    section = find_section(root, "164.312")
    for p in section.findall("P"):
        print(paragraph_parts(p))

if __name__ == "__main__":
    main()