from typing import Literal
from pydantic import BaseModel, Field

Status = Literal["met", "partially_met", "not_met", "insufficient_evidence"]


class EvidenceCitation(BaseModel):
    chunk_id: str
    filename: str
    page: int | None = None
    heading: str | None = None
    quote: str                                   # verbatim span from the evidence chunk


class CriterionResult(BaseModel):
    criterion_id: str
    text: str
    satisfied: bool
    citations: list[EvidenceCitation] = Field(default_factory=list)


class Finding(BaseModel):
    control_id: str
    control_name: str
    citation: str                                # "45 CFR § 164.312(a)(2)(i)"
    requirement_type: Literal["required", "addressable"]
    requirement_text: str
    safeguard_category: str | None = None        # "Technical", "Administrative"
    status: Status
    basis: Literal["implemented", "documented_alternative"] | None = None
    rationale: str
    criteria: list[CriterionResult]
    contradictions: list[EvidenceCitation] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    remediation: list[str] = Field(default_factory=list)
    guidance: list[dict] = Field(default_factory=list)       # [{chunk_id, citation, heading, excerpt}]
    assessor: Literal["rules", "llm"]
    confidence: Literal["low", "medium", "high"] | None = None   # LLM self-report only; not calibrated
    verification: dict = Field(default_factory=dict)          # {"passed": bool, "problems": [...]}
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    review: dict | None = None                                # human decision, once made

    @property
    def final_status(self) -> str:
        if self.review and self.review.get("decision") == "override":
            return self.review["status"]
        return self.status
