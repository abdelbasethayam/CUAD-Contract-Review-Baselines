#!/usr/bin/env python3
"""Live semantic smoke test for the contract-linked chatbot on the synthetic demo.

Run the API and the configured local Ollama model first. This is a narrow,
human-readable demo check, not a statistically valid accuracy benchmark.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests


QUESTIONS = [
    {
        "id": "liability_cap_comparison",
        "question": "How does the supplier liability cap compare with the customer's cap?",
        "must_cite_terms": ["ten times", "previous one month"],
        "must_answer_one_of": [["ten times", "10 times"], ["one month", "monthly"]],
        "must_answer_relations": [
            {"entity": "customer", "facts": ["ten times", "10 times"]},
            {"entity": "supplier", "facts": ["one month", "monthly"]},
        ],
        "must_answer_all": [],
    },
    {
        "id": "termination_rights_comparison",
        "question": "What termination rights does each party have?",
        "must_cite_terms": ["immediately", "90 days"],
        "must_answer_one_of": [["immediately", "immediate"], ["90 days", "ninety days"]],
        "must_answer_relations": [
            {"entity": "supplier", "facts": ["immediately", "immediate"]},
            {"entity": "customer", "facts": ["90 days", "ninety days"]},
        ],
        "must_answer_all": [],
    },
    {
        "id": "governing_law_resolution",
        "question": "Can we determine the governing law from this agreement alone?",
        "must_cite_terms": ["order form"],
        "must_answer_one_of": [
            ["cannot determine", "can't determine", "not specified", "deferred", "unresolved", "depends on", "not possible to determine"]
        ],
        "must_answer_all": [],
    },
    {
        "id": "insurance_limits",
        "question": "What insurance must the supplier maintain, and does the agreement set minimum policy limits?",
        "must_cite_terms": ["commercially reasonable", "No minimum policy limits"],
        "must_answer_one_of": [
            ["no minimum policy limits", "minimum policy limits are not stated", "does not specify minimum policy limits", "no minimum limits are specified"],
            ["commercially reasonable"],
        ],
        "must_answer_all": [],
        "must_answer_relations": [
            {"entity": "supplier", "facts": ["commercially reasonable", "maintain insurance", "maintain coverage"]}
        ],
    },
    {
        "id": "customer_data_after_termination",
        "question": "What happens to customer data after termination, and does the agreement specify retention or deletion?",
        "must_cite_terms": ["disable Customer access immediately", "Customer must export all data before the effective termination date"],
        "must_answer_one_of": [
            ["export all data", "export data", "export its data"],
            ["disable access", "disable customer access", "turn off access"],
        ],
        "must_answer_all": [
            ["does not specify a retention period", "no retention period", "does not say how long", "retention period is not specified"],
            ["does not specify deletion", "does not address deletion", "does not say whether data is deleted", "deletion is not specified"],
        ],
    },
    {
        "id": "indemnity_and_liability_cap_interaction",
        "question": "Does the agreement clearly say whether indemnification obligations are subject to the aggregate liability caps?",
        "must_cite_terms": ["indemnification obligations", "aggregate liability exceed", "Customer shall indemnify"],
        "must_cite_clause_indices": [3, 4],
        "must_answer_one_of": [
            ["unclear", "ambiguous", "does not expressly state", "does not expressly say", "not clear"],
            ["aggregate liability cap", "aggregate liability caps", "aggregate caps", "liability cap"],
        ],
        "must_answer_all": [["indemnification", "indemnity"]],
    },
]


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _contains_any(text: str, alternatives: list[str]) -> bool:
    return any(_normalize(item) in text for item in alternatives)


def _fact_attributed_to_entity(
    text: str,
    expected_entity: str,
    facts: list[str],
) -> bool:
    """Check that a party and its expected fact occur in the same comparison segment."""
    entity_patterns = {
        "customer": re.compile(r"\bcustomer(?:'s)?\b"),
        "supplier": re.compile(r"\bsupplier(?:'s)?\b"),
    }
    entity_pattern = entity_patterns.get(expected_entity)
    if entity_pattern is None:
        return False
    segments = re.split(
        r"\s+(?:whereas|while|but|versus|vs\.?|compared with|compared to)\s+"
        r"|;\s*"
        r"|\s+and\s+(?=(?:the\s+)?(?:customer|supplier)\b)"
        r"|,\s*(?=(?:the\s+)?(?:customer|supplier)\b)",
        text,
    )
    return any(
        entity_pattern.search(segment)
        and any(_normalize(fact) in segment for fact in facts)
        for segment in segments
    )

def _evaluate_question(
    spec: dict[str, Any],
    answer_data: dict[str, Any],
    clauses_by_id: dict[int, str],
) -> dict[str, Any]:
    answer = str(answer_data.get("answer") or "")
    normalized_answer = _normalize(answer)
    citations = answer_data.get("citations") if isinstance(answer_data.get("citations"), list) else []
    cited_texts: list[str] = []
    citation_errors: list[str] = []
    for citation in citations:
        if not isinstance(citation, dict):
            citation_errors.append("citation_not_object")
            continue
        try:
            clause_index = int(citation.get("clause_index"))
        except (TypeError, ValueError):
            citation_errors.append("citation_has_invalid_clause_index")
            continue
        quote = _normalize(citation.get("quote"))
        source = _normalize(clauses_by_id.get(clause_index, ""))
        if not quote or not source or quote not in source:
            citation_errors.append(f"citation_not_found_in_source_clause:{clause_index}")
            continue
        cited_texts.append(quote)

    cited_text = " ".join(cited_texts)
    cited_clause_indices = {
        int(item["clause_index"])
        for item in citations
        if isinstance(item, dict) and str(item.get("clause_index", "")).isdigit()
    }
    required_clause_indices = {int(item) for item in spec.get("must_cite_clause_indices", [])}
    checks: dict[str, bool] = {
        "answer_present": bool(answer.strip()),
        "not_abstained": answer_data.get("insufficient_evidence") is False,
        "has_verified_citations": bool(cited_texts) and not citation_errors,
        "citation_terms_present": all(_normalize(term) in cited_text for term in spec["must_cite_terms"]),
        "required_clause_citations_present": required_clause_indices.issubset(cited_clause_indices),
        "answer_contains_expected_concepts": all(
            _contains_any(normalized_answer, alternatives)
            for alternatives in spec["must_answer_one_of"]
        ),
        "answer_contains_all_required_concepts": all(
            _contains_any(normalized_answer, alternatives)
            for alternatives in spec.get("must_answer_all", [])
        ),
        "party_fact_attribution_correct": all(
            _fact_attributed_to_entity(
                normalized_answer,
                relation["entity"],
                relation["facts"],
            )
            for relation in spec.get("must_answer_relations", [])
        ),
    }
    return {
        "id": spec["id"],
        "question": spec["question"],
        "answer": answer,
        "model": answer_data.get("model"),
        "citations": citations,
        "citation_errors": citation_errors,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("CONTRACT_REVIEW_BASE_URL", "http://127.0.0.1:8000"),
        help="Running contract-review API base URL.",
    )
    parser.add_argument("--timeout", type=int, default=180, help="Timeout per chatbot question in seconds.")
    parser.add_argument("--out", type=Path, help="Optional JSON report output path.")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    try:
        demo_response = requests.get(f"{base_url}/query/demo-analysis", timeout=30)
        demo_response.raise_for_status()
        demo = demo_response.json()
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": f"Could not load demo analysis: {exc}"}, indent=2))
        return 2

    clauses = demo.get("clauses") if isinstance(demo.get("clauses"), list) else []
    clauses_by_id = {}
    for clause in clauses:
        try:
            clauses_by_id[int(clause.get("clause_index"))] = str(clause.get("clause_text") or "")
        except (TypeError, ValueError):
            continue
    if not clauses_by_id:
        print(json.dumps({"status": "FAIL", "error": "Demo result contains no clause text."}, indent=2))
        return 2

    results = []
    for spec in QUESTIONS:
        try:
            response = requests.post(
                f"{base_url}/query/contract",
                json={
                    "analysis_id": demo["analysis_id"],
                    "question": spec["question"],
                    "history": [],
                },
                timeout=args.timeout,
            )
            response.raise_for_status()
            answer_data = response.json()
            results.append(_evaluate_question(spec, answer_data, clauses_by_id))
        except Exception as exc:
            results.append({
                "id": spec["id"],
                "question": spec["question"],
                "passed": False,
                "error": str(exc),
            })

    report = {
        "status": "PASS" if results and all(item.get("passed") for item in results) else "FAIL",
        "evaluation_type": "THREE_QUESTION_LIVE_CHAT_SMOKE_NOT_ACCURACY_BENCHMARK",
        "demo_mode": demo.get("demo_mode") is True,
        "analysis_id": demo.get("analysis_id"),
        "question_count": len(results),
        "passed_questions": sum(bool(item.get("passed")) for item in results),
        "results": results,
        "limitations": [
            "This small smoke test is a demo-quality gate, not a legal-risk accuracy estimate.",
            "It checks answer concepts and citation provenance for three curated synthetic questions only.",
            "A pass does not establish legal correctness, calibrated confidence, or generalization to real contracts.",
        ],
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
