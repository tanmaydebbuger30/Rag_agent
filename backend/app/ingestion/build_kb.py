"""Build the regulatory knowledge base: eCFR + HHS + NIST -> regulatory_chunks.jsonl.

Run: python -m backend.app.ingestion.build_kb
"""
import json
from collections import Counter

from backend.app.config import REGULATORY_CHUNKS
from backend.app.ingestion.ecfr_parser import parse_controls
from backend.app.ingestion.hhs_chunks import load_hhs_chunks
from backend.app.ingestion.nist_chunks import load_nist_chunks
from backend.app.schemas.chunks import RegulatoryChunk

SECTION_TITLES = {"164.308": "Administrative safeguards", "164.312": "Technical safeguards"}


def ecfr_chunks():
    """One chunk per standard / implementation specification: the legal atoms."""
    controls = {c.control_id: c for c in parse_controls("164.312") + parse_controls("164.308")}
    chunks = []
    for c in controls.values():
        path = ["HIPAA Security Rule", f"45 CFR {c.section} {SECTION_TITLES[c.section]}"]
        if c.parent_id:
            path.append(f"{c.parent_id} {controls[c.parent_id].control_name}")
        label = f"{c.control_id} {c.control_name} ({c.requirement_type.capitalize()})"
        path.append(label)
        chunks.append(RegulatoryChunk(
            chunk_id=f"ecfr-{c.control_id}",
            doc_id="ecfr-45-164-subpartC",
            source=f"45 CFR § {c.section} (eCFR)",
            authority_level="regulation",
            heading=label,
            heading_path=path,
            control_ids=[c.control_id],
            primary_control_id=c.control_id,
            requirement_type=c.requirement_type,
            in_scope_v1=c.in_scope_v1,
            page_start=None,
            page_end=None,
            content_type="regulation_text",
            text=c.requirement_text,
            embedding_text=" > ".join(path) + "\n" + c.requirement_text,
        ))
    return chunks


def build_all():
    return ecfr_chunks() + load_hhs_chunks() + load_nist_chunks()


def load_kb(path=REGULATORY_CHUNKS):
    with path.open(encoding="utf-8") as f:
        return [RegulatoryChunk(**json.loads(line)) for line in f if line.strip()]


def main():
    chunks = build_all()
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "duplicate chunk ids"
    REGULATORY_CHUNKS.parent.mkdir(parents=True, exist_ok=True)
    with REGULATORY_CHUNKS.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.model_dump(), ensure_ascii=False) + "\n")
    by_source = Counter(c.doc_id for c in chunks)
    print(f"{len(chunks)} chunks -> {REGULATORY_CHUNKS}")
    for doc_id, n in by_source.items():
        print(f"  {doc_id:<24} {n}")
    print(f"  in scope: {sum(c.in_scope_v1 for c in chunks)}")


if __name__ == "__main__":
    main()
