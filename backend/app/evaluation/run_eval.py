"""Evaluation runner: retrieval ablations + rule-based assessor accuracy.

Run: python -m backend.app.evaluation.run_eval
Writes eval_results/<timestamp>.json and eval_results/latest.md.

Caveat printed into every report: the query labels and assessment cases are
drafts written by the same author as the alias map and criteria patterns, so
the numbers are optimistic until an independent reviewer relabels them.
"""
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

from backend.app.assessment import rules
from backend.app.config import EVAL_DIR, EVAL_RESULTS_DIR
from backend.app.evaluation.metrics import hit_at_k, recall_at_k, reciprocal_rank
from backend.app.ingestion.build_kb import load_kb
from backend.app.ingestion.evidence import parse_text
from backend.app.retrieval.hybrid import RegulatoryRetriever

CAVEAT = ("Labels are drafts (label_status=draft_unreviewed) written by the same author as the alias map and "
          "assessment patterns. Treat these numbers as a regression baseline, not as an independent quality claim.")

CONFIGS = {
    "bm25_only": dict(use_aliases=False, use_identifiers=False),
    "bm25+aliases": dict(use_aliases=True, use_identifiers=False),
    "bm25+identifiers": dict(use_aliases=False, use_identifiers=True),
    "full (bm25+aliases+identifiers)": dict(use_aliases=True, use_identifiers=True),
}


def load_jsonl(path):
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def eval_retrieval(queries, chunks):
    out = {}
    for name, kwargs in CONFIGS.items():
        r = RegulatoryRetriever(chunks, **kwargs)
        per_type = defaultdict(lambda: defaultdict(list))
        misses = []
        for q in queries:
            ranked = [c["control_id"] for c in r.search(q["query"], k=10)["controls"]]
            rel = set(q["expected_control_ids"])
            m = {"hit@1": hit_at_k(ranked, rel, 1), "hit@3": hit_at_k(ranked, rel, 3),
                 "recall@3": recall_at_k(ranked, rel, 3), "mrr": reciprocal_rank(ranked, rel)}
            for key in (q["query_type"], "ALL", f"split:{q['split']}"):
                for metric, v in m.items():
                    per_type[key][metric].append(v)
            if not m["hit@1"]:
                misses.append({"query": q["query"], "expected": q["expected_control_ids"], "got_top3": ranked[:3]})
        out[name] = {"metrics": {k: {mk: round(sum(v) / len(v), 3) for mk, v in ms.items()} | {"n": len(ms["mrr"])}
                                 for k, ms in per_type.items()},
                     "hit@1_misses": misses}
    return out


def eval_assessor(cases):
    rows, correct = [], 0
    confusion = defaultdict(int)
    for c in cases:
        chunks = parse_text("case", f"{c['case_id']}.txt", c["evidence"])
        got = rules.assess_control(c["control_id"], chunks, []).status
        ok = got == c["expected_status"]
        correct += ok
        confusion[f"{c['expected_status']} -> {got}"] += 1
        rows.append({"case_id": c["case_id"], "control_id": c["control_id"], "expected": c["expected_status"], "got": got, "ok": ok})
    return {"accuracy": round(correct / len(cases), 3), "n": len(cases), "confusion": dict(confusion),
            "errors": [r for r in rows if not r["ok"]]}


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def to_markdown(result):
    lines = [f"# Evaluation results ({result['created_at']}, commit {result['commit']})", "", f"> {CAVEAT}", "",
             f"## Retrieval: control ranking ({result['retrieval_n']} queries, dataset {result['datasets']['retrieval']})", "",
             "| Config | Hit@1 | Hit@3 | Recall@3 | MRR |", "|---|---|---|---|---|"]
    for name, r in result["retrieval"].items():
        m = r["metrics"]["ALL"]
        lines.append(f"| {name} | {m['hit@1']} | {m['hit@3']} | {m['recall@3']} | {m['mrr']} |")
    full = result["retrieval"]["full (bm25+aliases+identifiers)"]["metrics"]
    lines += ["", "### Full config by query type", "", "| Query type | n | Hit@1 | Hit@3 | MRR |", "|---|---|---|---|---|"]
    for k, m in sorted(full.items()):
        if k != "ALL":
            lines.append(f"| {k} | {m['n']} | {m['hit@1']} | {m['hit@3']} | {m['mrr']} |")
    lines += ["", "### Full config Hit@1 misses", ""]
    for miss in result["retrieval"]["full (bm25+aliases+identifiers)"]["hit@1_misses"]:
        lines.append(f"- \"{miss['query']}\": expected {', '.join(miss['expected'])}, got {', '.join(miss['got_top3'])}")
    a = result["assessor"]
    lines += ["", f"## Rule-based assessor ({a['n']} cases, dataset {result['datasets']['assessment']})", "",
              f"Status accuracy: **{a['accuracy']}**", "", "| expected -> got | count |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(a["confusion"].items())]
    if a["errors"]:
        lines += ["", "Errors:", ""] + [f"- {e['case_id']} ({e['control_id']}): expected {e['expected']}, got {e['got']}" for e in a["errors"]]
    return "\n".join(lines) + "\n"


def main():
    queries = load_jsonl(EVAL_DIR / "regulatory_retrieval_v1.jsonl")
    cases = load_jsonl(EVAL_DIR / "assessment_cases_v1.jsonl")
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": git_commit(),
        "caveat": CAVEAT,
        "datasets": {"retrieval": "regulatory_retrieval_v1", "assessment": "assessment_cases_v1"},
        "retrieval_n": len(queries),
        "retrieval": eval_retrieval(queries, load_kb()),
        "assessor": eval_assessor(cases),
    }
    EVAL_RESULTS_DIR.mkdir(exist_ok=True)
    stamp = result["created_at"].replace(":", "").replace("-", "")[:15]
    (EVAL_RESULTS_DIR / f"{stamp}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    md = to_markdown(result)
    (EVAL_RESULTS_DIR / "latest.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
