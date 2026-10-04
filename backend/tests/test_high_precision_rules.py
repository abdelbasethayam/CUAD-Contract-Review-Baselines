"""Unit tests for high-precision CUAD rules and candidate utils."""
from __future__ import annotations

from backend.app.core.rag.high_precision_rules import high_precision_rule_label
from backend.app.core.rag.candidate_utils import diversify_by_label, fuse_confidence
from backend.app.core.rag.text_preprocessor import preprocess_clause


def test_governing_law_rule():
    text = (
        "This Agreement shall be governed by and construed in accordance with "
        "the laws of the State of New York, without regard to conflicts of law."
    )
    assert high_precision_rule_label(text) == "Governing Law"


def test_insurance_rule():
    text = "Party B shall purchase sufficient insurance; liability coverage shall not be lower than RMB 1 million."
    assert high_precision_rule_label(text) == "Insurance"


def test_termination_for_convenience_rule():
    text = "Either party may terminate this Agreement for any reason upon thirty (30) days prior written notice."
    assert high_precision_rule_label(text) == "Termination For Convenience"


def test_non_compete_rule():
    text = "Distributor will not market a competing computer program for two years after termination."
    assert high_precision_rule_label(text) == "Non-Compete"


def test_preprocess_expands_incl():
    out = preprocess_clause("includes software incl. documentation")
    assert "including" in out.lower()


def test_diversify_by_label():
    hits = [
        {"clause_type": "Insurance", "score": 0.9},
        {"clause_type": "Insurance", "score": 0.89},
        {"clause_type": "Insurance", "score": 0.88},
        {"clause_type": "Governing Law", "score": 0.7},
    ]
    out = diversify_by_label(hits, max_per_label=2, limit=3)
    labels = [h["clause_type"] for h in out]
    assert labels.count("Insurance") <= 2
    assert "Governing Law" in labels


def test_fuse_confidence_rule_and_model():
    c = fuse_confidence(
        retrieval_score=0.55,
        rule_agrees=True,
        model_valid=True,
        min_retrieval=0.32,
    )
    assert 0.5 <= c <= 1.0
