"""The gap-analysis workflow as a LangGraph StateGraph.

    plan -> retrieve -> assess -> verify -> route --(any finding needs review)--> flag_for_review -> report
                                                  \\--(none)------------------------------------> report

Deterministic code controls the flow: the graph never lets a model decide
which controls exist or what the law says. The only model call (optional) is
inside `assess`, and its output is checked by `verify` before anyone sees it.
"""
import operator
import time
from collections import Counter
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app import config
from backend.app.assessment import llm, rules
from backend.app.assessment.verify import verify_finding
from backend.app.catalog import in_scope_controls
from backend.app.retrieval.hybrid import evidence_retriever, regulatory_retriever
from backend.app.schemas.assessment import Finding
from backend.app.schemas.chunks import EvidenceChunk

EVIDENCE_TOP_K = 8


class AssessmentState(TypedDict, total=False):
    assessor: str                                   # "rules" | "llm"
    evidence: list[dict]                            # EvidenceChunk dicts
    control_ids: list[str]
    guidance: dict[str, list[dict]]
    evidence_hits: dict[str, list[dict]]            # control_id -> [{chunk_id, score, signals}]
    findings: list[dict]                            # Finding dicts
    review_queue: list[str]
    summary: dict
    trace: Annotated[list[dict], operator.add]      # appended by every node


def _timed(name):
    def wrap(fn):
        def node(state):
            start = time.perf_counter()
            update, detail = fn(state)
            update["trace"] = [{"node": name, "ms": round((time.perf_counter() - start) * 1000, 1), **detail}]
            return update
        return node
    return wrap


@_timed("plan")
def plan(state):
    ids = [c.control_id for c in in_scope_controls()]
    return {"control_ids": ids}, {"controls": ids, "scope": "HIPAA Security Rule: Access Control + 164.308(a)(2), (a)(6), (a)(8)"}


@_timed("retrieve")
def retrieve(state):
    reg = regulatory_retriever()
    chunks = [EvidenceChunk(**c) for c in state["evidence"]]
    ev = evidence_retriever(chunks)
    guidance, hits = {}, {}
    for cid in state["control_ids"]:
        guidance[cid] = [{"chunk_id": g.chunk_id, "citation": g.citation_label, "heading": g.heading,
                          "excerpt": g.text[:600]} for g in reg.guidance_for(cid)]
        hits[cid] = [{"chunk_id": c.chunk_id, "score": round(s, 5), "signals": sig}
                     for c, s, sig in ev.search(ev.query_for(cid), k=EVIDENCE_TOP_K)]
    detail = {"evidence_chunks": len(chunks), "signals": ["bm25"] + (["dense"] if ev.dense is not None else [])}
    return {"guidance": guidance, "evidence_hits": hits}, detail


@_timed("assess")
def assess(state):
    chunks = [EvidenceChunk(**c) for c in state["evidence"]]
    by_id = {c.chunk_id: c for c in chunks}
    findings, errors = [], []
    for cid in state["control_ids"]:
        guidance = state["guidance"][cid]
        if state["assessor"] == "llm":
            top = [by_id[h["chunk_id"]] for h in state["evidence_hits"][cid]]
            try:
                finding = llm.assess_control(cid, top, guidance)
            except Exception as exc:              # an API failure must not lose the assessment
                errors.append(f"{cid}: {exc}")
                finding = rules.assess_control(cid, chunks, guidance)
                finding.needs_review = True
                finding.review_reasons.append(f"LLM assessment failed ({type(exc).__name__}); rule-based result shown")
        else:
            finding = rules.assess_control(cid, chunks, guidance)
        findings.append(finding.model_dump())
    return {"findings": findings}, {"assessor": state["assessor"], "llm_errors": errors}


@_timed("verify")
def verify(state):
    chunks = [EvidenceChunk(**c) for c in state["evidence"]]
    findings = [verify_finding(Finding(**f), chunks) for f in state["findings"]]
    failed = [f.control_id for f in findings if not f.verification["passed"]]
    return {"findings": [f.model_dump() for f in findings]}, {"verification_failed": failed}


@_timed("route")
def route(state):
    findings = []
    for f in map(lambda d: Finding(**d), state["findings"]):
        if f.status != "met" and f"status is {f.status}" not in f.review_reasons:
            f.review_reasons.append(f"status is {f.status}")
        f.needs_review = bool(f.review_reasons)
        findings.append(f.model_dump())
    queue = [f["control_id"] for f in findings if f["needs_review"]]
    return {"findings": findings, "review_queue": queue}, {"needs_review": queue}


def needs_review(state) -> str:
    return "flag_for_review" if state["review_queue"] else "report"


@_timed("flag_for_review")
def flag_for_review(state):
    return {}, {"queued_for_human_review": state["review_queue"]}


@_timed("report")
def report(state):
    counts = Counter(f["status"] for f in state["findings"])
    summary = {"total": len(state["findings"]), "by_status": dict(counts), "needs_review": len(state["review_queue"]),
               "assessor": state["assessor"]}
    return {"summary": summary}, summary


def build_graph():
    g = StateGraph(AssessmentState)
    for name, fn in [("plan", plan), ("retrieve", retrieve), ("assess", assess), ("verify", verify),
                     ("route", route), ("flag_for_review", flag_for_review), ("report", report)]:
        g.add_node(name, fn)
    g.add_edge(START, "plan")
    g.add_edge("plan", "retrieve")
    g.add_edge("retrieve", "assess")
    g.add_edge("assess", "verify")
    g.add_edge("verify", "route")
    g.add_conditional_edges("route", needs_review, {"flag_for_review": "flag_for_review", "report": "report"})
    g.add_edge("flag_for_review", "report")
    g.add_edge("report", END)
    return g.compile()


GRAPH = build_graph()


def run_assessment(evidence: list[EvidenceChunk], assessor: str | None = None) -> dict:
    assessor = assessor or config.ASSESSOR
    state = GRAPH.invoke({"assessor": assessor, "evidence": [c.model_dump() for c in evidence], "trace": []})
    return {k: state[k] for k in ("findings", "review_queue", "summary", "trace", "evidence_hits")}
