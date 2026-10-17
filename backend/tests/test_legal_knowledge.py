import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.core.legal_knowledge import ingest
from app.core.legal_knowledge.retriever import (
    build_guidance_query,
    retrieve_legal_guidance,
)
from app.core.risk import risk_detector
from app.models.schemas import ClauseResult


def test_ingestion_reads_metadata_chunks_and_upserts(monkeypatch, tmp_path):
    source_dir = tmp_path / "worldcc"
    source_dir.mkdir()
    (source_dir / "termination.md").write_text(
        """---
source_name: WorldCC
source_url: https://example.com/worldcc
title: Term and Termination
clause_category: Termination
document_filename: termination.md
source_tier: B
authority_status: NON_BINDING_PROFESSIONAL_PRACTICE
jurisdiction: international
contract_type: commercial_general
access_type: public
license_status: reference_only
---

Termination guidance for notice, cure, transition, and survival.
""",
        encoding="utf-8",
    )

    upserts = {}

    class FakeQdrant:
        def collection_exists(self, collection_name):
            return False

        def create_collection(self, collection_name, vectors_config):
            upserts["collection"] = collection_name
            upserts["vector_size"] = vectors_config.size

        def upsert(self, collection_name, points, wait):
            upserts["upsert_collection"] = collection_name
            upserts["points"] = points
            upserts["wait"] = wait

    monkeypatch.setattr(ingest, "make_cohere_client", lambda: object())
    monkeypatch.setattr(ingest, "embed_documents", lambda client, texts: [[0.1, 0.2]])
    monkeypatch.setattr(ingest, "make_qdrant_client", lambda: FakeQdrant())

    count = ingest.ingest_legal_knowledge(
        collection_name="legal_knowledge_test",
        base_path=tmp_path,
    )

    assert count == 1
    assert upserts["collection"] == "legal_knowledge_test"
    assert upserts["upsert_collection"] == "legal_knowledge_test"
    assert upserts["vector_size"] == 2
    payload = upserts["points"][0].payload
    assert payload["clause_category"] == "Termination"
    assert payload["source_name"] == "WorldCC"
    assert payload["chunk_id"]
    assert "Termination guidance" in payload["retrieved_text"]


def test_legal_knowledge_retrieval_prioritizes_category(monkeypatch):
    captured = {}

    class FakeQdrant:
        def scroll(self, **kwargs):
            return ([], None)

        def query_points(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                points=[
                    SimpleNamespace(
                        id="termination-guidance-1",
                        score=0.91,
                        payload={
                            "retrieved_text": "Review termination cure periods.",
                            "source_name": "WorldCC",
                            "source_url": "https://example.com",
                            "title": "Term and Termination",
                            "clause_category": "Termination",
                        },
                    )
                ]
            )

    monkeypatch.setattr(
        "app.core.legal_knowledge.retriever.embed_queries",
        lambda client, texts: [[0.1, 0.2]],
    )

    results = retrieve_legal_guidance(
        "Either party may terminate immediately.",
        "Termination For Convenience",
        cohere_client=object(),
        qdrant_client=FakeQdrant(),
        collection_name="legal_knowledge_test",
    )

    assert results[0]["source_name"] == "WorldCC"
    assert results[0]["dense_score"] == 0.91
    assert results[0]["rrf_score"] > 0
    assert captured["collection_name"] == "legal_knowledge_test"
    assert captured["query_filter"].must[0].match.value == "Termination"


def test_guidance_query_maps_liability_clause_type():
    query, category = build_guidance_query(
        "Liability shall not exceed fees paid.",
        "Cap On Liability",
    )

    assert category == "Limitation of Liability"
    assert "liability cap" in query


def test_guidance_query_maps_ip_clause_type():
    query, category = build_guidance_query(
        "The license is limited to internal software use in the United Kingdom.",
        "License Grant",
    )

    assert category == "Intellectual Property"
    assert "field of use" in query


