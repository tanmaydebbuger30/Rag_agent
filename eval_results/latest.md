# Evaluation results (2026-11-14T23:59:25+00:00, commit a12cd65)

> Labels are drafts (label_status=draft_unreviewed) written by the same author as the alias map and assessment patterns. Treat these numbers as a regression baseline, not as an independent quality claim.

## Retrieval: control ranking (50 queries, dataset regulatory_retrieval_v1)

| Config | Hit@1 | Hit@3 | Recall@3 | MRR |
|---|---|---|---|---|
| bm25_only | 0.64 | 0.76 | 0.75 | 0.726 |
| bm25+aliases | 0.7 | 0.78 | 0.77 | 0.767 |
| bm25+identifiers | 0.66 | 0.78 | 0.77 | 0.742 |
| full (bm25+aliases+identifiers) | 0.72 | 0.8 | 0.79 | 0.783 |

### Full config by query type

| Query type | n | Hit@1 | Hit@3 | MRR |
|---|---|---|---|---|
| citation | 8 | 1.0 | 1.0 | 1.0 |
| hard_negative | 10 | 0.6 | 0.8 | 0.731 |
| jargon | 11 | 0.818 | 0.909 | 0.864 |
| out_of_scope | 2 | 1.0 | 1.0 | 1.0 |
| paraphrase | 12 | 0.333 | 0.417 | 0.443 |
| split:dev | 38 | 0.711 | 0.789 | 0.769 |
| split:test | 12 | 0.75 | 0.833 | 0.824 |
| verbatim | 7 | 1.0 | 1.0 | 1.0 |

### Full config Hit@1 misses

- "every employee needs their own login": expected 164.312(a)(2)(i), got 164.308(a)(5)(ii)(B), 164.308(a)(5)(ii)(D), 164.312(b)
- "can two nurses share one EHR username?": expected 164.312(a)(2)(i), got 164.308(a)(4)(i), 164.312(d), 164.308(a)(7)(i)
- "how do clinicians get into the record system if the network is down": expected 164.312(a)(2)(ii), got 164.312(b), 164.312(a)(1), 164.308(a)(1)(ii)(D)
- "log users out when they walk away from the computer": expected 164.312(a)(2)(iii), got 164.312(a)(2)(i), 164.312(a)(1), 164.312(a)(2)(iii)
- "protect stored patient data so a stolen laptop cannot be read": expected 164.312(a)(2)(iv), got 164.312(c)(1), 164.308(a)(1)(i), 164.312(e)(2)(ii)
- "generic shared accounts": expected 164.312(a)(2)(i), got 164.308(a)(3)(ii)(C), 164.308(a)(5)(ii)(B), 164.308(a)(5)(ii)(D)
- "AES-256 encryption at rest": expected 164.312(a)(2)(iv), got 164.312(a)(2)(iii), 164.312(a)(2)(iv), 164.312(e)(2)(ii)
- "encrypt ePHI sent over email or the internet": expected 164.312(e)(2)(ii), got 164.312(e)(1), 164.312(e)(2)(ii), 164.312(a)(2)(iii)
- "TLS for data in transit": expected 164.312(e)(2)(ii), 164.312(e)(1), got 164.308(a)(7)(ii)(A), 164.308(a)(7)(ii)(B), 164.308(a)(7)(ii)(E)
- "do we need multi-factor authentication?": expected 164.312(d), got 164.312(a)(1), 164.312(d), 164.308(a)(8)
- "who is in charge of HIPAA security at our company?": expected 164.308(a)(2), got 164.308(a)(6)(i), 164.308(a)(5)(ii)(A), 164.308(a)(1)(i)
- "what should an employee do after clicking a phishing link?": expected 164.308(a)(6)(ii), 164.308(a)(6)(i), got 164.312(b), 164.312(a)(2)(iii), 164.308(a)(5)(ii)(A)
- "how often do we need to review our security program?": expected 164.308(a)(8), got 164.308(a)(1)(ii)(D), 164.312(b), 164.308(a)(4)(ii)(C)
- "conduct a risk analysis of threats to ePHI": expected 164.308(a)(1)(ii)(A), got 164.312(c)(1), 164.308(a)(5)(i), 164.308(a)(6)(i)

## Rule-based assessor (27 cases, dataset assessment_cases_v1)

Status accuracy: **0.852**

| expected -> got | count |
|---|---|
| insufficient_evidence -> insufficient_evidence | 4 |
| met -> met | 10 |
| met -> partially_met | 1 |
| not_met -> insufficient_evidence | 2 |
| not_met -> not_met | 4 |
| partially_met -> insufficient_evidence | 1 |
| partially_met -> partially_met | 5 |

Errors:

- as-005 (164.312(a)(2)(i)): expected met, got partially_met
- as-017 (164.312(a)(1)): expected partially_met, got insufficient_evidence
- as-018 (164.312(a)(1)): expected not_met, got insufficient_evidence
- as-020 (164.308(a)(2)): expected not_met, got insufficient_evidence
