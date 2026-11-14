# ComplianceGuard AI

Evidence-based **compliance readiness and gap analysis**, not a PDF chatbot.
ComplianceGuard compares an organization's policies and procedures against the
HIPAA Security Rule, quotes the evidence behind every finding, verifies those
quotes, routes uncertain findings to a human reviewer, and suggests remediation.
It does **not** make legal determinations of compliance.

**V1 scope:** HIPAA Security Rule, Access Control, 45 CFR § 164.312(a): the
standard and its four implementation specifications (unique user
identification, emergency access procedure, automatic logoff, encryption and
decryption).

## What it does

1. **Upload evidence** (Markdown, text or PDF policies), or use the bundled
   *fictional* sample clinic.
2. **Assess** each control: the workflow finds the criteria each control
   expects, quotes the sentence that shows it, and assigns a status: met,
   partially met, not met (the evidence says it is absent), or insufficient
   evidence (nothing addresses it).
3. **Verify** every quote verbatim against the uploaded text.
4. **Review**: findings that are not met, rely on a documented alternative for
   an addressable specification, or fail verification wait for a person to
   accept or override them.
5. **Report**: download a Markdown gap analysis with requirement text,
   evidence quotes, reviewer decisions, remediation and the guidance consulted.

The UI also has a **control catalog** and a **knowledge search** page that shows
how hybrid retrieval ranks the regulation and guidance for any question.

## Architecture

```text
data/raw/regulatory/                       eCFR XML · HHS Security Series #4 PDF · NIST SP 800-66r2 PDF
        │  ingestion/ (ecfr_parser, pdf_explore + hhs_chunks, nist_chunks, build_kb)
        ▼
controls.yaml (reviewed)  ──exact lookup──►  requirement text, citation, required/addressable
regulatory_chunks.jsonl (57 chunks)  ──►  retrieval/ BM25 + citation pass + alias map (+ optional dense) → RRF

uploads ──► ingestion/evidence.py ──► evidence chunks ──► assessment/workflow.py (LangGraph)

   plan → retrieve → assess → verify → route ─┬─► flag_for_review ─┐
                                               └────────────────────┴─► report
        assess: rules.py (offline, default) or llm.py (Claude, structured output)
        verify: every quote must appear verbatim in the cited chunk

api/main.py (FastAPI, SQLite) ◄──► frontend/ (React + Vite)
```

Key design decisions:

- **Binding law is looked up, not retrieved.** The five requirements have known
  IDs; similarity search could only add error. Retrieval is used where the
  question is fuzzy: mapping a question to a control, and finding guidance and
  evidence.
- **Structure-aware chunking.** One chunk per legal paragraph, per HHS heading
  section, and per NIST "Key Activity" table row. Guidance is linked to
  controls by citation, not by name (the HHS PDF misspells "ENCRYTION").
- **Distractors on purpose.** All of § 164.312 is indexed, so "encryption" in
  transmission security and "MFA" under person or entity authentication are
  real hard negatives in the evaluation.
- **Code controls the flow.** The graph, not a model, decides which controls
  exist and what goes to review. The optional LLM only fills in one schema per
  control, and its quotes are checked before anyone sees them.
- **Absence of evidence is not "not met".** "Insufficient evidence" and "not
  met" are separate statuses.

More detail: [docs/phase1_regulatory_kb_design.md](docs/phase1_regulatory_kb_design.md)
(original design) and [docs/project_journal.md](docs/project_journal.md)
(what was built, why, deviations from the design, bugs and lessons).

## Evaluation

`python -m backend.app.evaluation.run_eval` writes
[eval_results/latest.md](eval_results/latest.md). Current results (commit in
that file):

| | Metric | Value |
|---|---|---|
| Retrieval, 38 queries, full config | control Hit@1 / Hit@3 / MRR | 0.737 / 0.842 / 0.816 |
| Retrieval, paraphrase queries only (9) | Hit@1 | 0.444 |
| Rule-based assessor, 18 cases | status accuracy | 0.833 (in-sample, see below) |