def test_ingestion_skips_documentation_only_files(monkeypatch, tmp_path):
    (tmp_path / "source_catalog.md").write_text("# Catalog", encoding="utf-8")
    source_dir = tmp_path / "wipo"
    source_dir.mkdir()
    (source_dir / "intellectual_property.md").write_text(
        """---
source_name: World Intellectual Property Organization
source_url: https://www.wipo.int/en/web/technology-transfer/agreements
title: Technology Transfer Agreements
clause_category: Intellectual Property
document_filename: intellectual_property.md
---

IP licensing guidance.
""",
        encoding="utf-8",
    )

    upserts = {}

    class FakeQdrant:
        def collection_exists(self, collection_name):
            return True

        def upsert(self, collection_name, points, wait):
            upserts["points"] = points

    monkeypatch.setattr(ingest, "make_cohere_client", lambda: object())
    monkeypatch.setattr(ingest, "embed_documents", lambda client, texts: [[0.1, 0.2]])
    monkeypatch.setattr(ingest, "make_qdrant_client", lambda: FakeQdrant())

    count = ingest.ingest_legal_knowledge(
        collection_name="legal_knowledge_test",
        base_path=tmp_path,
    )

    assert count == 1
    assert upserts["points"][0].payload["clause_category"] == "Intellectual Property"


def test_risk_detector_parses_true_response():
    result = risk_detector.parse_risk_response(
        """
        {"risk": true, "risk_type": "Potential Uncapped Liability",
         "reason": "The clause excludes the cap for all losses.",
         "evidence": "liability is unlimited",
         "source": {"name": "WorldCC", "url": "https://example.com", "title": "Liability"}}
        """,
        {"name": "Fallback", "url": "https://fallback", "title": "Fallback"},
    )

    assert result["risk"] is True
    assert result["risk_type"] == "Potential Uncapped Liability"
    assert result["source"]["name"] == "WorldCC"


def test_risk_detector_parses_false_response():
    result = risk_detector.parse_risk_response(
        '{"risk": false, "risk_type": "Potential Risk", "reason": "Balanced.", '
        '"evidence": "", "source": {}}',
        {"name": "WorldCC", "url": "https://example.com", "title": "Termination"},
    )

    assert result["risk"] is False
    assert result["risk_type"] is None
    assert result["source"]["name"] == "WorldCC"


def test_risk_detector_rejects_non_boolean_risk_response():
    result = risk_detector.parse_risk_response(
        '{"risk": "false", "reason": "Looks clear."}',
        {"name": "WorldCC", "url": "https://example.com", "title": "Termination"},
    )

    assert result["risk"] is False
    assert result["risk_status"] == "ERROR"


def test_risk_detector_runs_for_unknown_classification(monkeypatch):
    monkeypatch.setattr(risk_detector, "retrieve_legal_guidance", lambda *a, **k: [])
    monkeypatch.setattr(
        risk_detector,
        "call_ollama",
        lambda prompt: '{"risk_status":"NO_RISK","risk_type":null,"risk_level":null,"reason":"No evidence-supported risk.","evidence":""}',
    )

    result = risk_detector.detect_clause_risk(
        "The clause was not classified.",
        "UNKNOWN",
        classification_status="UNKNOWN",
    )

    assert result["risk"] is False
    assert result["risk_status"] == "NO_RISK"


def test_risk_detector_requires_exact_evidence_for_positive_response(monkeypatch):
    monkeypatch.setattr(
        risk_detector,
        "retrieve_legal_guidance",
        lambda *args, **kwargs: [
            {
                "source_name": "WorldCC",
                "source_url": "https://example.com",
                "title": "Liability",
                "clause_category": "Limitation of Liability",
                "retrieved_text": "Review uncapped liability wording.",
                "relevance_score": 0.9,
            }
        ],
    )
    monkeypatch.setattr(
        risk_detector,
        "call_ollama",
        lambda prompt: '{"risk": true, "risk_type": "Potential Risk", "reason": "Review it", "evidence": "not in clause", "source": {}}',
    )

    result = risk_detector.detect_clause_risk(
        "Liability is unlimited.",
        "Uncapped Liability",
    )

    assert result["risk"] is False
    assert result["risk_status"] == "INSUFFICIENT_EVIDENCE"


