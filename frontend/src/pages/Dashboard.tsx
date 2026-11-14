import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, AssessmentListItem } from "../api";
import { StatusBar } from "../components/StatusBadge";

export default function Dashboard() {
  const [items, setItems] = useState<AssessmentListItem[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.assessments().then(setItems).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="stack">
      <section className="card hero">
        <div>
          <h1>Find the gaps before an auditor does</h1>
          <p className="muted">
            Upload your policies and procedures. ComplianceGuard checks them against the HIPAA Security Rule Access Control
            standard, 45 CFR § 164.312(a), and its four implementation specifications. Every finding quotes your evidence
            and the guidance behind it, and uncertain findings go to a human reviewer.
          </p>
          <div className="row">
            <Link to="/new" className="btn primary">Start an assessment</Link>
            <Link to="/method" className="btn">How it works</Link>
          </div>
        </div>
        <div className="stack" style={{ gap: 8 }}>
          <div className="section-label" style={{ margin: 0 }}>Workflow</div>
          <div className="flow">
            {["plan", "retrieve", "assess", "verify", "route", "human review", "report"].map((n, i, all) => (
              <span key={n} className="row" style={{ gap: 6 }}>
                <span className="node">{n}</span>
                {i < all.length - 1 && <span className="faint">→</span>}
              </span>
            ))}
          </div>
          <p className="faint" style={{ margin: 0 }}>
            The requirement text always comes from an exact lookup in a reviewed control catalog, never from a model.
          </p>
        </div>
      </section>

      <section className="card">
        <div className="row" style={{ marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>Assessments</h2>
          <span className="spacer" />
          <Link to="/new" className="btn small">New</Link>
        </div>
        {error && <div className="error">{error}</div>}
        {!items && !error && <span className="spinner" />}
        {items && items.length === 0 && (
          <div className="empty">
            No assessments yet. <Link to="/new">Run one</Link>. The fictional sample clinic takes about a second.
          </div>
        )}
        {items && items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Organization</th>
                  <th>Created</th>
                  <th>Evidence</th>
                  <th style={{ minWidth: 160 }}>Results</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id}>
                    <td><Link to={`/assessments/${a.id}`}>{a.org_name}</Link></td>
                    <td className="faint">{new Date(a.created_at).toLocaleString()}</td>
                    <td className="faint">{a.documents.length} file{a.documents.length === 1 ? "" : "s"}</td>
                    <td>
                      <StatusBar counts={a.summary.by_status} total={a.summary.total} />
                      <span className="faint">
                        {a.summary.by_status.met ?? 0} of {a.summary.total} met
                      </span>
                    </td>
                    <td>
                      {a.review_status === "complete" ? (
                        <span className="badge met">Complete</span>
                      ) : (
                        <span className="badge review">Needs review</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
