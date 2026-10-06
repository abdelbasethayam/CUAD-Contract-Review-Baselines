# Phase 2 deterministic risk score

Version: commercial-risk-score-v1

Each evidence-supported finding receives four 0–5 dimensions:

- exposure magnitude
- likelihood / uncertainty
- scope / duration
- control weakness

base_score = exposure + likelihood + scope + control_weakness (0–20).

Modifiers are deterministic and recorded in the finding:
+2 cross-clause conflict, +2 jurisdiction/competition-sensitive issue,
+1 low extraction confidence below 0.75, +1 missing defined/incorporated dependency,
and -2 where a clear cap/control/remedy bounds the same exposure.

Default severity bands are:
0–3 Informational, 4–7 Low, 8–11 Medium, 12–15 High, 16–20 Critical.

Overrides never allow the numeric score to suppress a critical/high-review condition.
The score is an internal triage instrument, not a legal standard and not a probability.

At contract level, aggregation uses highest finding severity/score plus explicit
interaction adjustments for critical findings, multiple high findings, same-domain high
clusters, and economic/exit stacks. No finding count is converted into a probability.

Human review is mandatory for Critical/High findings, jurisdiction-sensitive findings,
and detected conflicts. The review status must remain distinct from model confidence.
