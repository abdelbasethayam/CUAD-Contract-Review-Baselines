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
]


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _contains_any(text: str, alternatives: list[str]) -> bool:
    return any(_normalize(item) in text for item in alternatives)


def _fact_attributed_to_entity(
    text: str,
    expected_entity: str,
    facts: list[str],
    *,
    window: int = 100,
) -> bool:
    """Check that a fact is mentioned nearer its expected contract party than the other party."""
    entity_patterns = {
        "customer": re.compile(r"\bcustomer(?:'s)?\b"),
        "supplier": re.compile(r"\bsupplier(?:'s)?\b"),
    }
    expected_pattern = entity_patterns.get(expected_entity)
    if expected_pattern is None:
        return False
    for fact in facts:
        for fact_match in re.finditer(re.escape(_normalize(fact)), text):
            fact_center = (fact_match.start() + fact_match.end()) / 2
            start = max(0, fact_match.start() - window)
            end = min(len(text), fact_match.end() + window)
            mentions = []
            for entity, pattern in entity_patterns.items():
                for entity_match in pattern.finditer(text, start, end):
                    entity_center = (entity_match.start() + entity_match.end()) / 2
                    mentions.append((abs(entity_center - fact_center), entity))
            if mentions and min(mentions, key=lambda item: item[0])[1] == expected_entity:
                return True
    return False


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
    checks: dict[str, bool] = {
        "answer_present": bool(answer.strip()),
        "not_abstained": answer_data.get("insufficient_evidence") is False,
        "has_verified_citations": bool(cited_texts) and not citation_errors,
        "citation_terms_present": all(_normalize(term) in cited_text for term in spec["must_cite_terms"]),
        "answer_contains_expected_concepts": all(
            _contains_any(normalized_answer, alternatives)
            for alternatives in spec["must_answer_one_of"]
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
