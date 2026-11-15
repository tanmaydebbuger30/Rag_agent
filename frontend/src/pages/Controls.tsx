import { useEffect, useState } from "react";
import { api, ControlInfo } from "../api";
import KbChunkModal from "../components/KbChunkModal";

export default function Controls() {
  const [controls, setControls] = useState<ControlInfo[] | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api.controls().then(setControls).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Control catalog</h1>
          <p>
            The nine in-scope requirements, parsed from the eCFR XML and reviewed by a person. Requirement text is
            verbatim and is looked up by ID, not retrieved. Criteria are this project's drafted interpretation of the
            HHS and NIST guidance listed under each one.
          </p>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      {!controls && !error && <span className="spinner" />}
      {controls?.map((c) => (
        <article key={c.control_id} className="card">
          <div className="row">
            <span className="mono faint">{c.citation}</span>
            <span className={`badge ${c.requirement_type === "required" ? "accent" : "neutral"}`}>{c.requirement_type}</span>
            <span className="badge neutral">{c.level.replace("_", " ")}</span>
          </div>
          <h2 style={{ marginTop: 4 }}>{c.control_name}</h2>
          <div className="requirement">“{c.requirement_text}”</div>
          {c.requirement_type === "addressable" && (
            <p className="faint">
              Addressable does not mean optional: implement it, or document why it is not reasonable and appropriate and
              adopt an equivalent alternative (45 CFR 164.306(d)(3)).
            </p>
          )}
          <div className="grid grid-2">
            <div>
              <div className="section-label">What evidence should show</div>
              <ul className="plain">
                {c.criteria.map((k) => (
                  <li key={k.id}>
                    {k.text} <span className="faint">({k.sources.join(", ")})</span>
                  </li>
                ))}
              </ul>
              <div className="section-label">Search aliases</div>
              <div className="row" style={{ gap: 6 }}>{c.aliases.map((a) => <span key={a} className="badge neutral">{a}</span>)}</div>
            </div>
            <div>
              <div className="section-label">Guidance passages ({c.guidance.length})</div>
              <ul className="plain">
                {c.guidance.map((g) => (
                  <li key={g.chunk_id}>
                    <button className="btn ghost small" style={{ padding: 0, textAlign: "left" }} onClick={() => setOpen(g.chunk_id)}>
                      {g.heading}
                    </button>
                    <div className="faint">{g.citation}</div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </article>
      ))}
      {open && <KbChunkModal chunkId={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
