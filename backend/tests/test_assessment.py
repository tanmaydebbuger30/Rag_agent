import json
from pathlib import Path
from types import SimpleNamespace

from backend.app.assessment import llm, rules, workflow
from backend.app.assessment.verify import verify_finding
from backend.app.config import SAMPLE_EVIDENCE_DIR
from backend.app.ingestion.evidence import parse_document, parse_text

UI, EA, LO, EN = "164.312(a)(2)(i)", "164.312(a)(2)(ii)", "164.312(a)(2)(iii)", "164.312(a)(2)(iv)"


def sample_chunks():
    chunks = []
    for i, p in enumerate(sorted(Path(SAMPLE_EVIDENCE_DIR / "riverbend_clinic").glob("*.md")), start=1):
        chunks += parse_document(f"d{i}", p.name, p.read_bytes())
    return chunks


def chunks_of(text):
    return parse_text("t", "t.md", text)


def test_evidence_parser_keeps_headings_and_ids():
    chunks = parse_text("d1", "p.md", "# Policy\n\nIntro.\n\n## Backups\n\nBackups run nightly.\n")
    assert [(c.chunk_id, c.heading) for c in chunks] == [("d1-c001", "Policy"), ("d1-c002", "Backups")]


def test_sample_clinic_statuses():
    out = workflow.run_assessment(sample_chunks(), assessor="rules")
    status = {f["control_id"]: f["status"] for f in out["findings"]}
    assert status == {"164.312(a)(1)": "met", UI: "met", EA: "partially_met", LO: "met", EN: "not_met",
                      "164.308(a)(2)": "met", "164.308(a)(6)(i)": "met",
                      "164.308(a)(6)(ii)": "partially_met", "164.308(a)(8)": "partially_met"}
    assert out["review_queue"] == [EA, EN, "164.308(a)(6)(ii)", "164.308(a)(8)"]
    assert [t["node"] for t in out["trace"]] == ["plan", "retrieve", "assess", "verify", "route", "flag_for_review", "report"]


def test_all_met_skips_review_node():
    text = ("Access is role-based with least privilege. Managers approve access requests. Quarterly access reviews. "
            "Every user has a unique user ID. Shared accounts are prohibited. Audit logs record the user. "
            "A break-glass account exists; only the on-call admin is authorized to enable it; each use is logged and reviewed. "
            "Workstations lock automatically after 15 minutes of inactivity. "
            "Laptops use BitLocker full-disk encryption. Key management: keys are stored in the key vault. "
            "The IT Manager is designated as the HIPAA Security Officer. The Security Officer is responsible for "
            "developing and implementing security policies. Staff can contact the Security Officer at extension 9. "
            "This is our incident response policy. A security incident means any attempted or successful "
            "unauthorized access. The Security Officer leads the incident response. Staff must report suspected "
            "incidents within 1 hour. IT will contain the incident. All incidents are logged with their outcome. "
            "We perform an annual security evaluation. Significant operational changes trigger an evaluation. "
            "Evaluation findings are documented with a remediation plan.")
    out = workflow.run_assessment(chunks_of(text), assessor="rules")
    assert out["review_queue"] == []
    assert "flag_for_review" not in [t["node"] for t in out["trace"]]


def test_contradiction_beats_matches():
    f = rules.assess_control(UI, chunks_of("Every user has a unique user ID. Shared logins are permitted at reception."), [])
    assert f.status == "not_met" and f.contradictions


def test_addressable_documented_alternative():
    text = ("Our risk assessment found automatic logoff is not reasonable and appropriate for the OR terminals; "
            "as an alternative, the room is badge-controlled.")
    f = rules.assess_control(LO, chunks_of(text), [])
    assert (f.status, f.basis) == ("met", "documented_alternative")
    assert f.needs_review


def test_quarterly_access_review_is_not_a_security_evaluation():
    """Regression: the periodic-evaluation pattern used to match an access review."""
    f = rules.assess_control("164.308(a)(8)", chunks_of("Managers complete a quarterly access review."), [])
    assert f.status == "insufficient_evidence"


def test_no_evidence_is_insufficient_not_failed():
    f = rules.assess_control(EA, chunks_of("The clinic opens at 8 am."), [])
    assert f.status == "insufficient_evidence" and f.remediation


def test_verification_catches_fabricated_quote():
    evidence = chunks_of("Every user has a unique user ID.")
    f = rules.assess_control(UI, evidence, [])
    f.criteria[0].citations[0].quote = "Passwords rotate every 30 days."
    f = verify_finding(f, evidence)
    assert not f.verification["passed"] and f.needs_review


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(self.payload))])


def llm_payload(quote):
    return {"status": "partially_met", "basis": "none", "rationale": "Unique IDs shown; shared accounts not addressed.",
            "criteria": [{"criterion_id": "uid-1", "satisfied": True, "citations": [{"chunk_id": "t-c001", "quote": quote}]},
                         {"criterion_id": "uid-2", "satisfied": False, "citations": []},
                         {"criterion_id": "uid-3", "satisfied": False, "citations": []}],
            "contradictions": [], "gaps": ["shared accounts"], "remediation": ["Prohibit shared accounts."],
            "confidence": "medium"}


def test_llm_assessor_parses_structured_output_and_is_verified():
    evidence = chunks_of("Every user has a unique user ID.")
    client = FakeClient(llm_payload("Every user has a unique user ID."))
    f = verify_finding(llm.assess_control(UI, evidence, [], client=client), evidence)
    assert f.status == "partially_met" and f.assessor == "llm" and f.verification["passed"]
    call = client.calls[0]
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert "t-c001" in call["messages"][0]["content"]


def test_llm_hallucinated_quote_is_routed_to_review():
    evidence = chunks_of("Every user has a unique user ID.")
    f = verify_finding(llm.assess_control(UI, evidence, [], client=FakeClient(llm_payload("All users use MFA."))), evidence)
    assert not f.verification["passed"] and "citation verification failed" in f.review_reasons


def test_llm_failure_falls_back_to_rules(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("API down")

    monkeypatch.setattr(llm, "assess_control", boom)
    out = workflow.run_assessment(sample_chunks(), assessor="llm")
    assert all(f["assessor"] == "rules" for f in out["findings"])
    assert all(f["needs_review"] for f in out["findings"])
