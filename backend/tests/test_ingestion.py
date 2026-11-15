from functools import lru_cache

import yaml

from backend.app.config import CONTROLS_YAML
from backend.app.ingestion.build_kb import build_all, ecfr_chunks
from backend.app.ingestion.hhs_chunks import extract_citation, load_hhs_chunks
from backend.app.ingestion.nist_chunks import load_nist_chunks

ACCESS_CONTROL = ["164.312(a)(1)", "164.312(a)(2)(i)", "164.312(a)(2)(ii)", "164.312(a)(2)(iii)", "164.312(a)(2)(iv)"]
ADMINISTRATIVE = ["164.308(a)(2)", "164.308(a)(6)(i)", "164.308(a)(6)(ii)", "164.308(a)(8)"]


@lru_cache
def hhs():
    return load_hhs_chunks()


@lru_cache
def nist():
    return load_nist_chunks()


def test_extract_citation():
    assert extract_citation("4. ENCRYTION AND DECRYPTION (A) - § 164.312(a)(2)(iv)") == "164.312(a)(2)(iv)"
    assert extract_citation("Access Control") is None


def test_hhs_sections_map_to_controls_by_citation():
    chunks = hhs()
    assert len(chunks) == 18
    by_control = {c.primary_control_id: c for c in chunks if c.primary_control_id}
    for cid in ACCESS_CONTROL:
        assert by_control[cid].in_scope_v1
    # the source typo "ENCRYTION" does not break the link, because we link by citation
    assert "ENCRYTION" in by_control["164.312(a)(2)(iv)"].heading
    # distractors are tagged but not in scope
    for cid in ["164.312(b)", "164.312(c)(2)", "164.312(e)(2)(ii)"]:
        assert by_control[cid].in_scope_v1 is False


def test_hhs_chunks_drop_sidebars_and_footers():
    text = "\n".join(c.text for c in hhs())
    assert "5/2005: rev. 3/2007" not in text
    assert "NOTE:" not in text
    assert "Volume 2 / Paper 4" not in text


def test_hhs_requirement_type_matches_catalog():
    """Cross-source check: HHS marks specs (R)/(A); the eCFR-derived catalog must agree."""
    catalog = {c["control_id"]: c["requirement_type"] for c in yaml.safe_load(CONTROLS_YAML.read_text())}
    for c in hhs():
        if c.primary_control_id in catalog and "(R)" in c.heading:
            assert catalog[c.primary_control_id] == "required"
        if c.primary_control_id in catalog and "(A)" in c.heading:
            assert catalog[c.primary_control_id] == "addressable"


def test_nist_rows_are_complete_and_tagged():
    chunks = nist()
    assert len(chunks) == 73            # §5.1 administrative (46 rows) + §5.3 technical (27 rows)
    rows = {c.chunk_id: c for c in chunks}
    # row 8 covers two addressable specs and continues onto the next page
    row8 = rows["nist-5.3.1-08"]
    assert row8.control_ids == ["164.312(a)(2)(iii)", "164.312(a)(2)(iv)"]
    assert (row8.page_start, row8.page_end) == (78, 79)
    assert "terminate an electronic session" in row8.text
    assert rows["nist-5.3.1-03"].control_ids == ["164.312(a)(2)(i)"]
    assert rows["nist-5.3.1-01"].control_ids == ["164.312(a)(1)"]
    assert rows["nist-5.3.4-01"].control_ids == ["164.312(d)"] and not rows["nist-5.3.4-01"].in_scope_v1
    # administrative rows: outline "164.308(a)(6)" resolves to the standard (a)(6)(i); spec rows are tagged
    assert rows["nist-5.1.6-01"].control_ids == ["164.308(a)(6)(i)"]
    assert rows["nist-5.1.6-03"].control_ids == ["164.308(a)(6)(ii)"]
    assert rows["nist-5.1.1-02"].control_ids == ["164.308(a)(1)(ii)(A)"] and not rows["nist-5.1.1-02"].in_scope_v1
    assert "Assessment 32" not in rows["nist-5.1.1-02"].heading


def test_nist_footnote_markers_removed():
    row1 = next(c for c in nist() if c.chunk_id == "nist-5.3.1-01")
    assert "Users103" not in row1.text and "All Users" in row1.text
    assert "§ 164.308(a)(4)" in row1.text            # citations survive footnote stripping


def test_kb_ids_unique_and_every_control_has_regulation_and_guidance():
    chunks = build_all()
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    for cid in ACCESS_CONTROL + ADMINISTRATIVE:
        sources = {c.authority_level for c in chunks if cid in c.control_ids}
        assert {"regulation", "supporting_guidance"} <= sources, cid
    for cid in ACCESS_CONTROL:          # the HHS paper in the repo covers technical safeguards only
        assert "official_guidance" in {c.authority_level for c in chunks if cid in c.control_ids}, cid


def test_ecfr_chunks_are_verbatim_catalog_text():
    catalog = {c["control_id"]: c["requirement_text"] for c in yaml.safe_load(CONTROLS_YAML.read_text())}
    for c in ecfr_chunks():
        if c.primary_control_id in catalog:
            assert c.text == catalog[c.primary_control_id]
