# ComplianceGuard AI — Project Journal

A running record of what has been built, why, and what was learned along the
way. It is written to be re-read before an interview: every decision here is
one you should be able to explain out loud.

> Status as of this entry: **Phase 1, Step 2 complete** — the HIPAA Access
> Control catalog (`controls.yaml`) is generated, reviewed and covered by 4
> passing `pytest` tests. Next: Step 3, parsing and chunking the guidance PDFs. No AI model, embeddings or retrieval have been built yet.
> No performance metrics exist yet, so none are claimed.

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
| 3 | Parse + chunk guidance PDFs (HHS, NIST) | ⏳ next |
| 4 | Tag guidance chunks with control IDs | ⬜ |
| 5 | Embeddings + Qdrant vector store | ⬜ |
| 6 | Gold evaluation dataset (you review labels) | ⬜ |
| 7 | Retrieval metrics + eval runner | ⬜ |
| 8 | Hybrid search (dense + BM25 + RRF), ablations | ⬜ |
| 9 | Langfuse tracing on retrieval | ⬜ |

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

---

## 9. Command cheat sheet

```bash
cd ~/projects/Rag_agent
source .venv/bin/activate                        # prompt shows (.venv)
python -m backend.app.ingestion.ecfr_parser      # regenerate controls.yaml
python -m pytest backend/tests -v                # run tests
python -m pip install <pkg> && python -m pip freeze > requirements.txt
git status / git add <files> / git commit -m "..." / git push
```

---

## 10. How to keep this journal updated

After each step, add: a row in the progress tracker, a short "what / why / how"
under Section 4, any new decision to Section 6, any bug to Section 7. Only
record metrics that came from an actual run, along with the command that
produced them.
