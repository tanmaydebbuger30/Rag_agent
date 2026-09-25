# Phase 1 Design — HIPAA Access Control Regulatory Knowledge Base

> Status: **design, awaiting review**. No code has been written yet. Each section
> ends with the decision we are making and why, so it can be defended in an
> interview.

Phase 1 goal: ingest the authoritative HIPAA Access Control requirements and
their interpretive guidance, and make them retrievable **with measurable
quality**, before any agent exists.

---

## 0. The one architectural idea to internalize first

The regulatory knowledge base has two very different kinds of content, and they
deserve two different access paths:

| Content | Size | Access pattern | Mechanism |
|---|---|---|---|
| **Regulation text** (45 CFR §164.312(a)) | 5 controls, ~150 words total | "Give me the requirement for control X" | **Deterministic lookup** in a control catalog, keyed by `control_id` |
| **Guidance** (HHS, NIST SP 800-66r2) + the rest of the Security Rule | Hundreds of passages | "What does this requirement mean / what evidence satisfies it?" and "Which control is this question about?" | **Retrieval** (hybrid search + optional reranking) |

When you already have a primary key, similarity search is the wrong tool: it can
only add error. The legally binding requirement text will therefore always come
from an exact lookup (confidence 1.0 by construction, citation guaranteed
correct). Vector retrieval earns its place where the question is fuzzy:
mapping natural language ("do we need break-glass accounts?") to a control, and
finding the right guidance passage among hundreds of distractors.

This is also what keeps the system honest: the LLM is never asked to "remember"
or reconstruct regulatory text.

---

## 1. Exact V1 scope

### 1.1 Controls that will be **assessed** in V1

All from 45 CFR §164.312 — Technical Safeguards.

| control_id | Name | Level | Requirement type |
|---|---|---|---|
| `164.312(a)(1)` | Access Control | Standard | Required (standards are always required) |
| `164.312(a)(2)(i)` | Unique User Identification | Implementation specification | **Required** |
| `164.312(a)(2)(ii)` | Emergency Access Procedure | Implementation specification | **Required** |
| `164.312(a)(2)(iii)` | Automatic Logoff | Implementation specification | **Addressable** |
| `164.312(a)(2)(iv)` | Encryption and Decryption | Implementation specification | **Addressable** |

**Why "Required vs Addressable" is in scope from day one.** Under §164.306(d),
"addressable" does *not* mean optional. The covered entity must assess whether
the specification is reasonable and appropriate; if it is, implement it; if not,
document why and implement an equivalent alternative measure if reasonable.
So for automatic logoff and encryption, the *absence* of the control is not
automatically `NOT_MET` — a documented risk-based decision is valid evidence.
The later gap-analysis node needs this field to reason correctly, so the catalog
must carry it now.

### 1.2 Content that will be **ingested but not assessed** (context + hard negatives)

| Content | Why we ingest it |
|---|---|
| Rest of §164.312: (b) Audit controls, (c) Integrity, (d) Person or entity authentication, (e) Transmission security | Realistic **distractors**. "Encryption" also appears in §164.312(e)(2)(ii) (transmission); "authentication/MFA" belongs to §164.312(d), not unique user ID. A retriever that can't separate these is not good enough. |
| §164.304 Definitions (access, encryption, user, workforce, …) | The requirement text uses defined terms; the analyzer needs their legal meaning. |
| §164.306(d) Required vs addressable | Needed to interpret addressable specs (above). |
| §164.308(a)(4) Information access management | §164.312(a)(1) explicitly points to it ("access rights as specified in §164.308(a)(4)"). |

Non-assessed content is tagged `in_scope_v1: false` in the control catalog. It
is retrievable, but the planner will never create a task for it in V1.

### 1.3 Explicitly out of scope for Phase 1

Organization evidence (Phase 2), LLM calls of any kind, agents, UI, deployment,
Postgres. Phase 1 is pure ingestion + retrieval + evaluation.

### 1.4 Regulatory version pinning

The codified text will be pinned to a specific eCFR **point-in-time date**
(recorded as `as_of_date` on every chunk). HHS published a Notice of Proposed
Rulemaking in January 2025 that would, among other things, remove the
required/addressable distinction. We will ingest the **currently effective**
codified text only and re-verify its status at ingestion time. Proposed rules
are not requirements, and mixing them in would be a correctness bug.

