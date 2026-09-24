"""
Prompt construction for the Qwen/Ollama clause classifier.

Kept separate from generator.py so prompt wording, instructions, and
label definitions can be tuned without touching the Ollama call, response
parsing, or pipeline orchestration.

Location: app/core/rag/prompt.py
"""

from __future__ import annotations

import json

from ..config import LABEL_DEFINITIONS_PATH


# --------------------------------------------------------------------------
# Label definitions (the CUAD labels the model is allowed to choose from,
# with a human-readable definition of each -- injected into the prompt so
# the model isn't guessing from the label name alone)
# --------------------------------------------------------------------------
DEFAULT_LABEL_DEFINITIONS: dict[str, str] = {
    "Affiliate License-Licensee": (
        "License rights are granted to the licensee's affiliates, "
        "subsidiaries, parent companies, or related entities."
    ),
    "Affiliate License-Licensor": (
        "License rights are granted to, reserved for, or shared with the "
        "licensor's affiliates, subsidiaries, parent companies, or related "
        "entities."
    ),
    "Anti-Assignment": (
        "A clause restricting assignment, delegation, transfer, or "
        "subcontracting of the agreement or its rights and duties."
    ),
    "Audit Rights": (
        "A clause giving one party the right to inspect, audit, or review "
        "books, records, systems, or compliance."
    ),
    "Cap On Liability": (
        "A clause setting an express maximum amount or formula that limits "
        "liability exposure."
    ),
    "Change Of Control": (
        "A clause triggered by a merger, acquisition, ownership change, or "
        "similar change in control."
    ),
    "Competitive Restriction Exception": (
        "A clause that carves out permitted competitive activity from an "
        "otherwise restrictive non-compete or exclusivity provision."
    ),
    "Covenant Not To Sue": (
        "A clause where a party promises not to sue, assert claims, or bring "
        "infringement actions."
    ),
    "Exclusivity": (
        "A clause making a relationship exclusive, sole, or restricted to "
        "one counterparty, channel, product, or territory."
    ),
    "Governing Law": (
        "A clause specifying the law, jurisdiction, or venue that governs "
        "interpretation or disputes."
    ),
    "Insurance": (
        "A clause requiring insurance coverage, policy types, limits, "
        "certificates, or proof of insurance."
    ),
    "Ip Ownership Assignment": (
        "A clause assigning or transferring intellectual property ownership "
        "or future IP rights to a party."
    ),
    "Irrevocable Or Perpetual License": (
        "A clause granting a license that is irrevocable, perpetual, "
        "permanent, or continuing indefinitely."
    ),
    "Joint Ip Ownership": (
        "A clause stating that intellectual property is jointly owned by two "
        "or more parties."
    ),
    "License Grant": (
        "A clause that grants a license, right, permission, or authorization "
        "to use specified IP, data, or materials."
    ),
    "Liquidated Damages": (
        "A clause setting a pre-agreed damages amount or formula for a "
        "specified breach or delay."
    ),
    "Minimum Commitment": (
        "A clause requiring a minimum purchase, spend, volume, output, or "
        "other contractual commitment."
    ),
    "Most Favored Nation": (
        "A clause requiring parity with the best price, terms, or treatment "
        "given to another counterparty."
    ),
    "No-Solicit Of Customers": (
        "A clause prohibiting solicitation of customers, clients, or "
        "accounts."
    ),
    "No-Solicit Of Employees": (
        "A clause prohibiting solicitation, hiring, or recruitment of "
        "employees, contractors, or personnel."
    ),
    "Non-Compete": (
        "A clause prohibiting competing business activity, products, "
        "services, or market participation."
    ),
    "Non-Transferable License": (
        "A clause stating that a license may not be assigned, transferred, or "
        "sublicensed."
    ),
    "Notice Period To Terminate Renewal": (
        "A clause requiring advance notice to stop automatic renewal or to "
        "terminate at the end of a renewal period."
    ),
    "Post-Termination Services": (
        "A clause requiring transition assistance, wind-down support, or "
        "continuing services after termination."
    ),
    "Price Restrictions": (
        "A clause limiting pricing, discounts, resale price, or price "
        "changes."
    ),
    "Renewal Term": (
        "A clause defining an automatic or optional renewal period or "
        "extension term."
    ),
    "Revenue/Profit Sharing": (
        "A clause allocating revenue, profit, royalties, commissions, or "
        "similar proceeds between parties."
    ),
    "Rofr/Rofo/Rofn": (
        "A clause giving a right of first refusal, right of first offer, or "
        "right of first negotiation."
    ),
    "Source Code Escrow": (
        "A clause requiring source code or related materials to be placed in "
        "escrow and released on defined triggers."
    ),
    "Termination For Convenience": (
        "A clause allowing a party to terminate without cause, often on "
        "notice and at its discretion."
    ),
    "Third Party Beneficiary": (
        "A clause giving enforceable rights to a non-party beneficiary."
    ),
    "Uncapped Liability": (
        "A clause stating that liability is uncapped, unlimited, or not "
        "subject to a monetary limit."
    ),
    "Unlimited/All-You-Can-Eat-License": (
        "A clause granting unlimited, broad, or uncapped usage rights without "
        "a usage cap or quantity limit."
    ),
    "Volume Restriction": (
        "A clause limiting quantity, volume, usage, production, or throughput."
    ),
    "Warranty Duration": (
        "A clause stating the duration or period of a warranty or warranty "
        "coverage."
    ),
}