**Read these numbers with their caveats.** Both datasets are small drafts
(`label_status: draft_unreviewed`) written by the same author as the alias map
and criteria patterns. The assessor patterns were corrected after a first run on
the same 18 cases (0.667 before), so 0.833 is in-sample. Treat them as a
regression baseline until an independent reviewer relabels the data. Dense
retrieval and the Claude assessor have not been evaluated.

## Run it

Requirements: Python 3.11+, Node 20+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
uvicorn backend.app.api.main:app --reload
# open http://127.0.0.1:8000 and run the sample assessment
```

For UI development, run `npm run dev` in `frontend/` (port 5173, proxies `/api`
to port 8000).

With Docker:

```bash
docker compose up --build        # http://localhost:8000
```

### Deploy for free on Hugging Face Spaces

The workflow `.github/workflows/deploy-hf-space.yml` uploads the app to a
Docker Space on every push to `main` (`deploy/huggingface/sync_space.py`
stages only what the image needs; the guidance PDFs are not uploaded because
the prebuilt `data/processed/regulatory_chunks.jsonl` is used).

1. On huggingface.co, create a **write** access token (Settings → Access Tokens).
2. In this GitHub repo: Settings → Secrets and variables → Actions:
   - secret `HF_TOKEN` = the token
   - variable `HF_SPACE` = `<your-hf-username>/complianceguard-ai`
3. Push to `main`, or run the workflow from the Actions tab. The Space is
   created if it doesn't exist and builds from the Dockerfile.

Manual alternative: `HF_TOKEN=hf_... python deploy/huggingface/sync_space.py <user>/complianceguard-ai`.
Free Spaces sleep after a period without visitors, and assessments are lost
when the Space restarts. Don't add an `ANTHROPIC_API_KEY` to a public Space:
there is no login, so anyone could spend it.

Optional settings (environment variables):

| Variable | Default | Effect |
|---|---|---|
| `ANTHROPIC_API_KEY` | unset | Enables the Claude assessor in the UI |
| `CG_ASSESSOR` | `rules` | Default assessor: `rules` or `llm` |
| `CG_LLM_MODEL` | `claude-opus-5-5` | Model for the Claude assessor |
| `CG_DENSE` | `0` | `1` adds dense retrieval (`pip install -r requirements-dense.txt`; downloads `BAAI/bge-small-en-v1.5` once) |
| `CG_STATE_DIR` | `./var` | Where the SQLite database is stored |

Other commands:

```bash
python -m pytest -q                              # 37 tests
python -m backend.app.ingestion.build_kb         # rebuild the regulatory knowledge base
python -m backend.app.ingestion.ecfr_parser      # regenerate controls.yaml from the eCFR XML
```

## Project layout

```text
backend/app/
  ingestion/   ecfr_parser · pdf_explore · hhs_chunks · nist_chunks · build_kb · evidence
  retrieval/   text (tokenizer) · bm25 · dense (optional) · hybrid (RRF, regulatory + evidence retrievers)
  assessment/  workflow (LangGraph) · rules · llm · verify · report
  evaluation/  metrics · run_eval
  api/         main (FastAPI)
  catalog.py · storage.py · config.py · schemas/
backend/tests/              ingestion, retrieval, assessment, API
data/frameworks/hipaa_security_rule/   controls.yaml (reviewed) · assessment_criteria.yaml (draft)
data/processed/             regulatory_chunks.jsonl (generated)
data/sample_evidence/       fictional clinic policies
data/eval/                  draft gold datasets
frontend/                   React + TypeScript UI
```

## Limitations

- The rule-based assessor checks whether an expected statement is present. It
  cannot judge whether a policy is adequate, and it misses paraphrases it has
  no pattern for. That is why everything short of "met" is reviewed.
- The assessment criteria are this project's reading of HHS and NIST guidance,
  not an official checklist, and need review by a compliance professional.
- V1 assesses Access Control only. Other standards are retrievable but never
  assessed.
- Single-node storage (SQLite) and no authentication: a demo deployment, not a
  multi-tenant service.
- Sources: 45 CFR Part 164 Subpart C (eCFR), HHS HIPAA Security Series #4
  "Technical Safeguards", NIST SP 800-66 Rev. 2. All are U.S. Government works.
