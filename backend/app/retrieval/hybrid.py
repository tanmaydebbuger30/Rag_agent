"""Hybrid retrieval over the regulatory KB and over an organization's evidence.

Pipeline for search_regulatory(query):
  1. identifier pass  - CFR citations in the query select those controls directly
  2. alias match      - practitioner terms ("break-glass") add the control's name to the
                        BM25 query and rank that control's chunks as one more RRF list
  3. BM25             - keyword ranking (always on)
  4. dense            - embedding ranking (only when CG_DENSE=1)
  5. RRF fusion       - RRF(d) = sum_r 1 / (k + rank_r(d)), k = 60
  6. control ranking  - fused chunk scores aggregated per control_id

RRF fuses by rank, so BM25 scores and cosine similarities never have to be put
on the same scale. Raw signals are returned with every hit; none of them is a
calibrated probability.
"""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

from backend.app import config
from backend.app.catalog import all_controls, criteria
from backend.app.retrieval.bm25 import BM25Index
from backend.app.retrieval.text import find_citations
from backend.app.schemas.chunks import EvidenceChunk, RegulatoryChunk

RRF_K = 60


def rrf(rankings: dict[str, list[int]], k: int = RRF_K) -> dict[int, float]:
    """Reciprocal Rank Fusion of several ranked lists of doc indexes (best first)."""
    fused: dict[int, float] = defaultdict(float)
    for ranked in rankings.values():
        for rank, idx in enumerate(ranked, start=1):
            fused[idx] += 1.0 / (k + rank)
    return dict(fused)


@dataclass
class Hit:
    index: int
    score: float                              # fused RRF score
    signals: dict[str, dict] = field(default_factory=dict)   # {"bm25": {"rank": 1, "score": 7.2}, ...}


def fuse(rankings: dict[str, list[tuple[int, float]]], k: int) -> list[Hit]:
    fused = rrf({name: [i for i, _ in ranked] for name, ranked in rankings.items()})
    hits = {i: Hit(i, s) for i, s in fused.items()}
    for name, ranked in rankings.items():
        for rank, (i, raw) in enumerate(ranked, start=1):
            hits[i].signals[name] = {"rank": rank, "score": round(raw, 4)}
    return sorted(hits.values(), key=lambda h: h.score, reverse=True)[:k]


def _make_dense(texts):
    if not config.DENSE_ENABLED:
        return None
    from backend.app.retrieval.dense import DenseIndex, FastEmbedEmbedder

    return DenseIndex(FastEmbedEmbedder(config.DENSE_MODEL), texts)


