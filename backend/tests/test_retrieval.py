import math

import numpy as np

from backend.app.ingestion.build_kb import build_all
from backend.app.retrieval.bm25 import BM25Index
from backend.app.retrieval.dense import DenseIndex
from backend.app.retrieval.hybrid import RRF_K, RegulatoryRetriever, rrf
from backend.app.retrieval.text import find_citations, tokenize

_retriever = None


def retriever():
    global _retriever
    if _retriever is None:
        _retriever = RegulatoryRetriever(build_all())
    return _retriever


def test_citations_are_single_tokens():
    assert find_citations("see § 164.312 (a)(2)(iv) and 164.308(a)(4)") == ["164.312(a)(2)(iv)", "164.308(a)(4)"]
    assert "164.312(a)(2)(iv)" in tokenize("164.312(a)(2)(iv)")


def test_bm25_prefers_matching_document():
    idx = BM25Index(["automatic logoff after inactivity", "encryption of data at rest", "audit controls"])
    top = idx.search("logoff inactivity", 3)
    assert top[0][0] == 0 and len(top) == 1


def test_bm25_idf_formula():
    idx = BM25Index(["alpha beta", "alpha", "gamma"])
    assert math.isclose(idx.idf["alpha"], math.log(1 + (3 - 2 + 0.5) / (2 + 0.5)))


def test_rrf_math():
    fused = rrf({"a": [1, 2], "b": [2, 3]})
    assert math.isclose(fused[2], 1 / (RRF_K + 2) + 1 / (RRF_K + 1))
    assert max(fused, key=fused.get) == 2


def test_identifier_pass_puts_regulation_first():
    res = retriever().search("164.312(a)(2)(iv)", k=3)
    assert res["identified_controls"] == ["164.312(a)(2)(iv)"]
    assert res["chunks"][0]["chunk"]["chunk_id"] == "ecfr-164.312(a)(2)(iv)"
    assert res["controls"][0]["control_id"] == "164.312(a)(2)(iv)"


def test_standard_citation_resolves_to_standard():
    assert retriever().identified_controls("what does 164.312(a) say") == ["164.312(a)(1)"]


def test_alias_maps_jargon_to_control():
    res = retriever().search("Do we need a break-glass account?", k=3)
    assert "164.312(a)(2)(ii)" in res["matched_aliases"]
    assert res["controls"][0]["control_id"] == "164.312(a)(2)(ii)"


def test_hard_negative_mfa_is_not_unique_user_id():
    assert retriever().search("do we need MFA?", k=5)["controls"][0]["control_id"] == "164.312(d)"


def test_filters():
    res = retriever().search("encryption", k=10, in_scope_only=True)
    assert all(h["chunk"]["in_scope_v1"] for h in res["chunks"])
    res = retriever().search("encryption", k=10, authority_levels={"regulation"})
    assert all(h["chunk"]["authority_level"] == "regulation" for h in res["chunks"])


class FakeEmbedder:
    """Bag-of-letters embedder: enough to exercise the dense code path offline."""
    model_name = "fake"

    def _vec(self, t):
        v = np.zeros(26, dtype=np.float32)
        for ch in t.lower():
            if "a" <= ch <= "z":
                v[ord(ch) - 97] += 1
        return v

    def embed_documents(self, texts):
        return np.stack([self._vec(t) for t in texts])

    def embed_query(self, text):
        return self._vec(text)


def test_dense_path_is_fused_when_enabled():
    chunks = build_all()
    r = RegulatoryRetriever(chunks, dense=DenseIndex(FakeEmbedder(), [c.embedding_text for c in chunks]))
    res = r.search("automatic logoff", k=5)
    assert "dense" in res["signals_used"]
    assert any("dense" in h["signals"] for h in res["chunks"])
