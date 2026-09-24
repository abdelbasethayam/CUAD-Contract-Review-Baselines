# Legal Knowledge Risk Indicators

This file documents the MVP indicators before they are used by the system.
The legal sources identify contractual concepts and risk-allocation issues.
Our system flags only a potential review indicator after analyzing the uploaded
clause text with local LLM reasoning and retrieved guidance.

## Limitation of Liability

Clause Type: Limitation of Liability

Risk Indicator: Liability cap or exclusion is unclear, unusually broad, uses
uncapped/unlimited/without-limitation wording, or is not coordinated with
indemnity, warranty, confidentiality, IP, data, fraud, willful misconduct,
defense-cost, or statutory-liability carve-outs.

Why It May Require Review: Liability provisions allocate commercial exposure.
Ambiguity about what is capped or excluded can make the risk allocation hard to
understand and may conflict with other contract obligations.

Source Name: World Commerce & Contracting

Source URL: https://www.worldcc.foundation/how-we-help/resources-tools/contracting-principles.html

Source Title: Contracting Principles - Liability Caps and Exclusions From Liability

Notes / Limitations: The source identifies liability caps and exclusions as a
contracting principle topic. Our system does not infer that caps or exclusions
are improper; it flags only potential review issues found in the clause.

Source Name: American Bar Association

Source URL: https://www.americanbar.org/groups/intellectual_property_law/resources/landslide/archive/when-limitation-liability-not-so-limiting/

Source Title: When the Limitation of Liability Is Not So Limiting

Notes / Limitations: The source discusses coordination between limitation of
liability and indemnity. Our system uses this as review guidance, not as a
jurisdiction-specific rule.

## Indemnification

Clause Type: Indemnification

Risk Indicator: Indemnity language is one-sided, untethered to caused losses or
defined claims, unclear about direct claims, or ambiguous about defend,
settlement control, notice, mitigation, insurance, and liability-cap treatment.

Why It May Require Review: Indemnity can allocate losses and defense duties.
Unclear scope or procedure can materially change who funds defense and losses.

Source Name: World Commerce & Contracting

Source URL: https://www.worldcc.foundation/how-we-help/resources-tools/contracting-principles.html

Source Title: Contracting Principles - Indemnification of Third Party Claims

Notes / Limitations: The source treats indemnification as a commercial
risk-allocation principle. Our system flags potential review indicators only
from the uploaded clause text.

Source Name: International Bar Association

Source URL: https://www.ibanet.org/Handbook-for-lawyers/Chapter-2

Source Title: Handbook for Lawyers - Indemnities in Long-Term Supply Agreements

Notes / Limitations: The source discusses indemnities in the context of
long-term supply and human-rights-related contracting. It is supporting
guidance, not a general rule for every contract.

Source Name: American Bar Association

Source URL: https://www.americanbar.org/groups/litigation/resources/newsletters/corporate-counsel/negotiating-indemnity/

Source Title: Negotiating Indemnity

Notes / Limitations: The source discusses defense obligations and liability
exposure in indemnity negotiation. Our system does not treat every indemnity as
risky.

## Termination

Clause Type: Termination

Risk Indicator: Termination mechanics are unclear or operationally incomplete,
including termination at any time or without cause without a stated process,
missing cure periods for curable breaches, unclear notice deadlines, unclear
renewal termination windows, or missing transition, data return, survival, and
accrued-payment treatment.

Why It May Require Review: Termination clauses define exit rights and post-exit
responsibilities. Operational gaps can create disputes or business continuity
problems.

Source Name: World Commerce & Contracting

Source URL: https://www.worldcc.foundation/how-we-help/resources-tools/contracting-principles.html

Source Title: Contracting Principles - Term and Termination

Notes / Limitations: The source identifies term, termination, suspension rights,
and termination assistance as contracting principle topics. Our system uses
this only as review guidance.

Source Name: American Bar Association

Source URL: https://www.americanbar.org/groups/business_law/resources/business-law-today/2021-november/saas-agreements-key-contractual-provisions/

Source Title: SaaS Agreements: Key Contractual Provisions

Notes / Limitations: The source discusses SaaS contracts, so transition, data,
and suspension concerns are strongest where the uploaded agreement involves
services, hosted data, or ongoing operational dependency.

## Intellectual Property

Clause Type: Intellectual Property

Risk Indicator: Unclear IP Ownership

Why It May Require Review: IP clauses allocate ownership of background IP,
foreground IP, developed materials, improvements, derivatives, transferred
technology, and commercialization rights. If the clause does not clearly
identify which IP is owned by which party, human review may be needed to
understand the transaction's allocation of rights.

Source Name: World Intellectual Property Organization

Source URL: https://www.wipo.int/en/web/technology-transfer/agreements

Source Title: Technology Transfer Agreements

Notes / Limitations: WIPO identifies IP ownership and access rights as part of
the legal framework for collaborative research and technology transfer. The
system does not treat every customer-owned or supplier-owned IP term as risky;
it flags this indicator only when the clause itself leaves ownership scope
unclear.

Clause Type: Intellectual Property

Risk Indicator: Broad IP License Scope

Why It May Require Review: License terms define what the licensee may do with
the IP. Broad combinations of purpose, territory, field of use, duration,
exclusivity, transferability, sublicensing, modification, reproduction,
distribution, or software-use rights can materially affect the parties'
commercial allocation.

Source Name: World Intellectual Property Organization

Source URL: https://www.wipo.int/en/web/technology-transfer/agreements

Source Title: Technology Transfer Agreements

