# Phase 2 evidence policy

Risk reasoning uses four non-interchangeable evidence tiers.

| Tier | Role | Examples | May support |
|---|---|---|---|
| A | Primary / official | statutes, regulations, official regulator guidance, courts, treaties and clearly identified official materials | jurisdiction-specific legal conclusions when binding status is established |
| B | Professional practice | bar materials, law-firm checklists, licensed treatises, commercial drafting guidance | drafting/review recommendations |
| C | Research / methodology | papers, benchmark cards, dataset documentation, evaluation methods | methodology and benchmark claims |
| D | Internal policy | approved organizational playbook | internal review policy only |

A source tier is not the same as legal force. authority_status is required to distinguish
binding law from official but non-binding guidance.

Every source record should expose:

source_tier, jurisdiction, effective_date, contract_type, source_url,
source_title, retrieval_date, and supporting_quote_or_paraphrase.

A source from another contract type must carry transferability=limited_by_analogy rather than
being silently generalized.

Contract text is its own evidence class. A source can explain why a question matters;
it cannot prove that the uploaded contract contains a fact. Positive findings therefore
require exact contract evidence.

The current uploaded team playbook is an internal review-policy artifact at the system level,
even though its individual references are professional sources. It is not a gold label set.
