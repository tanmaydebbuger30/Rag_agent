import { FormEvent, useState } from "react";
import { api, SearchResult } from "../api";
import { AuthorityBadge } from "../components/KbChunkModal";

const EXAMPLES = [
  "Do we need a break-glass account?",
  "15-minute idle screen lock",
  "encrypt ePHI on laptops",
  "do we need MFA?",
  "164.312(a)(2)(i)",
  "audit log retention",
];

export default function Search() {
  const [q, setQ] = useState("");
  const [inScope, setInScope] = useState(false);
  const [res, setRes] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(query: string) {
    if (!query.trim()) return;
    setQ(query);
    setBusy(true);
    setError("");
    try {
      setRes(await api.search(query, inScope));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    run(q);
  }

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Knowledge search</h1>
          <p>
            Hybrid retrieval over the regulation text, HHS guidance and NIST SP 800-66r2 (57 chunks, every
            § 164.312 standard). Out-of-scope standards are kept on purpose as hard negatives: "encryption" also
            appears under transmission security, and "MFA" belongs to person or entity authentication.
          </p>
        </div>
      </div>
      <form className="card stack" onSubmit={onSubmit}>
        <div className="row">
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask in your own words or cite a section…" style={{ flex: 1, minWidth: 220 }} aria-label="Search query" />
          <button className="btn primary" disabled={busy}>{busy ? "Searching…" : "Search"}</button>
        </div>
        <div className="row" style={{ gap: 6 }}>
          {EXAMPLES.map((ex) => <button type="button" key={ex} className="btn small" onClick={() => run(ex)}>{ex}</button>)}
        </div>
        <label className="row faint" style={{ gap: 6 }}>
          <input type="checkbox" checked={inScope} onChange={(e) => setInScope(e.target.checked)} /> Only Access Control (in-scope) passages
        </label>
      </form>
      {error && <div className="error">{error}</div>}
      {res && (
        <div className="grid grid-2" style={{ alignItems: "start", gridTemplateColumns: "minmax(260px, 1fr) minmax(300px, 2fr)" }}>
          <div className="card">
            <h3>Most likely controls</h3>
            <ol className="plain">
              {res.controls.slice(0, 5).map((c) => (
                <li key={c.control_id}>
                  <span className="mono">{c.control_id}</span> {c.control_name}{" "}
                  {!c.in_scope_v1 && <span className="badge neutral">out of V1 scope</span>}
                  <div className="signal">best-chunk RRF {c.score}</div>
                </li>
              ))}
            </ol>
            <hr />
            <div className="faint">Signals: {res.signals_used.join(" + ")} fused with RRF (k = 60)</div>
            {res.identified_controls.length > 0 && <div className="faint">Citation found in query: {res.identified_controls.join(", ")}</div>}
            {Object.keys(res.matched_aliases).length > 0 && (
              <div className="faint">Aliases matched: {Object.entries(res.matched_aliases).map(([cid, a]) => `${a.join(", ")} → ${cid}`).join("; ")}</div>
            )}
          </div>
          <div className="stack">
            {res.chunks.length === 0 && <div className="card empty">No passages matched.</div>}
            {res.chunks.map((h, i) => (
              <div key={h.chunk.chunk_id} className="card">
                <div className="row">
                  <strong>#{i + 1}</strong>
                  <AuthorityBadge level={h.chunk.authority_level} />
                  <span className="faint">{h.citation}</span>
                  <span className="spacer" />
                  <span className="signal">
                    {Object.entries(h.signals).map(([k, v]) => `${k} #${v.rank}`).join(" · ")} · rrf {h.rrf_score}
                  </span>
                </div>
                <h3 style={{ marginTop: 6 }}>{h.chunk.heading}</h3>
                <div className="faint">Controls: {h.chunk.control_ids.join(", ") || "none"}</div>
                <p className="chunk-text">{h.chunk.text.length > 700 ? h.chunk.text.slice(0, 700) + "…" : h.chunk.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
