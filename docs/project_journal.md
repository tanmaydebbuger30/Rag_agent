# ComplianceGuard AI — Project Journal

A running record of what has been built, why, and what was learned along the
way. It is written to be re-read before an interview: every decision here is
one you should be able to explain out loud.

> Status as of this entry (Nov 2026): **V1 end to end** — ingestion of the
> regulation, HHS and NIST guidance; hybrid retrieval with an evaluation
> runner; a LangGraph gap-analysis workflow with citation verification and
> human review; FastAPI + React UI; Docker image. 37 tests pass. The only
> metrics claimed are in `eval_results/latest.md`, on draft labels that still
> need your review (see Steps 6–7).

---

## 1. The 10-year-old version

Imagine a school has a **rulebook** from the government that says things like
"every student must have their own locker key." The school also has its own
**handbook**. A teacher's job is to check, rule by rule, whether the handbook
follows the rulebook. That takes forever.

We are building a **robot helper** for that teacher. But a good robot helper
must never make up rules. So before the robot does anything clever, we did the
boring but important part:

1. **We got the real rulebook** — straight from the government's website, and
   saved a copy so it can never change on us.
2. **We taught the computer to read it properly.** The rulebook is written like
   an outline: (a), then (1), (2), then (i), (ii)... The computer only sees one
   line at a time, like `(ii)`. We wrote code that "keeps its place" — like
   keeping a finger on the outline — so it knows `(ii)` really means
   `164.312(a)(2)(ii)`.
3. **We turned each rule into a neat index card** with the same boxes on every
   card: its number, its name, whether it's a "must do" rule or a "must think
   about it" rule, and its exact words.
4. **We put a strict checker on the cards.** If a card has a box missing, or
   says "Standard" when only "standard" is allowed, the checker refuses it
   immediately.
5. **We saved the 5 cards into one file** (`controls.yaml`), and a human (you)
   checked them.

Later, when the robot helper answers questions, it will read these cards
instead of "remembering" the rules — so it can't invent rules that don't exist.

---

## 2. The project in one paragraph (elevator pitch)

ComplianceGuard AI is an evidence-based compliance readiness system. It compares
regulatory requirements against an organization's policies and evidence,
flags potential gaps with citations and confidence, routes uncertain findings
to a human reviewer, and suggests remediation. It never claims legal
compliance. V1 covers only HIPAA Security Rule Access Control
(45 CFR §164.312(a)). The design separates **binding law**, which is looked up
exactly from a reviewed control catalog, from **guidance and evidence**, which
is found with retrieval (RAG).

---

## 3. Progress tracker

| Step | What | Status |
|---|---|---|
| Design | Phase 1 design doc (`docs/phase1_regulatory_kb_design.md`) | ✅ |
| 0 | Local environment: venv, folders, `.gitignore` | ✅ |
| 1 | Source documents saved to `data/raw/regulatory/` | ✅ |
| 2a | Parse XML paragraphs into markers / title / body | ✅ |
| 2b | Rebuild full IDs with a marker stack | ✅ |
| 2c | Extract name, level, requirement type from titles | ✅ |
| 2d | Validated `Control` objects (Pydantic) | ✅ |
| 2e | Write `controls.yaml`, human review | ✅ |
| 2e | Automated tests (`pytest`, 4 passing) | ✅ |
| 3 | Parse + chunk guidance PDFs (HHS, NIST) | ✅ |
| 4 | Tag guidance chunks with control IDs | ✅ |
| 5 | Retrieval: BM25 + identifier pass + alias map + RRF; optional dense embeddings | ✅ (dense untested here: no model download) |
| 6 | Draft gold evaluation datasets (retrieval + assessment) | ✅ drafted, **your review pending** |
| 7 | Retrieval metrics + eval runner with ablations | ✅ |
| 8 | Evidence ingestion (uploads) | ✅ |
| 9 | Gap-analysis workflow (LangGraph): rules assessor, optional Claude assessor, citation verification, review routing | ✅ |
| 10 | Human review (accept / override), Markdown report, SQLite persistence | ✅ |
| 11 | FastAPI backend + React frontend | ✅ |
| 12 | Docker image | ✅ built and smoke-tested |
| 13 | Free deployment on Render (`render.yaml`): https://complianceguard-ai-l4aq.onrender.com | ✅ live (Hugging Face Docker Spaces now need a paid PRO plan, so we switched) |
| - | Langfuse tracing | ⬜ not done (a per-node trace is stored with each assessment instead) |

