"""NIST SP 800-66r2 §5.3 (Technical Safeguards) -> one chunk per Key Activity row.

Each standard in §5.3 has a table "Key Activities | Description | Sample
Questions". A table row is the natural unit: it says what to do and what an
assessor would ask, which is exactly what gap analysis needs. Rows that a page
break splits are merged back together. The standard each row belongs to comes
from the PDF outline (get_toc), not from the text.
"""
import json
import re

import pymupdf

from backend.app.config import NIST_PDF, PROCESSED_DIR
from backend.app.ingestion.ecfr_parser import parse_controls
from backend.app.schemas.chunks import RegulatoryChunk

SOURCE_NAME = "NIST SP 800-66r2: Implementing the HIPAA Security Rule"
DOC_ID = "nist-sp-800-66r2"
CHUNKS_PATH = PROCESSED_DIR / "nist_chunks.jsonl"

TOC_RE = re.compile(r"^(5\.3\.\d)\.\s+(.+?)\s*\(§\s*(164\.312\([a-z]\)(?:\(\d\))?)\)")
FOOTNOTE_RE = re.compile(r"(?<=[A-Za-z\.\)])\d{2,3}(?=\s|$|[,.;:])")   # "Users103" -> "Users"
ROW_NUMBER_RE = re.compile(r"^\d+\.\s")

# Key activity rows that name an implementation specification, matched by name.
SPEC_NAMES = {
    "unique identifier": "164.312(a)(2)(i)",
    "emergency access procedure": "164.312(a)(2)(ii)",
    "automatic logoff": "164.312(a)(2)(iii)",
    "encryption and decryption": "164.312(a)(2)(iv)",
    "mechanism to authenticate": "164.312(c)(2)",
    "integrity controls": "164.312(e)(2)(i)",
    "implement encryption": "164.312(e)(2)(ii)",
}


def technical_sections(doc):
    """[(number, title, standard_id, first_page, last_page)] for §5.3.x, from the outline."""
    toc = doc.get_toc()
    found = []
    for i, (level, title, page) in enumerate(toc):
        m = TOC_RE.match(title)
        if not m:
            continue
        next_page = next((p for _, _, p in toc[i + 1:]), page + 1)
        found.append((m.group(1), m.group(2), m.group(3), page, max(page, next_page - 1)))
    return found


def clean_cell(text):
    text = (text or "").replace("•", "•")
    text = FOOTNOTE_RE.sub("", text)
    lines = [" ".join(line.split()) for line in text.split("\n")]
    # Re-join wrapped lines; keep a line break before each bullet.
    out = ""
    for line in lines:
        if not line:
            continue
        if line in ("•", "o") or line.startswith(("• ", "o ")):
            out += "\n" + line
        elif out.endswith(("•", "o")):
            out += " " + line
        else:
            out += (" " if out else "") + line
    return out.strip()


def table_rows(doc, first_page, last_page):
    """Yield (page, key_activity, description, questions) for every data row."""
    for page_num in range(first_page, last_page + 1):
        for table in doc[page_num - 1].find_tables().tables:
            for row in table.extract():
                cells = [clean_cell(c) for c in row if c is not None and c.strip()]
                if len(cells) < 2 or cells[0] == "Key Activities":
                    continue
                if len(cells) == 2:            # continuation row with an empty first column
                    cells = ["", *cells]
                yield page_num, cells[0], cells[1], cells[2] if len(cells) > 2 else ""


def merge_rows(rows):
    """A row whose key activity is not numbered continues the previous one."""
    merged = []
    for page, activity, description, questions in rows:
        if merged and not ROW_NUMBER_RE.match(activity):
            prev = merged[-1]
            prev["page_end"] = page
            prev["activity"] = f"{prev['activity']} {activity}".strip()
            prev["description"] = f"{prev['description']}\n{description}".strip()
            prev["questions"] = f"{prev['questions']}\n{questions}".strip()
            continue
        merged.append({"page_start": page, "page_end": page, "activity": activity,
                       "description": description, "questions": questions})
    return merged


def spec_ids_for(activity):
    lowered = activity.lower()
    return [cid for name, cid in SPEC_NAMES.items() if name in lowered]


def build_chunks(doc, controls):
    chunks = []
    for number, title, standard_id, first, last in technical_sections(doc):
        if standard_id not in controls:            # outline says "164.312(a)"; the standard is (a)(1)
            standard_id += "(1)"
        for i, row in enumerate(merge_rows(table_rows(doc, first, last)), start=1):
            spec_ids = spec_ids_for(row["activity"])
            control_ids = spec_ids or [standard_id]
            primary = control_ids[0]
            control = controls.get(primary)
            text = (f"Key activity: {row['activity']}\n"
                    f"Description:\n{row['description']}\n"
                    f"Sample questions:\n{row['questions']}")
            path = ["NIST SP 800-66r2", "5.3 Technical Safeguards", f"{number} {title}"]
            chunks.append(RegulatoryChunk(
                chunk_id=f"nist-{number}-{i:02d}",
                doc_id=DOC_ID,
                source=SOURCE_NAME,
                authority_level="supporting_guidance",
                heading=row["activity"],
                heading_path=path,
                control_ids=control_ids,
                primary_control_id=primary,
                requirement_type=control.requirement_type if control else None,
                in_scope_v1=any(controls[c].in_scope_v1 for c in control_ids if c in controls),
                page_start=row["page_start"],
                page_end=row["page_end"],
                content_type="table_row",
                text=text,
                embedding_text=" > ".join(path) + "\n" + text,
            ))
    return chunks


def load_nist_chunks():
    controls = {c.control_id: c for c in parse_controls()}
    return build_chunks(pymupdf.open(NIST_PDF), controls)


def main():
    chunks = load_nist_chunks()
    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.model_dump(), ensure_ascii=False) + "\n")
    print(f"{len(chunks)} chunks -> {CHUNKS_PATH}")
    for c in chunks:
        print(f"{c.chunk_id:<16} p.{c.page_start}-{c.page_end:<3} {','.join(c.control_ids):<40} {c.heading[:70]}")


if __name__ == "__main__":
    main()
