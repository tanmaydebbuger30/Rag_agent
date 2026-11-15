import { DragEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, AppConfig } from "../api";

export default function NewAssessment() {
  const navigate = useNavigate();
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [sample, setSample] = useState<{ org_name: string; files: { filename: string; text: string }[] } | null>(null);
  const [orgName, setOrgName] = useState("");
  const [useSample, setUseSample] = useState(true);
  const [files, setFiles] = useState<File[]>([]);
  const [assessor, setAssessor] = useState<"rules" | "llm">("rules");
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.config().then((c) => {
      setCfg(c);
      setAssessor(c.default_assessor === "llm" && c.llm_available ? "llm" : "rules");
    });
    api.sample().then((s) => {
      setSample(s);
      setOrgName((n) => n || s.org_name);
    });
  }, []);

  function addFiles(list: FileList | null) {
    if (!list) return;
    setFiles((prev) => [...prev, ...Array.from(list).filter((f) => !prev.some((p) => p.name === f.name))]);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDrag(false);
    addFiles(e.dataTransfer.files);
  }

  async function submit() {
    setError("");
    if (!useSample && files.length === 0) {
      setError("Add at least one evidence document, or use the sample evidence.");
      return;
    }
    const form = new FormData();
    form.append("org_name", orgName || "Unnamed organization");
    form.append("use_sample", String(useSample));
    form.append("assessor", assessor);
    files.forEach((f) => form.append("files", f));
    setBusy(true);
    try {
      const a = await api.create(form);
      navigate(`/assessments/${a.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>New assessment</h1>
          <p>
            Scope: HIPAA Security Rule. Technical: Access Control, § 164.312(a), with its four implementation
            specifications. Administrative: Assigned Security Responsibility § 164.308(a)(2), Security Incident
            Procedures § 164.308(a)(6), Evaluation § 164.308(a)(8).
          </p>
        </div>
      </div>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <div className="card stack">
          <label className="field">
            Organization name
            <input type="text" value={orgName} onChange={(e) => setOrgName(e.target.value)} placeholder="e.g. Lakeside Pediatrics" />
          </label>

          <div>
            <div className="section-label" style={{ marginTop: 0 }}>Evidence</div>
            <label className={`choice ${useSample ? "selected" : ""}`}>
              <input type="checkbox" checked={useSample} onChange={(e) => setUseSample(e.target.checked)} />
              <span>
                <strong>Include the fictional sample evidence</strong>
                <span className="faint" style={{ display: "block" }}>
                  Four short policy documents for an invented clinic, written to show met, partially met and not met
                  results.
                </span>
                {sample && (
                  <span className="row" style={{ marginTop: 6, gap: 6 }}>
                    {sample.files.map((f) => (
                      <button key={f.filename} type="button" className="btn small" onClick={(e) => { e.preventDefault(); setPreview(f.filename); }}>
                        {f.filename}
                      </button>
                    ))}
                  </span>
                )}
              </span>
            </label>
          </div>

          <div
            className={`dropzone ${drag ? "drag" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={onDrop}
            onClick={() => input.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
          >
            <strong>Drop policy documents here</strong> or click to choose files
            <div className="faint">{cfg ? cfg.supported_files.join(", ") : ".md, .txt, .pdf"} · up to 10 MB each</div>
            <input ref={input} type="file" multiple hidden accept=".md,.markdown,.txt,.pdf" onChange={(e) => addFiles(e.target.files)} />
          </div>
          {files.length > 0 && (
            <ul className="plain">
              {files.map((f) => (
                <li key={f.name}>
                  {f.name} <span className="faint">({Math.ceil(f.size / 1024)} KB)</span>{" "}
                  <button className="btn ghost small" onClick={() => setFiles(files.filter((x) => x !== f))}>remove</button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card stack">
          <div className="section-label" style={{ marginTop: 0 }}>Assessor</div>
          <label className={`choice ${assessor === "rules" ? "selected" : ""}`}>
            <input type="radio" name="assessor" checked={assessor === "rules"} onChange={() => setAssessor("rules")} />
            <span>
              <strong>Rule-based</strong> <span className="badge neutral">offline</span>
              <span className="faint" style={{ display: "block" }}>
                Checks each criterion with reviewed patterns and quotes the sentence that matched. Deterministic and
                free. It cannot judge whether a policy is adequate, so anything short of "met" goes to review.
              </span>
            </span>
          </label>
          <label className={`choice ${assessor === "llm" ? "selected" : ""} ${cfg?.llm_available ? "" : "disabled"}`}>
            <input type="radio" name="assessor" disabled={!cfg?.llm_available} checked={assessor === "llm"} onChange={() => setAssessor("llm")} />
            <span>
              <strong>Claude</strong> <span className="badge neutral">{cfg?.llm_model ?? "LLM"}</span>
              <span className="faint" style={{ display: "block" }}>
                Reads the top retrieved evidence passages and returns a structured finding. Every quote is checked
                against the source text before it is shown.
                {cfg && !cfg.llm_available && " Not available: the server has no ANTHROPIC_API_KEY."}
              </span>
            </span>
          </label>
          {error && <div className="error">{error}</div>}
          <button className="btn primary" disabled={busy} onClick={submit}>
            {busy ? <><span className="spinner" /> Running assessment…</> : "Run assessment"}
          </button>
        </div>
      </div>

      {preview && sample && (
        <div className="modal-backdrop" onClick={() => setPreview(null)}>
          <div className="card modal" onClick={(e) => e.stopPropagation()}>
            <div className="row">
              <h3 style={{ margin: 0 }}>{preview}</h3>
              <span className="spacer" />
              <button className="btn small" onClick={() => setPreview(null)}>Close</button>
            </div>
            <pre className="chunk-text">{sample.files.find((f) => f.filename === preview)?.text}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
