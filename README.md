# ComplianceGuard AI

Evidence-based **compliance readiness and gap analysis** — not a PDF chatbot.
ComplianceGuard compares regulatory requirements against an organization's
internal policies and evidence, flags potential gaps with citations and
confidence, routes uncertain findings to a human reviewer, and proposes
remediation. It does **not** make legal determinations of compliance.

**V1 scope:** HIPAA Security Rule — Access Control, 45 CFR §164.312(a).

## Stack (planned)

FastAPI · LangGraph · Qdrant · PostgreSQL · Langfuse · Next.js · Docker

## Roadmap

| Phase | Focus | Status |
|---|---|---|
| 1 | Regulatory knowledge base: ingestion, chunking, embeddings, hybrid retrieval, retrieval eval | Design — [docs/phase1_regulatory_kb_design.md](docs/phase1_regulatory_kb_design.md) |
| 2 | Organization evidence RAG (upload, parse, chunk, retrieve) | Not started |
| 3 | Control → evidence mapping with structured assessments | Not started |
| 4 | LangGraph workflow (planner, retrieval, analysis, routing, remediation, report) | Not started |
| 5 | Human-in-the-loop (interrupts, persistence, resume) | Not started |
| 6 | Langfuse observability formalized | Not started |
| 7 | Evaluation suite (retrieval, faithfulness, classification, operational) | Not started |
| 8 | Frontend | Not started |
| 9 | Containerized deployment | Not started |

All reported metrics will come from the evaluation runner in this repo; none are
estimated or synthetic.
