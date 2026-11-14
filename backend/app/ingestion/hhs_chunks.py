"""HHS Security Series #4 (Technical Safeguards) -> one chunk per heading section.

Sections come from pdf_explore.build_sections (font-based heading detection).
Each section is linked to a control by its citation (SPEC headings carry
"§ 164.312(...)") or, for 16pt standard headings, by exact control name. We
link by citation rather than name because the source itself has typos
("ENCRYTION AND DECRYPTION").
"""
import json
import re

import pymupdf

from backend.app.config import HHS_PDF, PROCESSED_DIR
from backend.app.ingestion.ecfr_parser import parse_controls
from backend.app.ingestion.pdf_explore import build_sections
from backend.app.schemas.chunks import RegulatoryChunk

SOURCE_NAME = "HHS Security Series #4: Technical Safeguards"
DOC_ID = "hhs-security-series-4"
CHUNKS_PATH = PROCESSED_DIR / "hhs_chunks.jsonl"
CITATION_RE = re.compile(r"§\s*(164\.312(?:\([A-Za-z0-9]+\))+)")


def load_controls():
    """All §164.312 controls (in scope or not), keyed by control_id."""
    return {c.control_id: c for c in parse_controls()}


def extract_citation(heading):
    match = CITATION_RE.search(heading)
    if match:
        return match.group(1)
    return None


def find_standard_by_name(heading, controls):
    wanted = heading.lower().strip()
    for control in controls.values():
        if control.level != "standard":
            continue
        if wanted == control.control_name.strip().lower():
            return control.control_id
    return None


def build_chunks(sections, controls):
    chunks = []
    for i, section in enumerate(sections, start=1):
        control_id = None
        if section["kind"] == "SPEC":
            control_id = extract_citation(section["heading"])
        elif section["kind"] == "SECTION":
            control_id = find_standard_by_name(section["heading"], controls)

        control = controls.get(control_id) if control_id else None

        text = "\n".join(section["lines"])
        path = ["HIPAA Security Rule", "45 CFR 164.312 Technical safeguards"]
        if control is not None and control.parent_id:
            path.append(controls[control.parent_id].control_name)
        path.append(section["heading"])

        chunks.append(RegulatoryChunk(
            chunk_id=f"hhs-ts-{i:02d}",
            doc_id=DOC_ID,
            source=SOURCE_NAME,
            authority_level="official_guidance",
            heading=section["heading"],
            heading_path=path,
            control_ids=[control_id] if control_id else [],
            primary_control_id=control_id,
            requirement_type=control.requirement_type if control else None,
            in_scope_v1=control.in_scope_v1 if control else False,
            page_start=section["page_start"],
            page_end=section["page_end"],
            content_type="prose",
            text=text,
            embedding_text=" > ".join(path) + "\n" + text,
        ))
    return chunks


def load_hhs_chunks():
    doc = pymupdf.open(HHS_PDF)
    return build_chunks(build_sections(doc), load_controls())


def write_chunks(chunks, path=CHUNKS_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n")


def main():
    chunks = load_hhs_chunks()
    write_chunks(chunks)
    print(f"\n{len(chunks)} chunks -> {CHUNKS_PATH}\n")
    for c in chunks:
        print(f"{c.chunk_id}  {c.primary_control_id or '-':<20} in_scope={c.in_scope_v1!s:<5}  {c.heading}")


if __name__ == "__main__":
    main()
