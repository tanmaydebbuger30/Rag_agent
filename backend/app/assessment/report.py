"""Render an assessment as a Markdown gap-analysis report."""

STATUS_LABEL = {"met": "Met", "partially_met": "Partially met", "not_met": "Not met",
                "insufficient_evidence": "Insufficient evidence"}


def _status(f: dict) -> str:
    review = f.get("review")
    if review and review["decision"] == "override":
        return f"{STATUS_LABEL[review['status']]} (reviewer override; assessor said {STATUS_LABEL[f['status']]})"
    label = STATUS_LABEL[f["status"]]
    if review:
        return f"{label} (accepted by {review['reviewer']})"
    return label + (" (pending human review)" if f["needs_review"] else "")


def render_markdown(a: dict) -> str:
    lines = [
        f"# HIPAA Security Rule Readiness Report: {a['org_name']}",
        "",
        f"- Assessment ID: `{a['id']}`",
        f"- Created: {a['created_at']}",
        "- Scope: Access Control (45 CFR § 164.312(a), standard and four implementation specifications) plus three administrative standards: Assigned Security Responsibility (§ 164.308(a)(2)), Security Incident Procedures (§ 164.308(a)(6)) and Evaluation (§ 164.308(a)(8))",
        f"- Assessor: {a['assessor']}",
        f"- Evidence: {', '.join(d['filename'] for d in a['documents'])}",
        f"- Review status: {a['review_status']}",
        "",
        "> This is an evidence-based readiness gap analysis. It is not a legal determination of HIPAA compliance.",
        "",
        "## Summary",
        "",
        "| Control | Requirement | Safeguard | Type | Status |",
        "|---|---|---|---|---|",
    ]
    for f in a["findings"]:
        lines.append(f"| {f['control_id']} | {f['control_name']} | {f.get('safeguard_category') or '-'} "
                     f"| {f['requirement_type']} | {_status(f)} |")

    for f in a["findings"]:
        lines += ["", f"## {f['citation']} {f['control_name']}", "",
                  f"**Requirement ({f['requirement_type']}):** \"{f['requirement_text']}\"", "",
                  f"**Status:** {_status(f)}", "", f"**Rationale:** {f['rationale']}", "", "**Criteria:**", ""]
        for c in f["criteria"]:
            mark = "x" if c["satisfied"] else " "
            lines.append(f"- [{mark}] {c['text']}")
            for cite in c["citations"]:
                where = cite["filename"] + (f", p. {cite['page']}" if cite.get("page") else "") \
                    + (f", \"{cite['heading']}\"" if cite.get("heading") else "")
                lines.append(f"  - \"{cite['quote']}\" ({where})")
        if f["contradictions"]:
            lines += ["", "**Conflicting evidence:**", ""]
            lines += [f"- \"{c['quote']}\" ({c['filename']})" for c in f["contradictions"]]
        if f["remediation"]:
            lines += ["", "**Suggested remediation:**", ""] + [f"- {r}" for r in f["remediation"]]
        if f.get("review"):
            r = f["review"]
            lines += ["", f"**Reviewer note ({r['reviewer']}, {r['reviewed_at']}):** {r.get('note') or '-'}"]
        if f["guidance"]:
            lines += ["", "**Guidance consulted:** " + "; ".join(g["citation"] for g in f["guidance"])]
    return "\n".join(lines) + "\n"
