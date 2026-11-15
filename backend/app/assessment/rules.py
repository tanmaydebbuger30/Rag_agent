"""Deterministic, offline assessor.

For each criterion of a control it scans every evidence chunk with the
criterion's regex patterns and cites the sentence that matched. It cannot judge
whether a policy is adequate, only whether the expected statement is present,
so anything short of "met" is routed to a human reviewer.

Status rules:
  contradiction found                          -> not_met
  every criterion satisfied                    -> met
  addressable + documented alternative found   -> met (basis: documented_alternative)
  some criteria satisfied                      -> partially_met
  nothing satisfied                            -> insufficient_evidence
"""
import re

from backend.app.catalog import criteria, get_control
from backend.app.schemas.assessment import CriterionResult, EvidenceCitation, Finding
from backend.app.schemas.chunks import EvidenceChunk

# A sentence ends at . ! ? followed by whitespace or the end, so an address such as
# "security@clinic.example" doesn't cut a quote short. ("e.g. " still does.)
SENTENCE_RE = re.compile(r"(?:[^.!?\n]|[.!?](?=[^\s]))+[.!?]?")
MAX_CITATIONS = 3


def sentence_at(text: str, pos: int) -> str:
    for m in SENTENCE_RE.finditer(text):
        if m.start() <= pos < m.end():
            return m.group(0).strip()
    return text.strip()


def find_matches(patterns: list[str], chunks: list[EvidenceChunk]) -> list[EvidenceCitation]:
    found, seen = [], set()
    for chunk in chunks:
        for pattern in patterns:
            m = re.search(pattern, chunk.text, flags=re.IGNORECASE)
            if not m:
                continue
            quote = sentence_at(chunk.text, m.start())
            if (chunk.chunk_id, quote) in seen:
                continue
            seen.add((chunk.chunk_id, quote))
            found.append(EvidenceCitation(chunk_id=chunk.chunk_id, filename=chunk.filename, page=chunk.page,
                                          heading=chunk.heading, quote=quote))
            break
        if len(found) >= MAX_CITATIONS:
            break
    return found


def assess_control(control_id: str, chunks: list[EvidenceChunk], guidance: list[dict]) -> Finding:
    control = get_control(control_id)
    spec = criteria()[control_id]

    results = []
    for crit in spec["criteria"]:
        cites = find_matches(crit["patterns"], chunks)
        results.append(CriterionResult(criterion_id=crit["id"], text=crit["text"], satisfied=bool(cites), citations=cites))

    contradictions = find_matches(spec.get("contradictions", []), chunks)
    alternative = find_matches(spec.get("alternative", []), chunks) if control.requirement_type == "addressable" else []
    satisfied = [r for r in results if r.satisfied]
    missing = [r for r in results if not r.satisfied]
    basis = None

    if contradictions:
        status = "not_met"
        rationale = (f"The evidence contains {len(contradictions)} statement(s) indicating the control is not in place "
                     f"(for example: \"{contradictions[0].quote}\").")
    elif not missing:
        status, basis = "met", "implemented"
        rationale = f"All {len(results)} expected elements are documented in the evidence."
    elif alternative:
        status, basis = "met", "documented_alternative"
        rationale = ("This specification is addressable and the evidence documents a decision that it is not reasonable "
                     "and appropriate, with an alternative measure (45 CFR 164.306(d)(3)). A reviewer must confirm the "
                     "decision is backed by the risk assessment.")
    elif satisfied:
        status = "partially_met"
        rationale = (f"{len(satisfied)} of {len(results)} expected elements are documented; missing: "
                     + "; ".join(r.text.lower() for r in missing) + ".")
    else:
        status = "insufficient_evidence"
        rationale = "No statement in the uploaded evidence addresses this requirement."

    remediation_by_id = {c["id"]: c["remediation"] for c in spec["criteria"]}
    gaps = [r.text for r in missing] if status != "met" else []
    remediation = [remediation_by_id[r.criterion_id] for r in missing] if status != "met" else []
    if contradictions:
        remediation.insert(0, "Resolve the conflicting statements in the evidence, then re-assess.")

    reasons = []
    if status != "met":
        reasons.append(f"status is {status}")
    if basis == "documented_alternative":
        reasons.append("addressable specification met by a documented alternative")

    return Finding(
        control_id=control.control_id, control_name=control.control_name, citation=control.citation,
        requirement_type=control.requirement_type, requirement_text=control.requirement_text,
        safeguard_category=control.safeguard_category, status=status, basis=basis, rationale=rationale, criteria=results, contradictions=contradictions,
        gaps=gaps, remediation=remediation, guidance=guidance, assessor="rules",
        needs_review=bool(reasons), review_reasons=reasons,
    )
