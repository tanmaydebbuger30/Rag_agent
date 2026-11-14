# Evaluation results (2026-11-14T21:01:53+00:00, commit a21ee50)

> Labels are drafts (label_status=draft_unreviewed) written by the same author as the alias map and assessment patterns. Treat these numbers as a regression baseline, not as an independent quality claim.

## Retrieval: control ranking (38 queries, dataset regulatory_retrieval_v1)

| Config | Hit@1 | Hit@3 | Recall@3 | MRR |
|---|---|---|---|---|
| bm25_only | 0.684 | 0.816 | 0.816 | 0.777 |
| bm25+aliases | 0.711 | 0.816 | 0.816 | 0.795 |
| bm25+identifiers | 0.711 | 0.842 | 0.842 | 0.798 |
| full (bm25+aliases+identifiers) | 0.737 | 0.842 | 0.842 | 0.816 |

### Full config by query type

| Query type | n | Hit@1 | Hit@3 | MRR |
|---|---|---|---|---|
| citation | 6 | 1.0 | 1.0 | 1.0 |
| hard_negative | 8 | 0.625 | 0.875 | 0.766 |
| jargon | 8 | 0.75 | 0.875 | 0.812 |
| out_of_scope | 2 | 1.0 | 1.0 | 1.0 |
| paraphrase | 9 | 0.444 | 0.556 | 0.597 |
| split:dev | 29 | 0.724 | 0.793 | 0.793 |
| split:test | 9 | 0.778 | 1.0 | 0.889 |
| verbatim | 5 | 1.0 | 1.0 | 1.0 |

### Full config Hit@1 misses

- "every employee needs their own login": expected 164.312(a)(2)(i), got 164.312(b), 164.312(a)(2)(i), 164.312(a)(2)(ii)
- "can two nurses share one EHR username?": expected 164.312(a)(2)(i), got 164.312(d), 164.312(e)(1), 164.312(c)(1)
- "how do clinicians get into the record system if the network is down": expected 164.312(a)(2)(ii), got 164.312(b), 164.312(a)(1), 164.312(e)(1)
- "log users out when they walk away from the computer": expected 164.312(a)(2)(iii), got 164.312(a)(2)(i), 164.312(a)(1), 164.312(b)
- "protect stored patient data so a stolen laptop cannot be read": expected 164.312(a)(2)(iv), got 164.312(c)(1), 164.312(e)(2)(ii), 164.312(a)(2)(iii)
- "generic shared accounts": expected 164.312(a)(2)(i), got 
- "AES-256 encryption at rest": expected 164.312(a)(2)(iv), got 164.312(a)(2)(iii), 164.312(a)(2)(iv), 164.312(e)(2)(ii)
- "encrypt ePHI sent over email or the internet": expected 164.312(e)(2)(ii), got 164.312(e)(1), 164.312(e)(2)(ii), 164.312(a)(2)(iii)
- "TLS for data in transit": expected 164.312(e)(2)(ii), 164.312(e)(1), got 164.312(c)(1), 164.312(e)(2)(i), 164.312(c)(2)
- "do we need multi-factor authentication?": expected 164.312(d), got 164.312(a)(1), 164.312(d), 164.312(b)

## Rule-based assessor (18 cases, dataset assessment_cases_v1)

Status accuracy: **0.833**

| expected -> got | count |
|---|---|
| insufficient_evidence -> insufficient_evidence | 2 |
| met -> met | 6 |
| met -> partially_met | 1 |
| not_met -> insufficient_evidence | 1 |
| not_met -> not_met | 3 |
| partially_met -> insufficient_evidence | 1 |
| partially_met -> partially_met | 4 |

Errors:

- as-005 (164.312(a)(2)(i)): expected met, got partially_met
- as-017 (164.312(a)(1)): expected partially_met, got insufficient_evidence
- as-018 (164.312(a)(1)): expected not_met, got insufficient_evidence
