from fastapi.testclient import TestClient

from backend.app.api.main import app

client = TestClient(app)


def test_sample_assessment_review_and_report():
    r = client.post("/api/assessments", data={"org_name": "Test clinic", "use_sample": "true"})
    assert r.status_code == 200
    a = r.json()
    assert a["review_status"] == "pending_review"
    for cid in a["review_queue"]:
        r = client.post(f"/api/assessments/{a['id']}/findings/{cid}/review",
                        json={"decision": "accept", "reviewer": "Reviewer", "note": "ok"})
        assert r.status_code == 200
    assert r.json()["review_status"] == "complete"
    report = client.get(f"/api/assessments/{a['id']}/report.md").text
    assert "not a legal determination" in report and "accepted by Reviewer" in report
    assert client.get("/api/assessments").json()[0]["id"] == a["id"]


def test_override_requires_status_and_reviewer():
    a = client.post("/api/assessments", data={"org_name": "x", "use_sample": "true"}).json()
    url = f"/api/assessments/{a['id']}/findings/164.312(a)(2)(ii)/review"
    assert client.post(url, json={"decision": "override", "reviewer": "R"}).status_code == 400
    assert client.post(url, json={"decision": "accept", "reviewer": " "}).status_code == 400
    r = client.post(url, json={"decision": "override", "status": "not_met", "reviewer": "R"})
    assert next(f for f in r.json()["findings"] if f["control_id"] == "164.312(a)(2)(ii)")["review"]["status"] == "not_met"


def test_upload_validation():
    assert client.post("/api/assessments", data={"org_name": "x"}).status_code == 400
    bad = client.post("/api/assessments", data={"org_name": "x"}, files=[("files", ("a.exe", b"MZ", "application/octet-stream"))])
    assert bad.status_code == 400
    ok = client.post("/api/assessments", data={"org_name": "x"},
                     files=[("files", ("p.txt", b"Workstations lock automatically after 15 minutes of inactivity.", "text/plain"))])
    lo = next(f for f in ok.json()["findings"] if f["control_id"] == "164.312(a)(2)(iii)")
    assert lo["status"] == "met"


def test_llm_assessor_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = client.post("/api/assessments", data={"org_name": "x", "use_sample": "true", "assessor": "llm"})
    assert r.status_code == 400


def test_search_and_controls():
    assert client.get("/api/search", params={"q": "break-glass"}).json()["controls"][0]["control_id"] == "164.312(a)(2)(ii)"
    assert len(client.get("/api/controls").json()) == 5
    assert client.get("/api/kb/chunks/ecfr-164.312(a)(1)").json()["authority_level"] == "regulation"
