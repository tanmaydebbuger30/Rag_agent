"""Citation verification: the check that keeps findings grounded.

Every cited quote must appear verbatim (whitespace-normalized) in the evidence
chunk it names, and that chunk must be one the assessor was actually given.
A "met" status must also cite something. Failures do not silently pass: the
finding is routed to a human reviewer with the problems listed.
"""
import re

from backend.app.schemas.assessment import Finding
from backend.app.schemas.chunks import EvidenceChunk


def _norm(text: str) -> str:
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_finding(finding: Finding, evidence: list[EvidenceChunk]) -> Finding:
    by_id = {c.chunk_id: _norm(c.text) for c in evidence}
    problems = []
    citations = [c for r in finding.criteria for c in r.citations] + finding.contradictions
    for cite in citations:
        if cite.chunk_id not in by_id:
            problems.append(f"cites unknown chunk {cite.chunk_id}")
        elif _norm(cite.quote) not in by_id[cite.chunk_id]:
            problems.append(f"quote not found in {cite.chunk_id}: \"{cite.quote[:80]}\"")
    for r in finding.criteria:
        if r.satisfied and not r.citations:
            problems.append(f"criterion {r.criterion_id} marked satisfied without a citation")
    if finding.status == "met" and not citations:
        problems.append("status is met but nothing is cited")

    finding.verification = {"passed": not problems, "checked_citations": len(citations), "problems": problems}
    if problems:
        finding.needs_review = True
        finding.review_reasons.append("citation verification failed")
    if finding.confidence == "low":
        finding.needs_review = True
        finding.review_reasons.append("assessor reported low confidence")
    return finding