def test_detect_clause_risk_false_for_unsupported_clause(monkeypatch):
    monkeypatch.setattr(risk_detector, "retrieve_legal_guidance", lambda *a, **k: [])
    monkeypatch.setattr(
        risk_detector,
        "call_ollama",
        lambda prompt: '{"risk_status":"NO_RISK","risk_type":null,"risk_level":null,"reason":"No evidence-supported risk.","evidence":""}',
    )

    result = risk_detector.detect_clause_risk("The agreement is governed by New York.", "Governing Law")

    assert result["risk"] is False
    assert result["risk_type"] is None
    assert result["risk_status"] == "NO_RISK"


def test_ip_broad_license_fallback_requires_strong_documented_indicator():
    result = risk_detector._strong_ip_indicator_result(
        "The licensee is granted an irrevocable, worldwide, perpetual, exclusive license to use, modify, reproduce, distribute, and sublicense the technology for any purpose.",
        "License Grant",
        {"matched_indicators": ["broad license scope"]},
        {"name": "WIPO", "url": "https://example.com", "title": "Technology Transfer Agreements"},
        {"risk": False},
    )

    assert result is not None
    assert result["risk"] is True
    assert result["risk_type"] == "Broad IP License Scope"


def test_ip_clear_license_guard():
    assert risk_detector._is_clear_limited_ip_license_without_indicator(
        "The license is non-exclusive, limited to the United Kingdom, and valid for three years solely for internal use.",
        "License Grant",
    )


def test_ip_clear_assignment_guard():
    assert risk_detector._is_clear_ip_assignment_without_indicator(
        "Supplier assigns all right, title, and interest in the intellectual property described in Schedule A.",
        "Ip Ownership Assignment",
    )


def test_ip_generic_risk_type_is_normalized_to_documented_indicator():
    result = risk_detector._normalize_ip_risk_type(
        {"risk": True, "risk_type": "Potential Risk Indicator"},
        {"matched_indicators": ["broad license scope"]},
        "License Grant",
    )

    assert result["risk_type"] == "Broad IP License Scope"


def test_clause_result_response_compatibility_with_existing_fields():
    result = ClauseResult(
        clause_index=0,
        clause_text="Either party may terminate on thirty days notice.",
        predicted_label="Termination For Convenience",
        retrieved_labels=["Termination For Convenience"],
        retrieved_scores=[0.82],
    )

    assert result.predicted_label == "Termination For Convenience"
    assert result.risk is False
    assert "risk" in result.model_dump()


def test_documents_classify_response_includes_legacy_and_risk_fields(monkeypatch):
    def fake_classify_contract(file_path, filename=None):
        return {"filename": filename or file_path.name, "contract_metadata": {}, "analysis_id": None, "clauses": [
            {
                "clause_index": 0,
                "clause_text": "Supplier shall indemnify Customer for third-party claims.",
                "predicted_label": "Indemnification",
                "clause_type": "Indemnification",
                "retrieved_labels": ["Indemnification"],
                "retrieved_scores": [0.9],
                "risk": True,
                "risk_type": "Potential Broad Indemnity",
                "reason": "The defense obligation may require review.",
                "evidence": "shall indemnify Customer",
                "source": {
                    "name": "American Bar Association",
                    "url": "https://example.com",
                    "title": "Negotiating Indemnity",
                },
            }
        ], "contract_risk_assessment": {"status": "COMPLETED", "overall_risk": "LOW", "summary": "ok"}}

    monkeypatch.setattr("app.api.routes.documents.classify_contract", fake_classify_contract)
    client = TestClient(app)

    response = client.post(
        "/documents/classify",
        files={"file": ("contract.txt", b"sample", "text/plain")},
    )

    assert response.status_code == 200
    clause = response.json()["clauses"][0]
    assert clause["predicted_label"] == "Indemnification"
    assert clause["retrieved_labels"] == ["Indemnification"]
    assert clause["risk"] is True
    assert response.json()["contract_risk_assessment"]["status"] == "COMPLETED"