def load_label_definitions(labels: list[str]) -> dict[str, str]:
    """Load label definitions from disk, filling in any missing ones from
    DEFAULT_LABEL_DEFINITIONS and persisting the repaired file. Raises if a
    label has no definition anywhere, or if the file contains stale labels
    no longer in config.load_labels().
    """
    path = LABEL_DEFINITIONS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, str] = {}
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(
                f"{path} must contain a JSON object mapping labels to definitions."
            )
        existing = {str(k): str(v) for k, v in loaded.items()}

    missing = [label for label in labels if label not in existing]
    extra = [label for label in existing if label not in labels]

    if missing:
        for label in missing:
            definition = DEFAULT_LABEL_DEFINITIONS.get(label)
            if not definition:
                raise ValueError(
                    f"Missing definition for label '{label}' and no fallback was provided."
                )
            existing[label] = definition

        ordered = {label: existing[label] for label in labels}
        path.write_text(
            json.dumps(ordered, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        existing = ordered

    if extra:
        raise ValueError(
            f"{path} contains unexpected labels not present in config.load_labels(): "
            + ", ".join(sorted(extra))
        )

    missing_after = [label for label in labels if label not in existing]
    if missing_after:
        raise ValueError(
            "Label-definition coverage is incomplete after repair: "
            + ", ".join(missing_after)
        )

    return {label: existing[label] for label in labels}


# --------------------------------------------------------------------------
# Prompt template
# --------------------------------------------------------------------------
def _format_examples(examples: list[dict]) -> str:
    blocks: list[str] = []
    for index, example in enumerate(examples, start=1):
        score = example["score"]
        clause_type = example["clause_type"]
        clause_text = example["clause_text"]
        blocks.append(
            f"{index}. Label: {clause_type}\n"
            f"   Retrieval score: {score:.4f}\n"
            f"   Clause: \"{clause_text}\""
        )
    return "\n\n".join(blocks)


def _format_label_definitions(label_definitions: dict[str, str]) -> str:
    blocks: list[str] = []
    for label in label_definitions:
        blocks.append(f"- {label}: {label_definitions[label]}")
    return "\n".join(blocks)


def build_prompt(
    clause_text: str,
    examples: list[dict],
    labels: list[str],
    label_definitions: dict[str, str],
    extracted_features: dict[str, list[str]],
    candidate_labels: list[str] | None = None,
) -> str:
    """
    Prompt-tuning notes:
    - Decision rules are stated explicitly and ordered by priority for the
      configured local Ollama model.
    - "Return ONLY a JSON object" is paired with local validation because
      local Ollama is instructed to return the response schema as JSON.
    - Retrieved examples are framed as "evidence, not automatic answers"
      to discourage the model from just copying the top-1 retrieval hit's
      label without reasoning about the actual clause text.
    - If you change the section headers below, also check
      parse_prediction() in generator.py -- it does NOT depend on this
      exact wording, but keep the final JSON-format instruction intact,
      since that's what response parsing relies on.
    """
    allowed_labels = candidate_labels or labels
    label_list = "\n".join(f"- {label}" for label in allowed_labels)
    example_block = _format_examples(examples) if examples else "None"
    label_definition_block = _format_label_definitions(label_definitions)
    extracted_features_json = json.dumps(
        extracted_features,
        indent=2,
        ensure_ascii=False,
    )

    return f"""You are a legal contract clause classifier for CUAD.

Task:
Identify the MAIN LEGAL FUNCTION of the clause and select exactly one label from the allowed CUAD candidates.

Decision rules:
- Use the clause text, the extracted legal information, the label definitions, and the retrieved training examples together.
- Use retrieved examples as evidence, not as automatic answers.
- Distinguish rights, obligations, restrictions, permissions, conditions, limitations, termination mechanisms, and financial commitments.
- Prefer the primary contractual function when several concepts appear.
- Do not rely on keyword matching alone.
- Do not invent facts.
- Select exactly one allowed CUAD label only when the clause and retrieval evidence support it.
- If the clause is metadata or the evidence is weak, return {{"clause_type":"NO_APPLICABLE_LABEL"}}.
- Do not force a label when retrieval confidence is low or the classifier cannot support a candidate.
- UNKNOWN, OTHER, NONE, UNCLASSIFIED, NO_MATCH, and NO_LABEL are forbidden outputs; use NO_APPLICABLE_LABEL for a safe abstention.
- Return ONLY a JSON object in this exact format:
  {{"clause_type": "<one allowed candidate category>"}}

Original clause:
"{clause_text}"

Allowed candidate CUAD categories:
{label_list}

CUAD label definitions:
{label_definition_block}

Retrieved Top-K TRAIN examples:
{example_block}

Extracted legal information:
{extracted_features_json}
"""