---

## 4. What we built, step by step

### Step 0 — Environment

- A **virtual environment** (`.venv`) keeps this project's Python packages
  separate from every other project on the machine.
- `requirements.txt` records exact package versions, so anyone can recreate the
  same environment with `pip install -r requirements.txt`.
- `.gitignore` keeps `.venv/`, `__pycache__/` and `.env` (secrets) out of git.
- The project lives in `~/projects/Rag_agent`, **not** on the iCloud-synced
  Desktop (see Lessons: the 43-second pip).

### Step 1 — Source documents (`data/raw/regulatory/`)

| File | What it is | Authority |
|---|---|---|
| `ecfr_45_164_subpartC.xml` | The HIPAA Security Rule itself (45 CFR Part 164 Subpart C), from the eCFR API | **Binding law** |
| `techsafeguards.pdf` | HHS Security Series #4, Technical Safeguards | Official guidance |
| `NIST.SP.800-66r2.pdf` | NIST's guide to implementing the Security Rule | Supporting guidance |

**Why save copies instead of fetching live?** Reproducibility: every result
can be traced to exact source bytes, and tests don't depend on a website being
up. Regulations change, so the system is pinned to one version of the law.

**Why XML instead of the PDF for the law?** The XML already marks sections
(`<DIV8 N="164.312">`), paragraphs (`<P>`) and titles (`<I>`). Structure is the
hardest thing to recover from a PDF, so we don't throw it away.

**eCFR** = Electronic Code of Federal Regulations, the official online version
of U.S. federal regulations. Address format:
`45 CFR § 164.312(a)(2)(i)` = Title 45 → Part 164 → Section 164.312 → (a) → (2) → (i).

### Step 2a — Read the XML (`backend/app/ingestion/ecfr_parser.py`)

- `find_section(root, "164.312")` walks every `<DIV8>` and returns the one whose
  `N` attribute matches. It **raises an error** if nothing matches (fail loudly
  rather than return `None` and crash somewhere confusing later).
- `paragraph_parts(p)` splits one `<P>` into:
  - **markers**: `(a)(1)` → `["a", "1"]` (regex)
  - **title**: the `<I>` italic text, e.g. `Unique user identification (Required).`
  - **body**: the text after the title (the actual legal requirement)

**Discovery:** the paragraphs are **flat siblings**, not nested. A paragraph
only shows its own marker (`(ii)`), not its full path.

### Step 2b — Rebuild full IDs with a stack

The outline has 4 marker types, each a depth level:

| Marker | Example | Depth |
|---|---|---|
| lowercase letter | `a` | 1 |
| number | `2` | 2 |
| roman numeral | `ii` | 3 |
| uppercase letter | `A` | 4 |

**Algorithm:** keep a list `stack`. For each marker, get its depth `d`, cut the
stack to `d − 1` items, then append the marker. The full ID is the section
number plus the stack in parentheses.

```
(a)(1) → [a, 1]      → 164.312(a)(1)
(2)    → [a, 2]      → 164.312(a)(2)
(i)    → [a, 2, i]   → 164.312(a)(2)(i)
(b)    → [b]         → 164.312(b)          ← a new letter resets everything
```

**The roman-numeral trap:** `i` could be roman one or the letter i. The rule:
it's roman only if it looks roman **and** the stack is at depth 2 or 3.
Context decides, not the character alone.

This is a small **state machine**: the `stack` is the state, and each marker
moves it to the next state.

### Step 2c — Clean titles into fields

`parse_title()` turns `Unique user identification (Required).` into:

| Field | Value | Rule |
|---|---|---|
| `control_name` | `Unique User Identification` | strip prefixes, `(Required)`, trailing `.`; title case with small words (`and`, `or`, `to`…) kept lowercase |
| `level` | `implementation_specification` | `standard` if the title starts with `Standard:` |
| `requirement_type` | `required` | from `(Required)` / `(Addressable)`; standards are always `required` |

Headings like `(2) Implementation specifications:` (empty body, title ends
with `:`) are **skipped as controls but still update the stack**, or their
children would get the wrong ID.

### Step 2d — Validated `Control` objects (`backend/app/schemas/regulatory.py`)

A **class** is a template; an **object** is one filled-in copy. `Control` is a
Pydantic model, a template that **checks** its data when an object is created:

