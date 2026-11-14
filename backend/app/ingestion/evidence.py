"""Parse an organization's evidence documents into retrievable chunks.

Supported: .md / .txt (split on markdown headings, then paragraphs) and .pdf
(PyMuPDF text blocks, page numbers kept). Chunks stay inside one heading
section and are packed up to MAX_CHARS so a citation never spans two topics.
"""
import re

import pymupdf

from backend.app.schemas.chunks import EvidenceChunk

MAX_CHARS = 1200
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
SUPPORTED = (".md", ".markdown", ".txt", ".pdf")


def _pack(paragraphs: list[str]) -> list[str]:
    """Greedily pack paragraphs into chunks of at most MAX_CHARS (a longer paragraph stays whole)."""
    chunks, current = [], ""
    for p in paragraphs:
        if current and len(current) + len(p) + 2 > MAX_CHARS:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}" if current else p
    if current:
        chunks.append(current)
    return chunks


def _text_sections(text: str) -> list[tuple[str | None, list[str]]]:
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    paragraph: list[str] = []

    def flush():
        if paragraph:
            sections[-1][1].append(" ".join(paragraph).strip() if not paragraph[0].lstrip().startswith(("-", "*", "|"))
                                   else "\n".join(paragraph))
            paragraph.clear()

    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            flush()
            sections.append((m.group(2), []))
        elif not line.strip():
            flush()
        else:
            paragraph.append(line.rstrip())
    flush()
    return [(h, ps) for h, ps in sections if ps]


def parse_text(document_id: str, filename: str, text: str) -> list[EvidenceChunk]:
    chunks = []
    for heading, paragraphs in _text_sections(text):
        for body in _pack(paragraphs):
            chunks.append(EvidenceChunk(chunk_id=f"{document_id}-c{len(chunks) + 1:03d}", document_id=document_id,
                                        filename=filename, heading=heading, page=None, text=body))
    return chunks


def parse_pdf(document_id: str, filename: str, data: bytes) -> list[EvidenceChunk]:
    doc = pymupdf.open(stream=data, filetype="pdf")
    chunks = []
    for page in doc:
        blocks = [" ".join(b[4].split()) for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
        for body in _pack(blocks):
            chunks.append(EvidenceChunk(chunk_id=f"{document_id}-c{len(chunks) + 1:03d}", document_id=document_id,
                                        filename=filename, heading=None, page=page.number + 1, text=body))
    return chunks


def parse_document(document_id: str, filename: str, data: bytes) -> list[EvidenceChunk]:
    name = filename.lower()
    if name.endswith(".pdf"):
        return parse_pdf(document_id, filename, data)
    if name.endswith((".md", ".markdown", ".txt")):
        return parse_text(document_id, filename, data.decode("utf-8", errors="replace"))
    raise ValueError(f"Unsupported file type: {filename} (supported: {', '.join(SUPPORTED)})")