---

## 2. Source documents

Ranked by **authority level** — a field every chunk carries, because the system
must be able to say "this is the law" vs "this is guidance about the law".

| # | Document | Publisher | `authority_level` | Format | Role |
|---|---|---|---|---|---|
| S1 | 45 CFR Part 164 Subpart C (§§164.304, 164.306, 164.308(a)(4), 164.312) | eCFR / Office of the Federal Register | `regulation` | **XML** via eCFR versioner API | Binding requirement text. Source of the control catalog. |
| S2 | HIPAA Security Series #4 — Technical Safeguards | HHS (CMS) | `official_guidance` | PDF | HHS's own explanation of each implementation specification. |
| S3 | NIST SP 800-66 Rev. 2 — Implementing the HIPAA Security Rule: A Cybersecurity Resource Guide (Feb 2024) | NIST | `supporting_guidance` | PDF | Key activities, descriptions and sample questions per standard — i.e. *what evidence of compliance looks like*. Very useful for Phase 3 gap analysis. |

All three are U.S. Government works (public domain), so raw copies can be
committed to the repo.

**Why XML for the regulation instead of the PDF?** The PDF of the CFR is a
rendering; the XML *is* the structure. Paragraph markers `(a)`, `(1)`, `(i)`
are present as text in paragraph elements, so we can reconstruct the exact
hierarchy (standard → implementation specification) deterministically, with no
layout heuristics. Structure is the hardest thing to recover from a PDF; don't
throw it away and then try to rebuild it.

**Reproducibility.** Raw sources are downloaded once by a script, saved under
`data/raw/regulatory/` together with a `manifest.json` (URL, retrieval date,
SHA-256, `as_of_date`). Ingestion always reads from the snapshot, never from the
network, so the index is reproducible and tests don't depend on a website.

> Environment note: this cloud container's network policy currently blocks
> `www.ecfr.gov` (HTTP 403 from the proxy). Either allow that host (and the HHS /
> NIST hosts) in the environment's network settings, or download the three files
> locally and commit them to `data/raw/regulatory/`.

---

## 3. Document schema

Three layers, each a Pydantic model. Keeping them separate is what lets us
re-chunk or re-embed without re-parsing, and trace any chunk back to bytes on
disk.

```text
SourceDocument  (one per file in data/raw)
   └── Section  (parsed structural unit: CFR paragraph, or PDF heading section)
         └── Chunk  (the unit we embed, index, retrieve and cite)

Control  (curated catalog entry — not derived from retrieval)
```

### 3.1 `SourceDocument`

```python
class SourceDocument(BaseModel):
    doc_id: str                  # "ecfr-45-164-subpartC", "hhs-security-series-4", "nist-sp-800-66r2"
    title: str
    publisher: str               # "eCFR", "HHS", "NIST"
    authority_level: Literal["regulation", "official_guidance", "supporting_guidance"]
    source_url: HttpUrl
    format: Literal["xml", "pdf"]
    as_of_date: date             # eCFR point-in-time date or publication date
    retrieved_at: datetime
    sha256: str                  # of the raw file — detects silent source changes
```

### 3.2 `Control` — the control catalog

Stored as a reviewed, version-controlled file:
`data/frameworks/hipaa_security_rule/controls.yaml`. It is **generated** from the
eCFR XML by a script, then **reviewed by a human** and committed. It is the
single source of truth for "what are the controls and what do they say".

```python
class Control(BaseModel):
    framework: str               # "HIPAA"
    framework_version: str       # "45 CFR 164 Subpart C @ <as_of_date>"
    regulation: str              # "45 CFR Part 164, Subpart C (Security Rule)"
    section: str                 # "164.312"
    control_id: str              # "164.312(a)(2)(i)"
    parent_id: str | None        # "164.312(a)(1)" for implementation specs
    control_name: str            # "Unique User Identification"
    level: Literal["standard", "implementation_specification"]
    requirement_type: Literal["required", "addressable"]
    safeguard_category: Literal["Administrative", "Physical", "Technical"]
    requirement_text: str        # exact codified text, verbatim
    cross_references: list[str]  # ["164.308(a)(4)"]
    in_scope_v1: bool
    citation: str                # "45 CFR § 164.312(a)(2)(i)"
    source_url: HttpUrl          # eCFR deep link to the paragraph
```

