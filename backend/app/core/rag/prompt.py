"""Prompt construction for the Qwen/Ollama clause classifier (improved)."""
from __future__ import annotations

import json
from pathlib import Path

from ..config import LABEL_DEFINITIONS_PATH


DEFAULT_LABEL_DEFINITIONS: dict[str, str] = {
    "Affiliate License-Licensee": "License rights are granted to the licensee's affiliates, subsidiaries, parent companies, or related entities.",
    "Affiliate License-Licensor": "License rights are granted to, reserved for, or shared with the licensor's affiliates, subsidiaries, parent companies, or related entities.",
    "Anti-Assignment": "A clause restricting assignment, delegation, transfer, or subcontracting of the agreement or its rights and duties.",
    "Audit Rights": "A clause giving one party the right to inspect, audit, or review books, records, systems, or compliance.",
    "Cap On Liability": "A clause setting an express maximum amount or formula that limits liability exposure.",
    "Change Of Control": "A clause triggered by a merger, acquisition, ownership change, or similar change in control.",
    "Competitive Restriction Exception": "A clause that carves out permitted competitive activity from an otherwise restrictive non-compete or exclusivity provision.",
    "Covenant Not To Sue": "A clause where a party promises not to sue, assert claims, or bring infringement actions.",
    "Exclusivity": "A clause making a relationship exclusive, sole, or restricted to one counterparty, channel, product, or territory.",
    "Governing Law": "A clause specifying the law, jurisdiction, or venue that governs interpretation or disputes.",
    "Insurance": "A clause requiring insurance coverage, policy types, limits, certificates, or proof of insurance.",
    "Ip Ownership Assignment": "A clause assigning or transferring intellectual property ownership or future IP rights to a party.",
    "Irrevocable Or Perpetual License": "A clause granting a license that is irrevocable, perpetual, permanent, or continuing indefinitely.",
    "Joint Ip Ownership": "A clause stating that intellectual property is jointly owned by two or more parties.",
    "License Grant": "A clause that grants a license, right, permission, or authorization to use specified IP, data, or materials.",
    "Liquidated Damages": "A clause setting a pre-agreed damages amount or formula for a specified breach or delay.",
    "Minimum Commitment": "A clause requiring a minimum purchase, spend, volume, output, or other contractual commitment.",
    "Most Favored Nation": "A clause requiring parity with the best price, terms, or treatment given to another counterparty.",
    "No-Solicit Of Customers": "A clause prohibiting solicitation of customers, clients, or accounts.",
    "No-Solicit Of Employees": "A clause prohibiting solicitation, hiring, or recruitment of employees, contractors, or personnel.",
    "Non-Compete": "A clause prohibiting competing business activity, products, services, or market participation.",
    "Non-Transferable License": "A clause stating that a license may not be assigned, transferred, or sublicensed.",
    "Notice Period To Terminate Renewal": "A clause requiring advance notice to stop automatic renewal or to terminate at the end of a renewal period.",
    "Post-Termination Services": "A clause requiring transition assistance, wind-down support, or continuing services after termination.",
    "Price Restrictions": "A clause limiting pricing, discounts, resale price, or price changes.",
    "Renewal Term": "A clause defining an automatic or optional renewal period or extension term.",
    "Revenue/Profit Sharing": "A clause allocating revenue, profit, royalties, commissions, or similar proceeds between parties.",
    "Rofr/Rofo/Rofn": "A clause giving a right of first refusal, right of first offer, or right of first negotiation.",
    "Source Code Escrow": "A clause requiring source code or related materials to be placed in escrow and released on defined triggers.",
    "Termination For Convenience": "A clause allowing a party to terminate without cause, often on notice and at its discretion.",
    "Third Party Beneficiary": "A clause giving enforceable rights to a non-party beneficiary.",
    "Uncapped Liability": "A clause stating that liability is uncapped, unlimited, or not subject to a monetary limit.",
    "Unlimited/All-You-Can-Eat-License": "A clause granting unlimited, broad, or uncapped usage rights without a usage cap or quantity limit.",
    "Volume Restriction": "A clause limiting quantity, volume, usage, production, or throughput.",
    "Warranty Duration": "A clause stating the duration or period of a warranty or warranty coverage.",
}

# Hard negatives: if A is a candidate, remind the model how it differs from B.
CONTRASTIVE_HINTS: list[tuple[str, str, str]] = [
    ("Cap On Liability", "Uncapped Liability",
     "Cap sets a maximum; Uncapped explicitly removes or rejects a monetary limit."),
    ("Non-Compete", "Exclusivity",
     "Non-Compete restricts competing activity; Exclusivity restricts dealing with other counterparties."),
    ("License Grant", "Ip Ownership Assignment",
     "License Grant allows use; Ip Ownership Assignment transfers ownership."),
    ("Termination For Convenience", "Notice Period To Terminate Renewal",
     "Convenience is terminate for any reason; Notice-to-stop-renewal only blocks auto-renewal."),
    ("No-Solicit Of Employees", "No-Solicit Of Customers",
     "Employees/personnel vs customers/clients/accounts."),
    ("Renewal Term", "Notice Period To Terminate Renewal",
     "Renewal Term defines the extension; Notice Period is the opt-out timing."),
]