Notes / Limitations: WIPO distinguishes broad and narrow license rights by
purpose, territory, field of use, and other terms. A broad license is not
automatically improper; the system flags a potential indicator only when the
uploaded clause grants a broad bundle of rights.

Clause Type: Intellectual Property

Risk Indicator: Unclear Assignment Scope

Why It May Require Review: IP assignment transfers ownership with permanent
effect. If the assignment does not accurately identify the subject matter being
assigned, the scope of transferred ownership may be difficult to evaluate.

Source Name: World Intellectual Property Organization

Source URL: https://www.wipo.int/en/web/technology-transfer/agreements

Source Title: Technology Transfer Agreements

Notes / Limitations: WIPO states that assignment contracts should accurately
identify the assigned subject matter. The system treats cross-referenced
subject matter, such as IP described in a schedule, as clearer than a bare
assignment of undefined IP.

Clause Type: Intellectual Property

Risk Indicator: Unclear License Rights

Why It May Require Review: License rights may need to define territory, field
of use, exclusivity, duration, sublicensing, transferability, permitted users,
and software-use permissions. Missing or ambiguous boundaries can make it hard
to understand what use is permitted.

Source Name: World Commerce & Contracting

Source URL: https://www.worldcc.foundation/how-we-help/resources-tools/contracting-principles.html

Source Title: Contracting Principles - Intellectual Property Rights and Indemnification for Third Party IP Claims

Notes / Limitations: WorldCC identifies IP rights and third-party IP claim
indemnification as commercial contracting-principle topics. The system uses
this only as review guidance and does not infer a legal conclusion.

## Confidentiality

Clause Type: Confidentiality

Risk Indicator: Unclear Confidential Information Definition; Unclear Access Restrictions; Unclear Confidentiality Duration

Why It May Require Review: A confidentiality clause may be difficult to apply when it does not identify protected information, permitted use, authorized access, protective measures, or duration.

Source Name: World Intellectual Property Organization

Source URL: https://www.wipo.int/en/web/technology-transfer/agreements

Source Title: Technology Transfer Agreements - Confidentiality Agreements

Notes / Limitations: WIPO's public guidance is used as review context. The system does not treat a broad definition or a confidentiality duty as illegal or automatically risky.

## Payment

Clause Type: Payment

Risk Indicator: Unclear Payment Terms; Unclear Late Payment Consequences

Why It May Require Review: Amounts, invoices, due dates, disputed amounts, late charges, or suspension consequences may be difficult to administer when the clause is vague.

Source Name: World Commerce & Contracting

Source URL: https://www.worldcc.foundation/how-we-help/resources-tools/contracting-principles.html

Source Title: Contracting Principles - Payment Terms, Prices and Charges

Notes / Limitations: Commercial payment preferences vary. This is a potential review indicator, not a legal conclusion.

## Force Majeure

Clause Type: Force Majeure

Risk Indicator: Broad Force Majeure Definition; Unclear Notice Requirement; Unclear Mitigation Obligation

Why It May Require Review: Event scope, notice, mitigation, temporary impediment, and consequences can affect whether performance relief is operationally clear.

Source Name: International Chamber of Commerce

Source URL: https://iccwbo.org/news-publications/icc-rules-guidelines/icc-force-majeure-and-hardship-clauses/

Source Title: ICC Force Majeure and Hardship Clauses

Notes / Limitations: ICC model clauses are not a universal jurisdiction-specific rule. The system flags only language that may require human review.

## Insurance

Clause Type: Insurance

Risk Indicator: Unclear Insurance Coverage

Why It May Require Review: Coverage types, limits, certificates, additional-insured requirements, or maintenance periods may not be clear enough to verify operationally.

Source Name: World Commerce & Contracting

Source URL: https://www.worldcc.foundation/how-we-help/resources-tools/contracting-principles.html

Source Title: Contracting Principles - Insurance Coverages

Notes / Limitations: The system does not determine whether coverage is legally sufficient or commercially adequate.

## Warranties

Clause Type: Warranties

Risk Indicator: Unclear Warranty Scope

Why It May Require Review: The promised standard, duration, exclusions, disclaimers, or remedy may require review when unclear.

Source Name: World Commerce & Contracting

Source URL: https://www.worldcc.foundation/how-we-help/resources-tools/contracting-principles.html

Source Title: Contracting Principles - Warranties and Remedies

Notes / Limitations: No warranty term is treated as inherently risky.

## Assignment and Novation

Clause Type: Assignment

Risk Indicator: Unclear Assignment Scope

Why It May Require Review: Consent, affiliate transfers, novation, change of control, and continuing responsibility may materially affect the parties' allocation of obligations.

Source Name: World Commerce & Contracting

Source URL: https://www.worldcc.foundation/how-we-help/resources-tools/contracting-principles.html

Source Title: Contracting Principles - Assignment, Novation and Change of Control

Notes / Limitations: A transfer is not treated as invalid or inherently risky.

## Arbitration and ADR

Clause Type: Dispute Resolution

Risk Indicator: Unclear ADR Mechanics

Why It May Require Review: The clause may require review when the process, rules, seat, appointment, confidentiality, costs, or enforcement mechanics are unclear.

Source Name: United Nations Commission on International Trade Law

Source URL: https://uncitral.un.org/en/texts/arbitration/modellaw/commercial_arbitration

Source Title: UNCITRAL Model Law on International Commercial Arbitration

Notes / Limitations: Model-law material is not a universal legal rule and the system does not assess enforceability.