- every field present, with correct types
- `level` must be exactly `standard` or `implementation_specification`
  (`Literal`)
- `requirement_type` must be exactly `required` or `addressable`

`parent_id`: the parent of `(a)(2)(i)` is the **standard** `(a)(1)`, not the
`(a)(2)` heading. The code remembers the most recent standard in
`current_standard`.

`in_scope_v1`: true only for `164.312(a)(1)` and its children, so
`164.312(e)(2)(ii) Encryption` (transmission) is correctly **out of scope**.

### Step 2e — The control catalog (`data/frameworks/hipaa_security_rule/controls.yaml`)

The 5 in-scope controls, written with `yaml.safe_dump`:

| control_id | Name | Type |
|---|---|---|
| 164.312(a)(1) | Access Control | standard (required) |
| 164.312(a)(2)(i) | Unique User Identification | required |
| 164.312(a)(2)(ii) | Emergency Access Procedure | required |
| 164.312(a)(2)(iii) | Automatic Logoff | addressable |
| 164.312(a)(2)(iv) | Encryption and Decryption | addressable |

Rules for this file:
- It is **generated, never hand-edited**. If it's wrong, fix the parser and
  rerun. Rerunning produces byte-identical output (verified).
- The commit that adds it is the **human review sign-off**.
- Run with `python -m backend.app.ingestion.ecfr_parser`.

### Step 2e — Tests (`backend/tests/test_ecfr_parser.py`)

A test is a question with a known answer: `assert <must be true>`. If it's
false, pytest fails and shows both values. `pytest` runs every function whose
name starts with `test_`.

| Test | What it guards |
|---|---|
| `test_marker_level_roman_vs_letter` | roman `i` vs letter `i`, plus the `and`/`or` regression case |
| `test_exactly_five_in_scope_controls` | exactly the 5 right IDs, in order (a count alone would miss wrong IDs) |
| `test_requirements_types` | required vs addressable per control, including "standards are required" |
| `test_requirement_text_is_verbatim` | the legal text matches the regulation exactly (`==`, not "contains") |

The tests import `CONTROLS_PATH` from the parser instead of retyping it, so the
path lives in one place (single source of truth). Each test was broken once on
purpose to prove it can fail.

Run with `python -m pytest backend/tests -v`.

### Steps 3–12: the end-to-end build (written by Claude, Nov 2026)

> Honesty note for interviews: you wrote Steps 0–3c yourself (eCFR parser,
> catalog, tests, `pdf_explore.build_sections`). Steps 3d onward were written by
> Claude when you asked for the project to be completed end to end. Before you
> present any of it as your work, read each file, run it, and be able to answer
> the questions in Section 8b. If you can't explain a part, describe it as
> "the project includes…" rather than "I built…".

**3d. HHS chunks** (`ingestion/hhs_chunks.py`). One chunk per heading section
from `build_sections`. SPEC headings link to a control by the `§ 164.312(...)`
citation; 16pt headings link by exact standard name. We also fixed
`build_sections` to drop sidebar NOTE boxes and footers: they are set in Arial
at the right margin (x ≥ 340) or at 10pt, while the body is Times New Roman.
Result: 18 chunks, 5 in scope.

**3e. NIST chunks** (`ingestion/nist_chunks.py`). NIST SP 800-66r2 §5.3 is
tables of "Key Activity | Description | Sample Questions". One chunk per table
row (`page.find_tables()`). A row whose first cell is not numbered continues
the previous row across a page break, so it is merged. Footnote numbers glued
to words ("Users103") are stripped with a regex that leaves citations like
`§ 164.308(a)(4)` intact. The standard each row belongs to comes from the PDF
outline (`get_toc()`). Result: 27 chunks, 9 under Access Control.

**4. Control tagging.** eCFR: exact. HHS: citation, then name. NIST: outline
section, then implementation-spec names in the key activity
(row 8 "Automatic Logoff and Encryption and Decryption" → both specs).

**5. Retrieval** (`retrieval/`). 57 chunks total (12 eCFR + 18 HHS + 27 NIST).
- BM25 written from scratch (`bm25.py`); CFR citations are single tokens.
- Identifier pass: a citation in the query ranks that control's chunks as an
  extra list. Alias map: practitioner words ("break-glass") do the same.
