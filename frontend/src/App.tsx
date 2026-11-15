import { NavLink, Link, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import NewAssessment from "./pages/NewAssessment";
import AssessmentPage from "./pages/AssessmentPage";
import Controls from "./pages/Controls";
import Search from "./pages/Search";
import Method from "./pages/Method";

function Logo() {
  return (
    <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
      <path d="M16 2 4 7v8c0 7.5 5.1 13.4 12 15 6.9-1.6 12-7.5 12-15V7z" fill="var(--accent)" />
      <path d="m11 16 3.5 3.5L21.5 12" stroke="#fff" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function App() {
  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand">
            <Logo /> ComplianceGuard AI <small>HIPAA Security Rule</small>
          </Link>
          <nav className="nav">
            <NavLink to="/" end>Assessments</NavLink>
            <NavLink to="/new">New assessment</NavLink>
            <NavLink to="/controls">Controls</NavLink>
            <NavLink to="/search">Knowledge search</NavLink>
            <NavLink to="/method">How it works</NavLink>
          </nav>
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<NewAssessment />} />
          <Route path="/assessments/:id" element={<AssessmentPage />} />
          <Route path="/controls" element={<Controls />} />
          <Route path="/search" element={<Search />} />
          <Route path="/method" element={<Method />} />
          <Route path="*" element={<div className="card empty">Page not found. <Link to="/">Go to assessments</Link></div>} />
        </Routes>
      </main>
      <footer>
        Readiness gap analysis only, not a legal determination of compliance. Regulation text: 45 CFR § 164.312 (eCFR).
        Guidance: HHS Security Series #4, NIST SP 800-66r2.
      </footer>
    </>
  );
}
