"""Claude-backed assessor (CG_ASSESSOR=llm, needs ANTHROPIC_API_KEY).

Claude sees only: the verbatim requirement (from the catalog, never generated),
the control's criteria, a few guidance passages, and the top-k retrieved
evidence chunks, each with an id. It must answer in a fixed JSON schema and
quote evidence verbatim by chunk id. verify.py then checks every quote against
the chunk text; a finding with unverifiable citations is routed to review.
"""
import json

from backend.app import config
from backend.app.catalog import criteria, get_control
from backend.app.schemas.assessment import CriterionResult, EvidenceCitation, Finding
from backend.app.schemas.chunks import EvidenceChunk

SYSTEM_PROMPT = """You are a HIPAA Security Rule readiness assessor. You compare one requirement \
against excerpts from an organization's policies and evidence.

Rules:
- Use only the evidence excerpts provided. If they do not show something, treat it as not shown.
- Every citation must quote the excerpt verbatim (copy an exact span) and give its chunk_id.
- "addressable" does not mean optional: it is met either by implementing it, or by a documented \
decision that it is not reasonable and appropriate plus an equivalent alternative measure.
- Status meanings: met (every criterion shown), partially_met (some shown), not_met (evidence says the \
control is absent or contradicts it), insufficient_evidence (nothing relevant in the excerpts).
- This is a readiness gap analysis, not a legal determination of compliance."""

CITATION_SCHEMA = {
    "type": "object",
    "properties": {"chunk_id": {"type": "string"}, "quote": {"type": "string"}},
    "required": ["chunk_id", "quote"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["met", "partially_met", "not_met", "insufficient_evidence"]},
        "basis": {"type": "string", "enum": ["implemented", "documented_alternative", "none"]},
        "rationale": {"type": "string"},
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_id": {"type": "string"},
                    "satisfied": {"type": "boolean"},
                    "citations": {"type": "array", "items": CITATION_SCHEMA},
                },
                "required": ["criterion_id", "satisfied", "citations"],
                "additionalProperties": False,
            },
        },
        "contradictions": {"type": "array", "items": CITATION_SCHEMA},
        "gaps": {"type": "array", "items": {"type": "string"}},
        "remediation": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["status", "basis", "rationale", "criteria", "contradictions", "gaps", "remediation", "confidence"],
    "additionalProperties": False,
}


def build_prompt(control_id: str, evidence: list[EvidenceChunk], guidance: list[dict]) -> str:
    control = get_control(control_id)
    spec = criteria()[control_id]
    lines = [
        f"Requirement: {control.citation} {control.control_name} ({control.requirement_type})",
        f"Verbatim text: \"{control.requirement_text}\"",
        "",
        "Criteria to check:",
        *(f"- {c['id']}: {c['text']}" for c in spec["criteria"]),
        "",
        "Guidance (for interpretation only, not evidence):",
        *(f"- [{g['citation']}] {g['excerpt']}" for g in guidance),
        "",
        "Evidence excerpts:",
    ]
    for chunk in evidence:
        where = chunk.filename + (f", p. {chunk.page}" if chunk.page else "") + (f", section \"{chunk.heading}\"" if chunk.heading else "")
        lines += [f"<excerpt chunk_id=\"{chunk.chunk_id}\" source=\"{where}\">", chunk.text, "</excerpt>"]
    lines += ["", "Assess the requirement against the evidence excerpts."]
    return "\n".join(lines)


def call_claude(prompt: str, client=None) -> dict:
    import anthropic

    client = client or anthropic.Anthropic()
    response = client.beta.messages.create(
        model=config.LLM_MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("The model declined to assess this control")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("The model response was truncated")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def assess_control(control_id: str, evidence: list[EvidenceChunk], guidance: list[dict], client=None) -> Finding:
    control = get_control(control_id)
    spec = criteria()[control_id]
    by_id = {c.chunk_id: c for c in evidence}
    out = call_claude(build_prompt(control_id, evidence, guidance), client=client)

    def cite(c: dict) -> EvidenceCitation:
        chunk = by_id.get(c["chunk_id"])
        return EvidenceCitation(chunk_id=c["chunk_id"], quote=c["quote"],
                                filename=chunk.filename if chunk else "(unknown chunk)",
                                page=chunk.page if chunk else None, heading=chunk.heading if chunk else None)

    texts = {c["id"]: c["text"] for c in spec["criteria"]}
    results = [CriterionResult(criterion_id=r["criterion_id"], text=texts.get(r["criterion_id"], r["criterion_id"]),
                               satisfied=r["satisfied"], citations=[cite(c) for c in r["citations"]])
               for r in out["criteria"]]
    return Finding(
        control_id=control.control_id, control_name=control.control_name, citation=control.citation,
        requirement_type=control.requirement_type, requirement_text=control.requirement_text,
        safeguard_category=control.safeguard_category, status=out["status"], basis=None if out["basis"] == "none" else out["basis"],
        rationale=out["rationale"], criteria=results, contradictions=[cite(c) for c in out["contradictions"]],
        gaps=out["gaps"], remediation=out["remediation"], guidance=guidance, assessor="llm",
        confidence=out["confidence"],
    )