- Reciprocal Rank Fusion (k = 60) combines the lists by rank.
- Controls are ranked by their **best** chunk. Summing was tried first and
  over-ranked Access Control (a)(1), which simply has the most chunks.
- Dense embeddings are behind an `Embedder` interface with exact cosine
  search in numpy. Off by default (`CG_DENSE=1`), because the model must be
  downloaded and this cloud container blocks Hugging Face. The code path is
  unit-tested with a fake embedder; real embedding quality is **unmeasured**.
- Deviation from the design doc: no Qdrant. At 57 chunks, exact search is
  simpler and has no extra service; the `Embedder`/index interface keeps a
  vector DB swap possible.

**6–7. Evaluation** (`evaluation/run_eval.py`, `data/eval/`, `eval_results/latest.md`).
Two draft datasets: 38 retrieval queries (citation, verbatim, paraphrase,
jargon, hard negative, out of scope; dev/test split) and 18 assessment cases.
Labels are `draft_unreviewed`: written by the same author as the alias map and
patterns, so the numbers are optimistic. Your job: review and correct every
label, then re-run.

| Run | Retrieval Hit@1 (full, 38 q) | Assessor accuracy (18 cases) |
|---|---|---|
| First run | 0.711 (aliases had **no** effect: they only appended a control name to the BM25 query) | 0.667 |
| After fixes | 0.737 (alias match became its own RRF list) | 0.833 |

The assessor fixes were found **on these same cases** (an automatic-logoff
contradiction pattern matched "is not reasonable", and two patterns were too
narrow), so 0.833 is an in-sample number. Paraphrase queries are the weak spot
(Hit@1 0.44): that is the measured case for adding dense retrieval.

**8. Evidence ingestion** (`ingestion/evidence.py`). `.md/.txt` split on
headings, then paragraphs packed up to 1,200 chars; `.pdf` by page text blocks.
Chunks never cross a heading, so a citation never spans two topics.

**9. Workflow** (`assessment/workflow.py`). LangGraph `StateGraph`:
`plan → retrieve → assess → verify → route → (flag_for_review) → report`.
`route` is a conditional edge. `trace` uses an `operator.add` reducer, so
every node appends its timing and decisions.
- Rule-based assessor (`rules.py`): per-criterion regex patterns from
  `assessment_criteria.yaml`, quoting the matched sentence. Contradiction →
  not_met; all criteria → met; addressable + documented alternative → met
  (basis: documented_alternative, always reviewed); some → partially_met;
  none → insufficient_evidence.
- Claude assessor (`llm.py`, optional, needs `ANTHROPIC_API_KEY`): top-8
  evidence chunks + verbatim requirement + criteria → JSON-schema structured
  output. If the API call fails, that control falls back to the rule-based
  result and is flagged for review. **Not run against the real API in this
  environment** (no key); tested with a mocked client.
- Verification (`verify.py`): every quote must appear verbatim in the chunk it
  cites, and the chunk must be one the assessor was given. Failure → review.

**10. Human review + report.** Accept or override each routed finding with a
reviewer name and note; the assessment becomes `complete` when nothing is
pending. The Markdown report shows the assessor's status and the reviewer's
decision side by side. Storage is SQLite with JSON rows (`storage.py`).

**11. API + UI.** FastAPI (`api/main.py`) also serves the built React app
(`frontend/`, Vite + TypeScript + React Router). Pages: assessments list, new
assessment (upload or fictional sample), findings with quotes, review panel,
evidence and trace tabs, control catalog, knowledge search with per-signal
ranks.

**12. Docker.** A two-stage Dockerfile (Node build → Python runtime) and
`docker-compose.yml`. Built and smoke-tested in the cloud container.

---

## 5. Key concepts (glossary)

