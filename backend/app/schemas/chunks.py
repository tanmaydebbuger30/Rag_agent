from typing import Literal
from pydantic import BaseModel


AuthorityLevel = Literal["regulation", "official_guidance", "supporting_guidance"]


class RegulatoryChunk(BaseModel):
    """One retrievable passage of regulation or guidance."""

    chunk_id: str                      # "ecfr-164.312(a)(2)(i)", "hhs-ts-05", "nist-5.3.1-03"
    doc_id: str                        # "ecfr-45-164-subpartC", "hhs-security-series-4", "nist-sp-800-66r2"
    source: str                        # human title of the source document
    authority_level: AuthorityLevel
    heading: str
    heading_path: list[str]
    control_ids: list[str]             # may be empty or several
    primary_control_id: str | None
    requirement_type: Literal["required", "addressable"] | None
    in_scope_v1: bool
    page_start: int | None             # None for XML sources
    page_end: int | None
    content_type: Literal["regulation_text", "prose", "table_row"]
    text: str                          # verbatim source text: what we cite and show
    embedding_text: str                # contextual header + text: what we index

    @property
    def citation_label(self) -> str:
        if self.page_start is None:
            return self.source
        pages = f"p. {self.page_start}" if self.page_start == self.page_end else f"pp. {self.page_start}-{self.page_end}"
        return f"{self.source}, {pages}"


class EvidenceChunk(BaseModel):
    """One passage of an organization's uploaded evidence document."""

    chunk_id: str                      # "<document_id>-c003"
    document_id: str
    filename: str
    heading: str | None
    page: int | None
    text: str