def load_label_definitions(labels: list[str]) -> dict[str, str]:
    path = Path(LABEL_DEFINITIONS_PATH)
    existing: dict[str, str] = {}
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} must contain a JSON object mapping labels to definitions.")
        existing = {str(k): str(v) for k, v in loaded.items()}

    missing = [label for label in labels if label not in existing]
    if missing:
        for label in missing:
            definition = DEFAULT_LABEL_DEFINITIONS.get(label)
            if not definition:
                raise ValueError(f"Missing definition for label '{label}'.")
            existing[label] = definition
        ordered = {label: existing[label] for label in labels}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False), encoding="utf-8")
        existing = ordered

    return {label: existing[label] for label in labels if label in existing}


def _format_examples(examples: list[dict]) -> str:
    blocks: list[str] = []
    for index, example in enumerate(examples, start=1):
        score = float(example.get("score") or 0.0)
        clause_type = example.get("clause_type") or ""
        clause_text = example.get("clause_text") or ""
        if len(clause_text) > 900:
            clause_text = clause_text[:900] + "…"
        blocks.append(
            f"{index}. Label: {clause_type}\n"
            f"   Retrieval score: {score:.4f}\n"
            f"   Clause: \"{clause_text}\""
        )
    return "\n\n".join(blocks) if blocks else "None"


def _format_label_definitions(label_definitions: dict[str, str]) -> str:
    return "\n".join(f"- {label}: {definition}" for label, definition in label_definitions.items())


def _contrastive_block(allowed_labels: list[str]) -> str:
    allowed = {a.lower() for a in allowed_labels}
    lines: list[str] = []
    for a, b, hint in CONTRASTIVE_HINTS:
        if a.lower() in allowed and b.lower() in allowed:
            lines.append(f"- {a} vs {b}: {hint}")
    if not lines:
        return "None (no known hard pairs both present in candidates)."
    return "\n".join(lines)


def build_prompt(
    clause_text: str,
    examples: list[dict],
    labels: list[str],
    label_definitions: dict[str, str],
    extracted_features: dict[str, list[str]],
    candidate_labels: list[str] | None = None,
) -> str:
    allowed_labels = candidate_labels or labels
    label_list = "\n".join(f"- {label}" for label in allowed_labels)
    example_block = _format_examples(examples)
    defs_for_prompt = {
        label: label_definitions[label]
        for label in allowed_labels
        if label in label_definitions
    }
    label_definition_block = _format_label_definitions(defs_for_prompt)
    extracted_features_json = json.dumps(extracted_features, indent=2, ensure_ascii=False)
    contrastive = _contrastive_block(allowed_labels)

    return f"""You are a precise legal contract clause classifier for the CUAD taxonomy.

Task:
Identify the MAIN LEGAL FUNCTION of the clause and select exactly one label from the Allowed candidate list below.

Strict decision rules (follow in order):
1. Read the original clause carefully. Prefer the primary contractual function when several concepts appear.
2. Use retrieved training examples only as evidence. Do NOT automatically copy the top-1 label.
3. Compare the clause against the label definitions of the Allowed candidates.
4. When two similar labels appear, use the Hard-negative contrasts section.
5. Distinguish rights, obligations, restrictions, permissions, conditions, limitations, termination mechanisms, and financial commitments.
6. Do not rely on keyword matching alone.
7. Do not invent facts that are not supported by the clause text.
8. If the clause is metadata, boilerplate, or the evidence is weak / conflicting, return NO_APPLICABLE_LABEL.
9. UNKNOWN, OTHER, NONE, UNCLASSIFIED, NO_MATCH, and NO_LABEL are forbidden. Use NO_APPLICABLE_LABEL for safe abstention.

Output requirements:
- Return ONLY a single JSON object.
- Schema: {{"clause_type": "<one Allowed candidate or NO_APPLICABLE_LABEL>"}}
- No markdown, no explanation, no extra keys.

Original clause:
\"{clause_text}\"

Allowed candidate CUAD categories:
{label_list}

CUAD label definitions (for Allowed candidates only):
{label_definition_block}

Hard-negative contrasts (only for pairs both in Allowed):
{contrastive}

Retrieved Top-K TRAIN examples (evidence, not automatic answers):
{example_block}

Extracted legal information:
{extracted_features_json}
"""