Why a hand-reviewed catalog rather than letting the LLM find controls at runtime:
compliance frameworks are **closed, enumerable sets**. Enumerating them once,
correctly, and reviewing them is cheaper and far more reliable than retrieving
them every time. It is also exactly the shape we'll need for CMMC / SOC 2 later:
each framework = one catalog file + its source documents.

### 3.3 `Chunk`

```python
class Chunk(BaseModel):
    chunk_id: str                # deterministic: uuid5(doc_id + section_path + chunk_index + content_hash)
    doc_id: str
    text: str                    # verbatim source text — what we cite and show
    embedding_text: str          # contextual header + text — what we embed (see §4.3)
    metadata: ChunkMetadata      # see §5
```

Note the split between `text` and `embedding_text`: we **cite the verbatim
text** but **embed an enriched version**. Never show the user text that isn't
literally in the source.

---

## 4. Chunking strategy

### 4.1 First principles

An embedding model turns a passage into one vector. That vector is roughly an
"average meaning" of the passage. Consequences:

- **Too big** → several topics blend into one vector; the passage matches many
  queries weakly and none strongly (low precision), and wastes context window.
- **Too small** → the vector lacks context ("Implement a mechanism to encrypt
  and decrypt…" doesn't say *what* or *under which rule*), so paraphrased
  queries miss it (low recall).
- **Crossing a boundary** → a chunk half about Automatic Logoff and half about
  Encryption produces a wrong citation no matter how good retrieval is.

So the rule is: **chunk along the document's own structure first, and use size
limits only as a fallback.** Fixed-size (every N tokens) chunking ignores
structure and is the main reason naive PDF chatbots cite the wrong thing.

### 4.2 Per-source strategy

**S1 — eCFR regulation (structure-exact):**

- One chunk per paragraph node: each standard and each implementation
  specification is its own chunk. These are the legal atoms; they are never
  split and never merged.
- The standard `(a)(1)` and the list header `(a)(2) Implementation
  specifications:` are separate nodes; the header node is attached to the
  standard rather than stored as a near-empty chunk.
- §164.304 definitions: one chunk per defined term.
- Result: a few dozen chunks, each 15–120 tokens, each mapped to exactly one
  `control_id`.

**S2 / S3 — guidance PDFs (structure-aware, size-bounded):**

1. Parse with **PyMuPDF**: extract text blocks with font size/weight, plus the
   PDF outline (`get_toc()`) when present.
2. Build a heading tree (outline first; font-size heuristics as fallback).
3. Section = text under one heading. Sections are the primary chunk unit.
4. If a section exceeds the max size, split it recursively on paragraph →
   sentence boundaries with a **target ~400 tokens, max ~600, ~60-token
   overlap**. Overlap exists only to protect sentences that straddle a split;
   it is not applied across section boundaries.
5. Tables (NIST 800-66r2 presents Key Activities / Description / Sample
   Questions as tables): extract with PyMuPDF `find_tables()`, serialize each
   row as `Key Activity: … | Description: … | Sample questions: …`. A table
   row is one chunk (or rows grouped until the size target). Tables are the
   most likely place for parsing bugs, so they get dedicated tests.
6. Cleaning: remove running headers/footers and page numbers (detected as
   lines repeating on most pages), de-hyphenate line-break hyphens, normalize
   whitespace and Unicode, keep § and paragraph markers intact.
7. Record `page_start`/`page_end` for every chunk — citations need pages.

The 400/600 numbers are a starting point, not a truth. Chunk size is one of the
ablations in the evaluation plan (§9); the data chooses the final value.

**Tool choice — PyMuPDF vs Unstructured vs LLM/vision parsers.** PyMuPDF is
fast, local, deterministic and exposes font metadata, which is all we need for
three born-digital government PDFs. Unstructured adds layout models and many
dependencies — useful for messy scanned enterprise documents, so we'll revisit
it in Phase 2 for org evidence. LLM-based parsing is non-deterministic and
unnecessary here.

### 4.3 Contextual headers (the cheapest big win)

Before embedding, each chunk is prefixed with its location in the hierarchy:

```text
HIPAA Security Rule > 45 CFR 164.312 Technical safeguards > (a)(1) Access control
> (a)(2)(iii) Automatic logoff (Addressable)
Implement electronic procedures that terminate an electronic session after a
predetermined time of inactivity.
```

The raw sentence alone never says "access control" or "HIPAA"; the header adds
the vocabulary queries actually use. This goes into `embedding_text` only. Its
effect is measured as an ablation, not assumed.

### 4.4 Control tagging of guidance chunks

Every guidance chunk gets `control_ids: list[str]` (may be empty or multiple),
assigned by **deterministic rules**, in order:

1. Explicit citation regex, e.g. `164\.312\s*\(a\)\s*\(2\)\s*\(i\)` and variants.
2. The section heading path (e.g., NIST §5.3.1 "HIPAA Standard: Access Control"
   → all chunks under it inherit `164.312(a)(1)`).
3. Exact control-name match inside a section already tagged with the parent
   standard ("Automatic Logoff" under the Access Control section →
   `164.312(a)(2)(iii)`).

No LLM tagging in V1: rules are auditable and testable; an LLM tagger would need
its own evaluation. If rule coverage turns out poor (measurable: % of guidance
chunks in access-control sections left untagged), we revisit.

---

## 5. Metadata schema

Metadata serves three distinct jobs; every field should earn its place in at
least one:

- **Filtering** before/while searching (indexed in the vector DB).
- **Citation** — rendering "NIST SP 800-66r2, §5.3.1, p. <n>".
- **Lineage / debugging** — knowing which ingestion run and model produced a
  vector.

```python
class ChunkMetadata(BaseModel):
    # --- identity & lineage
    kb: Literal["regulatory"]                 # which knowledge base (evidence KB uses "evidence")
    doc_id: str
    chunk_index: int
    content_hash: str                         # sha256 of `text`
    ingestion_run_id: str
    embedding_model: str                      # e.g. "text-embedding-3-small"
    as_of_date: date

    # --- framework / control (FILTER)
    framework: str                            # "HIPAA"
    regulation: str                           # "45 CFR Part 164, Subpart C"
    section: str | None                       # "164.312"
    control_ids: list[str]                    # ["164.312(a)(2)(iii)"]  — list: guidance can cover several
    primary_control_id: str | None
    control_name: str | None
    level: Literal["standard", "implementation_specification", "definition", "guidance"]
    requirement_type: Literal["required", "addressable"] | None
    safeguard_category: str | None            # "Technical Safeguards"
    in_scope_v1: bool

    # --- source / authority (FILTER + CITATION)
    authority_level: Literal["regulation", "official_guidance", "supporting_guidance"]
    source_document: str                      # human title
    source_url: str                           # eCFR paragraph deep link or PDF URL
    section_heading: str | None
    heading_path: list[str]                   # ["5 Considerations...", "5.3 Technical Safeguards", "5.3.1 Access Control"]
    page_start: int | None                    # None for XML sources
    page_end: int | None

    # --- content shape
    content_type: Literal["regulation_text", "definition", "prose", "table_row"]
    token_count: int
```

Indexed (filterable) payload fields: `kb`, `framework`, `control_ids`,
`authority_level`, `level`, `requirement_type`, `in_scope_v1`, `doc_id`.

---

## 6. Embedding strategy

### 6.1 What an embedding is

A function `f(text) → ℝᵈ` trained (contrastively) so that texts with similar
meaning land near each other. "Near" is measured by **cosine similarity**:
`cos(a, b) = a·b / (‖a‖‖b‖)`. With unit-normalized vectors this is just the dot
product. Similarity search = embed the query with the **same** model, return
the chunks whose vectors have the highest cosine to it.

Two properties matter for us:

- Embeddings capture paraphrase well ("session timeout" ≈ "automatic logoff"),
  but are weak at exact identifiers ("164.312(a)(2)(iv)"), rare terms and
  negation. That's why we add sparse/keyword retrieval (§8).
- A cosine score is **not a probability**. 0.82 means nothing on its own; it is
  only meaningful relative to other scores from the same model. We will not
  expose raw cosine as "confidence".

### 6.2 Options

| Option | Dim | Where it runs | Pros | Cons |
|---|---|---|---|---|
| OpenAI `text-embedding-3-small` | 1536 (can be truncated) | API | Strong general quality, trivial ops, negligible cost for a corpus this size | External dependency, data leaves the machine (fine for public regs; matters for org evidence) |
| OpenAI `text-embedding-3-large` | 3072 | API | Better quality | ~6x cost, 2x storage; unclear gain at our scale |
| `BAAI/bge-small-en-v1.5` / `bge-base` | 384 / 768 | Local (sentence-transformers) | Free, offline, reproducible, private | Needs query instruction prefix; CPU inference slower; slightly weaker on some domains |

### 6.3 Decision

- Define an `Embedder` interface (`embed_documents`, `embed_query`, `model_name`,
  `dim`). Nothing else in the codebase knows which model is behind it.
- **Baseline: `text-embedding-3-small`.** **Challenger: `bge-base-en-v1.5`
  (local).** Both are run through the same evaluation; we keep the winner, and
  the privacy argument for a local model gets a real data point before Phase 2
  (where org documents are sensitive).
- Queries and documents always use the same model; the model name and dimension
  are stored in chunk metadata **and** in the collection name, so mixing vectors
  from two models is impossible by construction.
- Embed `embedding_text` (contextual header + text), in batches, with retry and
  a local cache keyed by `(model, sha256(embedding_text))` so re-ingestion
  doesn't re-pay for unchanged chunks.

---

## 7. Vector database design

### 7.1 Choice: Qdrant (vectors) + Postgres later (application state)

| | Qdrant | pgvector |
|---|---|---|
| Hybrid dense + sparse | Native: named dense + sparse vectors per point, server-side fusion (RRF) in one query | Manual: `tsvector` BM25-ish + vector query + fuse in SQL/Python |
| Metadata filtering | Payload indexes, filters applied *during* ANN search | SQL `WHERE`; filtered HNSW can lose recall with selective filters |
| Local dev | Docker, or **embedded in-process mode** (no server) for tests | Needs Postgres running |
| Ops footprint | One more service | Reuses the Postgres we'll need anyway |

**Decision: Qdrant.** Hybrid retrieval and filtered search are central to this
project, and Qdrant makes them first-class and inspectable. The in-process mode
means Phase 1 needs *zero* infrastructure; Docker Compose comes in when the API
does. The honest counter-argument — "one database is simpler" — is valid, and
the retriever interface keeps a pgvector swap possible if we ever want it.

At our scale (hundreds to low thousands of vectors) exact brute-force search
would be fine; Qdrant's HNSW index (an approximate nearest-neighbour graph) only
matters at hundreds of thousands+. We use it because it's the production shape,
not because we need it yet.

### 7.2 Collections

```text
regulatory_kb__<embedder>__v<N>     (alias: regulatory_kb)
evidence_kb__<embedder>__v<N>       (alias: evidence_kb)      ← Phase 2
```

- Two physically separate collections = the two logically separate knowledge
  bases. Different schemas, different lifecycles (regs change rarely; evidence
  is uploaded per assessment), different access control (evidence is
  tenant-scoped by `organization_id`).
- **Aliases** enable blue/green re-indexing: build `…__v2`, evaluate, then
  switch the alias atomically. A new chunking or embedding strategy never
  mutates the index in use.

Per point:

- `id`: the deterministic `chunk_id` → re-running ingestion **upserts**, never
  duplicates.
- vector `dense`: cosine, dim from the embedder.
- vector `sparse`: BM25 sparse vector (Qdrant IDF modifier) for keyword/identifier
  matching.
- `payload`: `text`, `embedding_text`, and all `ChunkMetadata` fields.

---

## 8. Retrieval strategy

Two retrieval operations exist in Phase 1. Both return a typed result with
citations and scores; neither calls an LLM.

### 8.1 `get_requirement(control_id)` — deterministic

Catalog lookup → returns `Control` (verbatim requirement text, requirement type,
citation, URL) + the matching regulation chunk id. Retrieval confidence is 1.0
because nothing is being guessed. This is what later nodes will cite as "the
requirement".

### 8.2 `search_regulatory(query, filters, k)` — hybrid retrieval

```text
query
 ├─ (1) identifier pass: regex for CFR citations → if found, add those controls directly
 ├─ (2) dense search   (top 30, with filters)
 ├─ (3) sparse BM25    (top 30, with filters)
 └─ (4) fuse with Reciprocal Rank Fusion
        RRF(d) = Σ_r 1 / (k_rrf + rank_r(d)),  k_rrf = 60
      → (5) optional cross-encoder rerank of top 20
      → (6) return top k (default 5) chunks
      → (7) aggregate by control_id → ranked list of candidate controls
```

**Why each piece:**

- **Hybrid.** Dense handles paraphrase ("idle session lock" → automatic logoff);
  BM25 handles exact terms and citations ("164.312(a)(2)(iv)", "emergency
  access"). RRF fuses by *rank*, so we never have to put a cosine score and a
  BM25 score on the same scale.
- **Metadata filters.** e.g. `authority_level=regulation` when we want only
  binding text; `control_ids ∋ X` when fetching guidance for a known control.
  Filtering shrinks the candidate set to what's legitimately relevant, which
  is the most reliable precision gain available.
- **Reranking (optional, evaluation-gated).** A bi-encoder (the embedder)
  encodes query and chunk separately — fast but coarse. A cross-encoder
  (e.g. `BAAI/bge-reranker-base`, local) reads query + chunk *together* and
  scores relevance directly — slower but sharper. We use it only on the top ~20.
  It is added only if the ablation shows a gain on the dev set.
- **Multi-query / query rewriting.** Deferred until an LLM is in the loop
  (Phase 3/4). For Phase 1 we instead use a small curated **synonym map per
  control** in the catalog (`aliases: ["session timeout", "screen lock",
  "idle logout"]`) appended to the sparse query. Deterministic, testable, and
  a useful baseline to beat once LLM query rewriting arrives.

### 8.3 Control resolution (preview of the planner's retrieval)

"Evaluate our organization against HIPAA Access Control" → scope keyword match
against the catalog → `164.312(a)(1)` and its children where `in_scope_v1`.
Free-text questions fall back to §8.2 step (7). The LLM planner (Phase 4) will
sit on top of this, not replace it.

### 8.4 Retrieval confidence

Exact lookup → 1.0. For search results we return the raw signals (fused rank,
rerank score, top-1 vs top-2 margin, whether the identifier pass fired) rather
than inventing a number. A calibrated `retrieval_confidence` is built in the
evaluation phase by checking, on the labeled set, how often a given score band
is actually correct. Until then the field is documented as uncalibrated.

---

## 9. Evaluation plan

### 9.1 Gold dataset (Phase 1 slice)

Target: **~70 hand-labeled queries**, split 50 dev / 20 held-out test (tuning
only ever looks at dev).

```json
{
  "query_id": "reg-017",
  "query": "Do we have to log users out automatically after they walk away from a workstation?",
  "query_type": "paraphrase",
  "expected_control_ids": ["164.312(a)(2)(iii)"],
  "expected_chunk_ids": ["…", "…"],
  "in_scope_v1": true,
  "notes": "Should not return 164.310(b) workstation use as top-1"
}
```

Query types, deliberately mixed so aggregate numbers can't hide weaknesses:

| Type | Example | Expected |
|---|---|---|
| Verbatim / citation | "164.312(a)(2)(i)" | (a)(2)(i) |
| Paraphrase | "every employee needs their own login" | (a)(2)(i) |
| Practitioner jargon | "break-glass account procedure" | (a)(2)(ii) |
| Practitioner jargon | "15-minute idle screen lock" | (a)(2)(iii) |
| Hard negative | "encrypt ePHI on laptops" vs "TLS for data in transit" | (a)(2)(iv) vs (e)(2)(ii) |
| Hard negative | "do we need MFA?" | 164.312(d), **not** (a)(2)(i) |
| Definitional | "what counts as 'access' under HIPAA?" | §164.304 definition |
| Out of V1 scope | "audit log retention" | 164.312(b), `in_scope_v1: false` |

**Labeling protocol:** I draft candidate queries and labels; **you review and
correct every label** before it is frozen. Labels produced by the same model
being evaluated, unreviewed, would make the evaluation circular. The dataset is
versioned in `data/eval/regulatory_retrieval_v1.jsonl` and mirrored as a
Langfuse dataset.

### 9.2 Metrics

**Ingestion correctness (unit tests, must be 100%):**

- All 5 in-scope controls exist in the catalog; `requirement_text` matches the
  eCFR XML verbatim; `requirement_type` correct.
- No regulation chunk spans two controls; every regulation chunk has exactly
  one `primary_control_id`.
- Idempotency: ingesting twice yields identical chunk ids and point count.
- Citation resolvability: for every PDF chunk, its `text` is found on
  `page_start..page_end` of the raw PDF.
- Table extraction: known NIST 800-66r2 Access Control key-activity rows are
  present and intact.

**Retrieval quality (on the labeled set):**

- **Control-level:** Hit@1, Recall@5, MRR over `expected_control_ids` — "did we
  find the right control?"
- **Chunk-level:** Recall@k, Precision@k (k = 3, 5, 10), nDCG@10 — "did we find
  the right passages, ranked well?"
- **Hard-negative confusion:** how often a distractor control outranks the
  correct one (reported per pair, e.g. (a)(2)(iv) vs (e)(2)(ii)).
- Reported per `query_type`, not only as an average.

Definitions (so we implement them exactly):
`Recall@k = |relevant ∩ top_k| / |relevant|`,
`Precision@k = |relevant ∩ top_k| / k`,
`MRR = mean(1 / rank of first relevant result)`.

**Operational:** retrieval latency p50/p95 per strategy, embedding
tokens/cost per ingestion run.

### 9.3 Ablations (each one a row in a results table produced by a script)

1. Dense only vs BM25 only vs hybrid (RRF)
2. With vs without contextual headers
3. Guidance chunk target size: 256 / 400 / 800 tokens
4. Embedder: `text-embedding-3-small` vs `bge-base-en-v1.5`
5. With vs without cross-encoder reranking
6. With vs without the per-control alias map

Results are written to `eval_results/` with the git commit, dataset version and
config that produced them. **No number goes into the README unless it came out
of this runner.**

### 9.4 Observability from day one (Langfuse, minimal)

Phase 1 already emits Langfuse traces for retrieval calls: one span per
`search_regulatory` call with query, filters, per-stage candidates (dense,
sparse, fused, reranked) with scores, and latency. Evaluation runs are recorded
as Langfuse dataset runs with the metrics as scores. This is deliberately thin;
Phase 6 formalizes dashboards. Getting it in now means when Phase 4 adds the
graph, retrieval spans already nest inside node spans.

---

## 10. Phase 1 code layout

```text
backend/
  app/
    schemas/          regulatory.py      # SourceDocument, Control, Chunk, ChunkMetadata, RetrievalResult
    ingestion/        fetch_sources.py   # download + manifest (run once)
                      ecfr_parser.py     # XML → Sections (hierarchy from paragraph markers)
                      pdf_parser.py      # PyMuPDF → Sections (+ tables)
                      cleaning.py
                      chunking.py
                      control_tagger.py
                      regulatory_ingestion.py   # orchestrates parse → chunk → tag → embed → upsert
    rag/              embedding_service.py      # Embedder interface + OpenAI / local impls
                      vector_store.py           # Qdrant collection mgmt, upsert, search
    retrieval/        regulatory_retriever.py   # get_requirement, search_regulatory (hybrid + RRF)
    reranking/        reranker.py               # optional cross-encoder
    observability/    langfuse_client.py
    evaluation/       retrieval_metrics.py, run_retrieval_eval.py
  tests/
data/
  raw/regulatory/          # source snapshots + manifest.json
  frameworks/hipaa_security_rule/controls.yaml
  eval/regulatory_retrieval_v1.jsonl
```

## 11. Implementation order (each step is tested before the next)

1. **Source snapshot** — fetch script + manifest; commit raw files.
2. **eCFR parser → control catalog** — generate `controls.yaml`; you review it.
   Unit tests for verbatim text and hierarchy.
3. **PDF parser + cleaning + chunking** for S2/S3; inspect chunks by eye (a
   small script dumps them to a readable file), then tests.
4. **Control tagger** — rules + coverage report.
5. **Embedder interface + Qdrant store** — dense only first; ingestion becomes
   idempotent end to end.
6. **Draft gold dataset** → your review → freeze v1.
7. **Metrics + eval runner** → baseline numbers for dense-only.
8. **Sparse + RRF hybrid**, then the ablations in §9.3; keep only what the dev
   set justifies; confirm once on the test split.
9. **Langfuse spans** on retrieval and eval runs.

## 12. Decisions needed from you before step 1

1. **Embedding provider:** do you have an OpenAI API key for the baseline, or
   should the baseline be the local `bge` model (fully offline, free)?
2. **Network:** allow `www.ecfr.gov`, `www.hhs.gov`, `nvlpubs.nist.gov` for this
   environment, or download the three source files yourself and commit them.
3. **Langfuse:** Langfuse Cloud (free tier, fastest) or self-hosted via Docker?