| Term | Plain meaning |
|---|---|
| **RAG** | Retrieval-Augmented Generation: find relevant text first, then let the LLM answer *using* that text, with citations |
| **Knowledge base** | The collection of documents the system retrieves from. We plan two: regulatory and organization evidence |
| **Control** | One requirement to check, e.g. Unique User Identification |
| **Standard vs implementation specification** | A standard is the main rule; specifications are the detailed parts under it |
| **Required vs addressable** | Required = must implement. Addressable = must *assess*; implement if reasonable, otherwise document why and use an equivalent alternative (§164.306(d)). Addressable ≠ optional |
| **§164.306** | The Security Rule's "general rules": flexibility of approach, required vs addressable, maintenance |
| **Parsing** | Turning raw text or markup into structured data |
| **Schema / Pydantic** | A contract for data shape, checked automatically |
| **Deterministic** | Same input → same output every time, no randomness (unlike an LLM) |
| **Regression test** | A test that locks in a fixed bug so it can't silently come back |
| **Reproducibility** | Anyone can rebuild the exact same result from the saved inputs |
| **BM25** | Keyword ranking: rewards rare query words that appear often in a short document |
| **RRF** | Reciprocal Rank Fusion: add 1/(60 + rank) from each ranked list; fuses lists without comparing their raw scores |
| **Hard negative** | A passage that looks relevant but belongs to another control (transmission encryption vs encryption at rest) |
| **Hit@1 / MRR** | Was the right control first? / average of 1 ÷ rank of the first right answer |
| **Citation verification** | Checking that every quoted sentence really exists, word for word, in the cited chunk |
| **Human-in-the-loop** | Uncertain findings wait for a person to accept or override them |

---

## 6. Design decisions (interview-ready)

**Why look up the law instead of retrieving it?**
The law for V1 is 5 short paragraphs with known IDs. When you have a primary
key, similarity search can only add error. Exact lookup gives the correct text
and a guaranteed-correct citation every time. Retrieval (vector search) is
reserved for fuzzy tasks: mapping a question to a control, and finding
guidance or company evidence.

**Why a reviewed catalog file instead of letting the LLM identify controls?**
Compliance frameworks are closed, enumerable lists. Enumerate once, review
once, and the result is reliable and auditable. It also scales: each new
framework (CMMC, SOC 2) is another catalog file plus its source documents.

**Why rule-based parsing instead of an LLM for the XML?**
Deterministic, testable, free, and exact. Legal text must be verbatim; an LLM
could paraphrase or drop words.

**Why Pydantic?**
Fail loudly at the source. A typo in a field name or value stops the program
where it happens, instead of an agent quietly reasoning over bad data later.
The same approach will validate LLM structured outputs in Phase 3.

**Schema validation vs tests.**
Pydantic checks *shape* (right fields, types, allowed values). Tests check
*truth* (the text matches the law word for word, (iii) really is
addressable). You need both.

**Why track required vs addressable from day one?**
Without it, the gap analysis would wrongly flag a missing addressable control
as NOT_MET even when the organization has a documented risk-based alternative.

**Why ingest out-of-scope sections at all (later)?**
They are realistic distractors. "Encryption" also appears in §164.312(e)(2)(ii)
(transmission), and "authentication/MFA" belongs to §164.312(d). The retriever
must tell them apart, and the evaluation will measure that.

---

## 7. Bugs we hit and what they taught

| Bug | Symptom | Lesson |
|---|---|---|
| `root.iter("DIVB")` instead of `"DIV8"` | "Section not found" | A loop that runs **zero** times looks like "no match". Put a debug print inside the loop to tell them apart. Keep magic strings in named constants |
| `marker in [0-9]` | never matched | `[0-9]` is regex syntax; in Python it's the list `[-9]`. Use `marker.isdigit()` |
| `A and B or C` | `(b)` after `(iv)` became depth 3 → `164.312(a)(2)(b)` | `and` binds tighter than `or`. Use parentheses or `len(stack) in (2, 3)` |
| `marker == ROMAN_RE` / `ROMAN_RE(marker)` | always False / not callable | A compiled regex is an object; call `ROMAN_RE.match(marker)` |
| `marker_level = level - 1` | function overwritten → `'int' object is not callable` | Never reuse a function's name for a variable |
| `section_number = find_section(...)` | searching for an XML element | Know what a function **returns** (element vs string) |
| `stack.appen(...)` | `AttributeError` | Read the last line of the traceback first |
| `full_id` built inside the inner loop (design question) | would print a fake `164.312(a)` | Build results after the loop that completes them |
| `name = "Standard"` | original title lost | One variable, one meaning |
| `.replace("implementation_specification:")` | silently did nothing | Copy text from real output; our labels ≠ source text |
| `("Required") in name` | parentheses ignored | Parentheses outside quotes are grouping, not text |
| Two `parse_title` versions | fixes seemed to vanish | Python uses the **last** definition; save the file (Cmd+S) |
| `in_scope_v11` in the model | Pydantic `Field required` | Validation caught a typo that a dict would have hidden |
| Print loop indented inside the paragraph loop | repeated output | Inside vs after a loop matters |
| `hipaa_secuirty_rule` folder | typo spreading into paths | Fix the code, delete and regenerate the output, don't hand-edit |
| `ModuleNotFoundError: backend` | running by file path | Use `python -m backend.app...` from the repo root |
| pip took 43 s (0.3 s CPU) | project on the iCloud Desktop | Files were offloaded to the cloud. Keep code out of synced folders |
| `git push` 403 as another account | cached credentials | `gh auth login` as the right account, then `gh auth setup-git` |
| Pasted `# comment` broke git | zsh doesn't treat `#` as a comment | Don't paste inline comments into the shell |
| `schemas/` missing after clone | git doesn't store empty folders | `__init__.py` files keep package folders tracked |
| `marker_level("i", ["a","2"] == 3)` in a test | `len(False)` crash | Close the function call first, then compare |
| Test dict mapped ID → whole control | would always fail | Compare like with like: ID → one field |
| Test built values but had no `assert` | passes no matter what | A test with no assert protects nothing |
| Test redefined `CONTROLS_PATH` as `data/framework/...` | `FileNotFoundError` | Import shared constants; the later definition wins |
| `ENOSPC: no space left on device` | editor couldn't save; only 104 MB free | Check `df -h ~`; caches (`~/Library/Caches`) are safe to clear; keep 15+ GB free for models and Docker |

