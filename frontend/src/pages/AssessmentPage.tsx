import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Assessment, Citation, EvidenceChunk, finalStatus, Finding, Status, STATUS_LABEL } from "../api";
import { StatusBadge, StatusBar } from "../components/StatusBadge";
import KbChunkModal from "../components/KbChunkModal";
import Modal from "../components/Modal";

type Tab = "findings" | "evidence" | "trace";

export default function AssessmentPage() {
  const { id = "" } = useParams();
  const [a, setA] = useState<Assessment | null>(null);
  const [evidence, setEvidence] = useState<EvidenceChunk[]>([]);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("findings");
  const [kbChunk, setKbChunk] = useState<string | null>(null);
  const [evChunk, setEvChunk] = useState<string | null>(null);
  const [onlyReview, setOnlyReview] = useState(false);

  useEffect(() => {
    api.assessment(id).then(setA).catch((e) => setError(e.message));
    api.evidence(id).then(setEvidence).catch(() => undefined);
  }, [id]);

  const counts = useMemo(() => {
    const c: Partial<Record<Status, number>> = {};
    a?.findings.forEach((f) => (c[finalStatus(f)] = (c[finalStatus(f)] ?? 0) + 1));
    return c;
  }, [a]);

  if (error) return <div className="error">{error}</div>;
  if (!a) return <span className="spinner" />;

  const pending = a.findings.filter((f) => f.needs_review && !f.review);
  const shown = onlyReview ? a.findings.filter((f) => f.needs_review) : a.findings;
  const evidenceById = Object.fromEntries(evidence.map((c) => [c.chunk_id, c]));

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <div className="faint"><Link to="/">Assessments</Link> › {a.id}</div>
          <h1>{a.org_name}</h1>
          <p className="faint" style={{ margin: 0 }}>
            {new Date(a.created_at).toLocaleString()} · {a.assessor === "llm" ? "Claude assessor" : "Rule-based assessor"} ·{" "}
            {a.documents.map((d) => d.filename).join(", ")}
          </p>
        </div>
        <div className="row">
          {a.review_status === "complete" ? <span className="badge met">Review complete</span> : <span className="badge review">{pending.length} awaiting review</span>}
          <a className="btn" href={api.reportUrl(a.id)}>Download report (.md)</a>
        </div>
      </div>

      <div className="grid grid-4">
        {(["met", "partially_met", "not_met", "insufficient_evidence"] as Status[]).map((s) => (
          <div key={s} className={`card stat ${s}`}>
            <div className="value">{counts[s] ?? 0}</div>
            <div className="label">{STATUS_LABEL[s]}</div>
          </div>
        ))}
        <div className="card stat review">
          <div className="value">{pending.length}</div>
          <div className="label">Awaiting human review</div>
        </div>
      </div>
      <StatusBar counts={counts} total={a.findings.length} />

      <div>
        <div className="tabs" role="tablist">
          {(["findings", "evidence", "trace"] as Tab[]).map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
              {t === "findings" ? `Findings (${a.findings.length})` : t === "evidence" ? `Evidence (${evidence.length} chunks)` : "Workflow trace"}
            </button>
          ))}
        </div>

        {tab === "findings" && (
          <div className="stack">
            <label className="row faint" style={{ gap: 6 }}>
              <input type="checkbox" checked={onlyReview} onChange={(e) => setOnlyReview(e.target.checked)} /> Show only findings routed to review
            </label>
            {shown.map((f) => (
              <FindingCard key={f.control_id} assessmentId={a.id} finding={f} onUpdate={setA}
                onOpenGuidance={setKbChunk} onOpenEvidence={setEvChunk} />
            ))}
          </div>
        )}

        {tab === "evidence" && (
          <div className="stack">
            {a.documents.map((d) => (
              <div key={d.document_id} className="card">
                <h3>{d.filename} <span className="faint">· {d.chunks} chunks · {Math.ceil(d.bytes / 1024)} KB</span></h3>
                {evidence.filter((c) => c.document_id === d.document_id).map((c) => (
                  <div key={c.chunk_id} style={{ marginTop: 12 }}>
                    <div className="row" style={{ gap: 8 }}>
                      <code>{c.chunk_id}</code>
                      {c.heading && <strong>{c.heading}</strong>}
                      {c.page && <span className="faint">p. {c.page}</span>}
                    </div>
                    <p className="chunk-text">{c.text}</p>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        {tab === "trace" && <Trace a={a} />}
      </div>

      {kbChunk && <KbChunkModal chunkId={kbChunk} onClose={() => setKbChunk(null)} />}
      {evChunk && evidenceById[evChunk] && (
        <Modal title={`${evidenceById[evChunk].filename}${evidenceById[evChunk].heading ? ` › ${evidenceById[evChunk].heading}` : ""}`} onClose={() => setEvChunk(null)}>
          <div className="faint"><code>{evChunk}</code></div>
          <p className="chunk-text">{evidenceById[evChunk].text}</p>
        </Modal>
      )}
    </div>
  );
}

function Quote({ c, bad, onOpen }: { c: Citation; bad?: boolean; onOpen: (id: string) => void }) {
  return (
    <blockquote className={`quote ${bad ? "bad" : ""}`}>
      “{c.quote}”
      <span className="quote-src">
        <button className="btn ghost small" style={{ padding: 0 }} onClick={() => onOpen(c.chunk_id)}>
          {c.filename}{c.heading ? ` › ${c.heading}` : ""}{c.page ? `, p. ${c.page}` : ""}
        </button>
      </span>
    </blockquote>
  );
}

function FindingCard({ assessmentId, finding: f, onUpdate, onOpenGuidance, onOpenEvidence }: {
  assessmentId: string;
  finding: Finding;
  onUpdate: (a: Assessment) => void;
  onOpenGuidance: (id: string) => void;
  onOpenEvidence: (id: string) => void;
}) {
  const status = finalStatus(f);
  return (
    <article className={`card finding ${status}`}>
      <div className="finding-head">
        <div>
          <div className="faint mono">{f.citation}</div>
          <h2 style={{ margin: "2px 0" }}>{f.control_name}</h2>
          <div className="row" style={{ gap: 6 }}>
            <span className={`badge ${f.requirement_type === "required" ? "accent" : "neutral"}`}>{f.requirement_type}</span>
            {f.basis === "documented_alternative" && <span className="badge neutral">documented alternative</span>}
            {f.confidence && <span className="badge neutral">self-reported confidence: {f.confidence}</span>}
            <span className={`badge ${f.verification.passed ? "met" : "not_met"}`}>
              {f.verification.passed ? `citations verified (${f.verification.checked_citations})` : "citation check failed"}
            </span>
          </div>
        </div>
        <div className="stack" style={{ alignItems: "flex-end", gap: 6 }}>
          <StatusBadge status={status} />
          {f.review?.decision === "override" && <span className="faint">assessor said {STATUS_LABEL[f.status]}</span>}
          {f.needs_review && !f.review && <span className="badge review">needs review</span>}
        </div>
      </div>

      <div className="requirement">“{f.requirement_text}”</div>
      <p>{f.rationale}</p>

      <div className="section-label">Criteria</div>
      <ul className="criteria">
        {f.criteria.map((c) => (
          <li key={c.criterion_id}>
            <span className={`check ${c.satisfied ? "yes" : "no"}`} aria-label={c.satisfied ? "satisfied" : "not shown"}>{c.satisfied ? "✓" : "✗"}</span>
            <div>
              <div>{c.text}</div>
              {c.citations.slice(0, 2).map((q) => <Quote key={q.chunk_id + q.quote} c={q} onOpen={onOpenEvidence} />)}
              {!c.satisfied && <div className="faint">Not shown in the evidence.</div>}
            </div>
          </li>
        ))}
      </ul>

      {f.contradictions.length > 0 && (
        <>
          <div className="section-label">Conflicting evidence</div>
          {f.contradictions.map((q) => <Quote key={q.chunk_id + q.quote} c={q} bad onOpen={onOpenEvidence} />)}
        </>
      )}

      {f.remediation.length > 0 && (
        <>
          <div className="section-label">Suggested remediation</div>
          <ul className="plain">{f.remediation.map((r) => <li key={r}>{r}</li>)}</ul>
        </>
      )}

      {!f.verification.passed && (
        <>
          <div className="section-label">Verification problems</div>
          <ul className="plain">{f.verification.problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </>
      )}

      {f.guidance.length > 0 && (
        <>
          <div className="section-label">Guidance consulted</div>
          <div className="row" style={{ gap: 6 }}>
            {f.guidance.map((g) => (
              <button key={g.chunk_id} className="btn small" onClick={() => onOpenGuidance(g.chunk_id)} title={g.citation}>
                {g.citation.split(":")[0]} · {g.heading.length > 48 ? g.heading.slice(0, 48) + "…" : g.heading}
              </button>
            ))}
          </div>
        </>
      )}

      {(f.needs_review || f.review) && <ReviewPanel assessmentId={assessmentId} finding={f} onUpdate={onUpdate} />}
    </article>
  );
}

function ReviewPanel({ assessmentId, finding: f, onUpdate }: { assessmentId: string; finding: Finding; onUpdate: (a: Assessment) => void }) {
  const [reviewer, setReviewer] = useState(() => localStorageGet("cg-reviewer"));
  const [note, setNote] = useState("");
  const [override, setOverride] = useState<Status>(f.status);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);

  async function submit(decision: "accept" | "override") {
    setError("");
    if (!reviewer.trim()) return setError("Enter your name to sign the review.");
    if (decision === "override" && override === f.status) return setError("Pick a different status to override.");
    setBusy(true);
    try {
      localStorageSet("cg-reviewer", reviewer);
      onUpdate(await api.review(assessmentId, f.control_id, { decision, status: decision === "override" ? override : undefined, note, reviewer }));
      setEditing(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (f.review && !editing) {
    return (
      <div className="review-box done">
        <div className="row">
          <strong>{f.review.decision === "accept" ? "Accepted" : `Overridden to ${STATUS_LABEL[f.review.status]}`}</strong>
          <span className="faint">by {f.review.reviewer} · {new Date(f.review.reviewed_at).toLocaleString()}</span>
          <span className="spacer" />
          <button className="btn small" onClick={() => setEditing(true)}>Change</button>
        </div>
        {f.review.note && <p style={{ margin: "6px 0 0" }}>{f.review.note}</p>}
      </div>
    );
  }

  return (
    <div className="review-box">
      <strong>Human review</strong>
      <div className="faint" style={{ marginBottom: 10 }}>Routed because: {f.review_reasons.join("; ") || "reviewer requested a change"}.</div>
      <div className="grid grid-2" style={{ gap: 10 }}>
        <label className="field">Reviewer<input type="text" value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="Your name" /></label>
        <label className="field">
          Override status
          <select value={override} onChange={(e) => setOverride(e.target.value as Status)}>
            {(Object.keys(STATUS_LABEL) as Status[]).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
          </select>
        </label>
      </div>
      <label className="field" style={{ marginTop: 10 }}>Note<textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why you accept or change this finding" /></label>
      {error && <div className="error" style={{ marginTop: 8 }}>{error}</div>}
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn primary" disabled={busy} onClick={() => submit("accept")}>Accept finding</button>
        <button className="btn" disabled={busy} onClick={() => submit("override")}>Override status</button>
        {f.review && <button className="btn ghost" onClick={() => setEditing(false)}>Cancel</button>}
      </div>
    </div>
  );
}

function Trace({ a }: { a: Assessment }) {
  return (
    <div className="stack">
      <div className="card">
        <h3>LangGraph run</h3>
        <p className="faint">Each node of the workflow, its duration, and what it decided.</p>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Node</th><th>ms</th><th>Details</th></tr></thead>
            <tbody>
              {a.trace.map((t, i) => {
                const { node, ms, ...rest } = t;
                return (
                  <tr key={i}>
                    <td><code>{node}</code></td>
                    <td>{ms}</td>
                    <td className="signal">{JSON.stringify(rest)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card">
        <h3>Evidence retrieval per control</h3>
        <p className="faint">Top evidence chunks the hybrid retriever returned for each control (what an LLM assessor would read).</p>
        {Object.entries(a.evidence_hits).map(([cid, hits]) => (
          <div key={cid} style={{ marginTop: 10 }}>
            <strong className="mono">{cid}</strong>
            <div className="row" style={{ gap: 6, marginTop: 4 }}>
              {hits.map((h) => (
                <span key={h.chunk_id} className="badge neutral" title={JSON.stringify(h.signals)}>
                  {h.chunk_id} · bm25 #{h.signals.bm25?.rank ?? "-"}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function localStorageGet(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function localStorageSet(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
}
