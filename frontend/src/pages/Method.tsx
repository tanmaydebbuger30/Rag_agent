export default function Method() {
  const steps: [string, string][] = [
    ["plan", "Select the nine in-scope controls from the reviewed catalog: Access Control (§ 164.312(a)) and § 164.308(a)(2), (a)(6) and (a)(8)."],
    ["retrieve", "Look up guidance tagged to each control (HHS, NIST), and rank the organization's evidence chunks for each control with hybrid retrieval."],
    ["assess", "Rule-based: check each criterion with reviewed patterns over every evidence chunk. Claude (optional): read the top-ranked evidence and return a finding in a fixed JSON schema."],
    ["verify", "Check that every quote appears verbatim in the evidence chunk it cites, and that 'met' findings cite something. Failures go to review."],
    ["route", "Conditional edge: any finding that is not met, relies on a documented alternative, or fails verification is queued for a human reviewer."],
    ["report", "Summarize the findings. A reviewer can accept or override each one; the Markdown report shows both the assessor's status and the reviewer's decision."],
  ];
  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>How it works</h1>
          <p>
            Binding law is looked up exactly; guidance and evidence are retrieved; every finding cites its sources; uncertain findings go to a
            person. The system never claims an organization is compliant.
          </p>
        </div>
      </div>

      <section className="card">
        <h2>Two access paths</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Content</th><th>Size</th><th>Access</th></tr></thead>
            <tbody>
              <tr><td>Regulation text, 45 CFR § 164.308 and § 164.312</td><td>41 paragraphs</td><td>Exact lookup by control ID in a reviewed catalog (controls.yaml), parsed from eCFR XML</td></tr>
              <tr><td>Guidance: HHS Security Series #4, NIST SP 800-66r2 §5.1 and §5.3</td><td>91 chunks</td><td>Hybrid retrieval (BM25, optional dense embeddings, fused with reciprocal rank fusion) and control tags</td></tr>
              <tr><td>Organization evidence (uploads)</td><td>Per assessment</td><td>Heading-aware chunking, then hybrid retrieval and criterion matching</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h2>Workflow (LangGraph)</h2>
        <ol className="plain">
          {steps.map(([n, d]) => <li key={n}><code>{n}</code>: {d}</li>)}
        </ol>
      </section>

      <section className="grid grid-2">
        <div className="card">
          <h2>Chunking</h2>
          <ul className="plain">
            <li>eCFR: one chunk per standard or implementation specification (the legal atoms).</li>
            <li>HHS PDF: one chunk per heading section. Headings are found from font size and weight; sidebars and footers are dropped.</li>
            <li>NIST PDF: one chunk per Key Activity table row (activity, description, sample questions), with rows split across pages merged.</li>
            <li>Guidance is linked to controls by citation, not by name: the HHS PDF itself misspells "ENCRYTION".</li>
          </ul>
        </div>
        <div className="card">
          <h2>Known limits</h2>
          <ul className="plain">
            <li>The rule-based assessor checks that expected statements are present; it cannot judge adequacy or detect a paraphrase it has no pattern for.</li>
            <li>The assessment criteria and evaluation labels are drafts written for this project and need review by a compliance professional.</li>
            <li>Retrieval quality numbers come from a small hand-labelled query set (see eval_results/), not from production traffic.</li>
            <li>V1 assesses nine requirements. The other § 164.308 and § 164.312 standards are retrievable but never assessed; physical safeguards (§ 164.310) are not ingested yet.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