**Debugging techniques used:** read tracebacks bottom-up; `print(repr(x))`
after each transformation step; test a function alone before wiring it in;
break things on purpose to confirm the check works.

---

## 8. Interview practice questions

1. *Why not just put the regulation PDF into a vector database and ask
   questions?* → Section 6: exact lookup for binding text; retrieval for fuzzy
   tasks; citations must be guaranteed correct.
2. *How did you parse the regulation's hierarchy?* → Step 2b: flat paragraphs,
   stack-based state machine, the roman-numeral context rule.
3. *What does "addressable" mean and why does your system care?* → Glossary +
   Section 6.
4. *How do you prevent bad data from reaching the LLM or agents?* → Pydantic at
   creation time + tests for correctness + a reviewed, generated catalog.
5. *How is the system reproducible?* → Pinned source snapshots,
   `requirements.txt`, a deterministic parser, generated (not hand-edited)
   catalog.
6. *Tell me about a bug you found.* → Pick one from Section 7, e.g. the
   `and`/`or` precedence bug that would have produced a non-existent control ID
   silently, and how a regression test now guards it.

### 8b. Questions about the end-to-end build

7. *Why BM25 + identifiers + aliases, and what did the evaluation show?* →
   Step 5 and the table in Steps 6–7, including that aliases first did nothing.
8. *How do you stop the LLM from inventing evidence?* → It only sees retrieved
   chunks with ids; output is schema-constrained; `verify.py` checks every
   quote verbatim; failures go to a human.
9. *Why is "insufficient evidence" different from "not met"?* → Absence of a
   statement in the uploaded documents is not proof the control is missing;
   "not met" needs evidence that says so.
10. *What decides what goes to human review?* → The `route` node: any status
    other than met, a documented alternative, failed verification, low
    self-reported confidence, or an LLM failure.
11. *What would you do next?* → Have a compliance reviewer relabel the eval
    sets; measure dense retrieval on paraphrases; run the Claude assessor
    against the same 18 cases and compare with the rules; add Langfuse.

---

## 9. Command cheat sheet

```bash
cd ~/projects/Rag_agent
source .venv/bin/activate                        # prompt shows (.venv)
python -m backend.app.ingestion.ecfr_parser      # regenerate controls.yaml
python -m pytest backend/tests -v                # run tests (37)
python -m backend.app.ingestion.build_kb         # rebuild data/processed/regulatory_chunks.jsonl
python -m backend.app.evaluation.run_eval        # metrics -> eval_results/latest.md
uvicorn backend.app.api.main:app --reload        # API on :8000 (serves the UI if built)
cd frontend && npm install && npm run build      # build the UI (or `npm run dev` on :5173)
python -m pip install <pkg> && python -m pip freeze > requirements.txt
git status / git add <files> / git commit -m "..." / git push
```

---

## 10. How to keep this journal updated

After each step, add: a row in the progress tracker, a short "what / why / how"
under Section 4, any new decision to Section 6, any bug to Section 7. Only
record metrics that came from an actual run, along with the command that
produced them.