class RegulatoryRetriever:
    def __init__(self, chunks: list[RegulatoryChunk], dense=None, use_aliases: bool = True,
                 use_identifiers: bool = True):
        self.chunks = chunks
        self.bm25 = BM25Index([c.embedding_text for c in chunks])
        self.dense = dense
        self.use_aliases = use_aliases
        self.use_identifiers = use_identifiers
        self.aliases = {cid: spec.get("aliases", []) for cid, spec in criteria().items()}

    # -- query understanding -------------------------------------------------
    def identified_controls(self, query: str) -> list[str]:
        if not self.use_identifiers:
            return []
        known = all_controls()
        found = []
        for cite in find_citations(query):
            # "164.312(a)" means the standard 164.312(a)(1)
            for candidate in (cite, cite + "(1)"):
                if candidate in known and candidate not in found:
                    found.append(candidate)
                    break
        return found

    def matched_aliases(self, query: str) -> dict[str, list[str]]:
        if not self.use_aliases:
            return {}
        q = query.lower()
        out = {}
        for cid, aliases in self.aliases.items():
            hits = [a for a in aliases if re.search(rf"(?<![a-z]){re.escape(a.lower())}(?![a-z])", q)]
            if hits:
                out[cid] = hits
        return out

    # -- search --------------------------------------------------------------
    def search(self, query: str, k: int = 5, in_scope_only: bool = False,
               authority_levels: set[str] | None = None, control_id: str | None = None) -> dict:
        allowed = {
            i for i, c in enumerate(self.chunks)
            if (not in_scope_only or c.in_scope_v1)
            and (authority_levels is None or c.authority_level in authority_levels)
            and (control_id is None or control_id in c.control_ids)
        }
        identified = self.identified_controls(query)
        aliases = self.matched_aliases(query)
        expanded = query
        for cid in aliases:
            expanded += " " + all_controls()[cid].control_name

        depth = max(30, k)
        rankings: dict[str, list[tuple[int, float]]] = {"bm25": self.bm25.search(expanded, depth, allowed)}
        if self.dense is not None:
            rankings["dense"] = self.dense.search(query, depth, allowed)
        if identified:
            rankings["identifier"] = self._tagged(identified, allowed)
        if aliases:
            rankings["alias"] = self._tagged(list(aliases), allowed)

        hits = fuse(rankings, depth)
        return {
            "query": query,
            "expanded_query": expanded,
            "identified_controls": identified,
            "matched_aliases": aliases,
            "signals_used": list(rankings),
            "chunks": [self._hit_dict(h) for h in hits[:k]],
            "controls": self._rank_controls(hits),
        }

    def _tagged(self, control_ids: list[str], allowed: set[int]) -> list[tuple[int, float]]:
        """Chunks tagged with any of the controls: regulation text first, then HHS, then NIST."""
        order = {"regulation": 0, "official_guidance": 1, "supporting_guidance": 2}
        ranked = sorted((i for i in allowed if set(self.chunks[i].control_ids) & set(control_ids)),
                        key=lambda i: (order[self.chunks[i].authority_level], i))
        return [(i, 1.0) for i in ranked]

    def _hit_dict(self, hit: Hit) -> dict:
        c = self.chunks[hit.index]
        return {"chunk": c.model_dump(), "citation": c.citation_label,
                "rrf_score": round(hit.score, 5), "signals": hit.signals}

    def _rank_controls(self, hits: list[Hit]) -> list[dict]:
        # A control scores as its best chunk. Summing would favour controls that
        # simply have more chunks (the Access Control standard has nine NIST rows).
        best: dict[str, float] = {}
        for h in hits:
            for cid in self.chunks[h.index].control_ids:
                best[cid] = max(best.get(cid, 0.0), h.score)
        controls = all_controls()
        ranked = sorted(best.items(), key=lambda x: x[1], reverse=True)
        return [{"control_id": cid, "control_name": controls[cid].control_name if cid in controls else cid,
                 "in_scope_v1": controls[cid].in_scope_v1 if cid in controls else False,
                 "score": round(s, 5)} for cid, s in ranked]

    def guidance_for(self, control_id: str, k: int = 4) -> list[RegulatoryChunk]:
        """Guidance chunks tagged with a control (deterministic, no similarity)."""
        order = {"official_guidance": 0, "supporting_guidance": 1}
        tagged = [c for c in self.chunks if control_id in c.control_ids and c.authority_level != "regulation"]
        return sorted(tagged, key=lambda c: (order[c.authority_level], c.chunk_id))[:k]


class EvidenceRetriever:
    """Hybrid retrieval over one assessment's evidence chunks."""

    def __init__(self, chunks: list[EvidenceChunk], dense=None):
        self.chunks = chunks
        texts = [f"{c.heading or ''}\n{c.text}" for c in chunks]
        self.bm25 = BM25Index(texts) if chunks else None
        self.dense = dense

    @staticmethod
    def query_for(control_id: str) -> str:
        control = all_controls()[control_id]
        spec = criteria().get(control_id, {})
        parts = [control.control_name, control.requirement_text, *spec.get("aliases", []),
                 *(c["text"] for c in spec.get("criteria", []))]
        return " ".join(parts)

    def search(self, query: str, k: int = 8) -> list[tuple[EvidenceChunk, float, dict]]:
        if not self.chunks:
            return []
        rankings = {"bm25": self.bm25.search(query, 30)}
        if self.dense is not None:
            rankings["dense"] = self.dense.search(query, 30)
        return [(self.chunks[h.index], h.score, h.signals) for h in fuse(rankings, k)]


@lru_cache
def regulatory_retriever() -> RegulatoryRetriever:
    from backend.app.ingestion import build_kb

    if not config.REGULATORY_CHUNKS.exists():
        build_kb.main()
    chunks = build_kb.load_kb()
    return RegulatoryRetriever(chunks, dense=_make_dense([c.embedding_text for c in chunks]))


def evidence_retriever(chunks: list[EvidenceChunk]) -> EvidenceRetriever:
    return EvidenceRetriever(chunks, dense=_make_dense([f"{c.heading or ''}\n{c.text}" for c in chunks]))
