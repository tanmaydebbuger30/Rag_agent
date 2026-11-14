"""FastAPI backend. Run: uvicorn backend.app.api.main:app --reload

Serves the JSON API under /api and, when frontend/dist exists, the built UI.
"""
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.app import config, storage
from backend.app.assessment.report import render_markdown
from backend.app.assessment.workflow import run_assessment
from backend.app.catalog import all_controls, criteria, in_scope_controls
from backend.app.ingestion.evidence import SUPPORTED, parse_document
from backend.app.retrieval.hybrid import regulatory_retriever

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
SAMPLE_ORG = ("Riverbend Family Clinic (fictional sample)", config.SAMPLE_EVIDENCE_DIR / "riverbend_clinic")

app = FastAPI(title="ComplianceGuard AI", version="1.0.0")


def llm_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@app.get("/api/health")
def health():
    return {"status": "ok", "kb_chunks": len(regulatory_retriever().chunks)}


@app.get("/api/config")
def get_config():
    return {"default_assessor": config.ASSESSOR, "llm_available": llm_available(), "llm_model": config.LLM_MODEL,
            "dense_enabled": config.DENSE_ENABLED, "supported_files": list(SUPPORTED)}


@app.get("/api/controls")
def list_controls():
    reg = regulatory_retriever()
    spec = criteria()
    out = []
    for c in in_scope_controls():
        out.append({**c.model_dump(),
                    "aliases": spec[c.control_id].get("aliases", []),
                    "criteria": [{"id": k["id"], "text": k["text"], "sources": k.get("sources", [])}
                                 for k in spec[c.control_id]["criteria"]],
                    "guidance": [{"chunk_id": g.chunk_id, "citation": g.citation_label, "heading": g.heading,
                                  "text": g.text} for g in reg.guidance_for(c.control_id, k=10)]})
    return out


@app.get("/api/kb/chunks/{chunk_id}")
def get_kb_chunk(chunk_id: str):
    for c in regulatory_retriever().chunks:
        if c.chunk_id == chunk_id:
            return {**c.model_dump(), "citation": c.citation_label}
    raise HTTPException(404, "chunk not found")


@app.get("/api/search")
def search(q: str, k: int = 5, in_scope_only: bool = False, authority: str | None = None):
    if not q.strip():
        raise HTTPException(400, "empty query")
    levels = set(authority.split(",")) if authority else None
    return regulatory_retriever().search(q, k=min(max(k, 1), 20), in_scope_only=in_scope_only, authority_levels=levels)


@app.get("/api/sample-evidence")
def sample_evidence():
    name, folder = SAMPLE_ORG
    return {"org_name": name, "files": [{"filename": p.name, "text": p.read_text(encoding="utf-8")}
                                        for p in sorted(folder.glob("*.md"))]}


def _documents_from_sample():
    _, folder = SAMPLE_ORG
    return [(p.name, p.read_bytes()) for p in sorted(folder.glob("*.md"))]


@app.post("/api/assessments")
async def create_assessment(org_name: str = Form(...), use_sample: bool = Form(False),
                            assessor: Literal["rules", "llm"] | None = Form(None),
                            files: list[UploadFile] = File(default=[])):
    assessor = assessor or config.ASSESSOR
    if assessor == "llm" and not llm_available():
        raise HTTPException(400, "The LLM assessor needs ANTHROPIC_API_KEY on the server. Use the rule-based assessor.")

    raw = _documents_from_sample() if use_sample else []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename} is larger than 10 MB")
        raw.append((Path(f.filename or "upload.txt").name, data))
    if not raw:
        raise HTTPException(400, "Upload at least one evidence document or use the sample evidence.")

    assessment_id = storage.new_id()
    documents, evidence = [], []
    for i, (filename, data) in enumerate(raw, start=1):
        doc_id = f"d{i}"
        try:
            chunks = parse_document(doc_id, filename, data)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        documents.append({"document_id": doc_id, "filename": filename, "bytes": len(data), "chunks": len(chunks)})
        evidence += chunks
    if not evidence:
        raise HTTPException(400, "No text could be extracted from the uploaded documents.")

    result = run_assessment(evidence, assessor=assessor)
    assessment = {"id": assessment_id, "org_name": org_name.strip() or "Unnamed organization",
                  "created_at": storage.now(), "assessor": assessor, "documents": documents,
                  "review_status": "pending_review" if result["review_queue"] else "complete", **result}
    storage.save_assessment(assessment, evidence)
    return assessment


@app.get("/api/assessments")
def list_assessments():
    return storage.list_assessments()


def _load(assessment_id: str) -> dict:
    a = storage.get_assessment(assessment_id)
    if a is None:
        raise HTTPException(404, "assessment not found")
    return a


@app.get("/api/assessments/{assessment_id}")
def get_assessment(assessment_id: str):
    return _load(assessment_id)


@app.get("/api/assessments/{assessment_id}/evidence")
def get_evidence(assessment_id: str):
    _load(assessment_id)
    return [c.model_dump() for c in storage.get_evidence(assessment_id)]


class ReviewIn(BaseModel):
    decision: Literal["accept", "override"]
    status: Literal["met", "partially_met", "not_met", "insufficient_evidence"] | None = None
    note: str = ""
    reviewer: str


@app.post("/api/assessments/{assessment_id}/findings/{control_id}/review")
def review_finding(assessment_id: str, control_id: str, body: ReviewIn):
    a = _load(assessment_id)
    finding = next((f for f in a["findings"] if f["control_id"] == control_id), None)
    if finding is None:
        raise HTTPException(404, "finding not found")
    if body.decision == "override" and body.status is None:
        raise HTTPException(400, "an override needs a status")
    if not body.reviewer.strip():
        raise HTTPException(400, "reviewer name is required")
    finding["review"] = {"decision": body.decision, "status": body.status if body.decision == "override" else finding["status"],
                         "note": body.note.strip(), "reviewer": body.reviewer.strip(), "reviewed_at": storage.now()}
    pending = [f["control_id"] for f in a["findings"] if f["needs_review"] and not f.get("review")]
    a["review_status"] = "pending_review" if pending else "complete"
    storage.update_assessment(a)
    return a


@app.get("/api/assessments/{assessment_id}/report.md", response_class=PlainTextResponse)
def report(assessment_id: str):
    return PlainTextResponse(render_markdown(_load(assessment_id)), media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="complianceguard-{assessment_id}.md"'})


@app.get("/api/catalog/all")
def full_catalog():
    """Every §164.312 control, including the out-of-scope distractors."""
    return [c.model_dump() for c in all_controls().values()]


# --- built frontend (single-page app) ---------------------------------------
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        file = config.FRONTEND_DIST / path
        if path and file.is_file() and config.FRONTEND_DIST in file.resolve().parents:
            return FileResponse(file)
        return FileResponse(config.FRONTEND_DIST / "index.html")
