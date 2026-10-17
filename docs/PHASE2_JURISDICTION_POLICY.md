# Phase 2 jurisdiction and authority policy

## Decision

The first research scope is **U.S. commercial contracts**, because the current 37-clause taxonomy is aligned with CUAD's commercial-contract review task. This is a dataset/task choice, not a claim that every CUAD contract is governed by U.S. law or that every clause is governed by federal law.

## How the system selects law

1. Extract the governing-law and forum clauses as contract evidence.
2. Record the actual contract type and transaction subject matter (goods, services/SaaS, IP licence, employment-related, M&A/corporate, or mixed).
3. Apply federal authority only where its subject matter and jurisdictional scope fit.
4. Apply New York or Delaware UCC Article 2 authorities only when the contract is actually governed by that state's law and the transaction is within Article 2's sale-of-goods scope.
5. If the law, transaction type, party relationship, or statutory exception is unknown, report `JURISDICTION_REVIEW_REQUIRED` and abstain from legal conclusions.
6. Never infer governing law solely from party location, incorporation, a dataset label, or the presence of a source in the authority catalog.

## Authority sources

`data/risk/authority_catalog.json` contains 33 traceable federal, state, and regulator/court-source records. It identifies exact statutory/case pinpoints, retrieval dates, source tier, currentness caveats, and applicability limits. Government statutes link to official U.S. Code, New York Senate, Delaware Code, FTC, and California code pages. The California § 16600 page returned HTTP 403 during this audit, so its content and effective dates remain unverified. One Delaware Supreme Court opinion is linked through a legal-opinion republication host and is explicitly marked for official-docket and subsequent-history verification before approval.

`data/risk/clause_authority_map.json` maps all 37 taxonomy categories to applicable authority leads or explicitly states that no universal primary statute has been identified. This distinction is deliberate: audit rights, insurance requirements, transition services, non-disparagement, rights of first refusal/offer/negotiation, and indemnification are not governed by one universal rule that can be applied without context.

## Non-compete caution

The FTC's 2024 Non-Compete Clause Rule must not be described as a currently enforceable nationwide ban. The FTC stated in September 2025 that it would withdraw its appeals and accede to vacatur; its status page says the rule is not in effect. State-specific law remains necessary. See the FTC status notice in the authority catalog and re-check it on every release.

## What is still not approved

The authority map is a research and triage layer, not a validated legal ruleset. All 37 categories remain review triggers; `legal_conclusion_allowed=false`. A rule can only be approved after rule-level verification of the proposition, jurisdiction, relevant date, pinpoint, exceptions, positive/negative/edge cases, independent annotation, and adjudication. The initial authority catalog is not a 50-state survey and does not cover all state laws, regulations, or case law.
