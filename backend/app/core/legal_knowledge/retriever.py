"""Retrieve curated legal guidance from Qdrant for risk review."""

from __future__ import annotations

from typing import Callable

from qdrant_client import models

from ..config import LEGAL_KNOWLEDGE_COLLECTION, LEGAL_KNOWLEDGE_TOP_K
from ..rag.embedder import embed_queries, make_cohere_client
from ..rag.retriever import make_qdrant_client

ProgressCallback = Callable[[dict], None]

CATEGORY_QUERY_TERMS = {
    "Limitation of Liability": "liability cap uncapped liability exclusions damages carve-outs defense costs",
    "Indemnification": "indemnify defend hold harmless third party claims settlement notice losses",
    "Termination": "termination cure period notice renewal suspension transition assistance survival accrued payment",
    "Intellectual Property": "intellectual property ownership assignment license scope territory field of use software sublicensing confidentiality technology transfer IP indemnification",
    "Confidentiality": "confidential information definition disclosure access restrictions permitted use duration non-disclosure trade secrets",
    "Payment": "payment terms invoice prices charges fees due date late payment interest suspension",
    "Force Majeure": "force majeure hardship unforeseen event notice mitigation performance termination adaptation",
    "Insurance": "insurance coverage policy limits certificate additional insured maintain coverage",
    "Warranties": "warranties disclaimers as-is scope duration remedies conformity performance",
    "Assignment": "assignment novation transfer consent change of control affiliate restrictions",
    "Dispute Resolution": "arbitration mediation alternative dispute resolution seat rules appointment confidentiality settlement",
    "Termination Assistance": "termination assistance transition data return continuity post-termination services",
    "Suspension Rights": "suspension rights service suspension notice cure payment security operational continuity",
    "Non-Solicitation": "non-solicitation employees customers personnel restrictions duration",
    "Sub-Contracting": "subcontracting subcontractor consent responsibility flow-down obligations",
    "Order of Precedence": "order of precedence conflict documents agreement priority",
}

CLAUSE_TYPE_TO_CATEGORY = {
    "Cap On Liability": "Limitation of Liability",
    "Uncapped Liability": "Limitation of Liability",
    "Indemnification": "Indemnification",
    "Termination For Convenience": "Termination",
    "Notice Period To Terminate Renewal": "Termination",
    "Renewal Term": "Termination",
    "Post-Termination Services": "Termination",
    "Ip Ownership Assignment": "Intellectual Property",
    "Joint Ip Ownership": "Intellectual Property",
    "License Grant": "Intellectual Property",
    "Non-Transferable License": "Intellectual Property",
    "Affiliate License-Licensor": "Intellectual Property",
    "Affiliate License-Licensee": "Intellectual Property",
    "Unlimited/All-You-Can-Eat-License": "Intellectual Property",
    "Irrevocable Or Perpetual License": "Intellectual Property",
    "Source Code Escrow": "Intellectual Property",
    "Confidentiality": "Confidentiality",
    "Non-Disclosure Agreement": "Confidentiality",
    "Payment Terms": "Payment",
    "Prices And Charges": "Payment",
    "Force Majeure": "Force Majeure",
    "Insurance": "Insurance",
    "Warranties": "Warranties",
    "Assignment": "Assignment",
    "Change Of Control": "Assignment",
    "Arbitration": "Dispute Resolution",
    "Alternative Dispute Resolution": "Dispute Resolution",
    "Governing Law": "Dispute Resolution",
    "Non-Solicitation": "Non-Solicitation",
    "Sub-Contracting": "Sub-Contracting",
    "Suspension Rights": "Suspension Rights",
    "Order Of Precedence": "Order of Precedence",
    "Post-Termination Services": "Termination Assistance",
}


def map_clause_category(clause_type: str) -> str | None:
    normalized = str(clause_type or "").strip()
    if normalized in CATEGORY_QUERY_TERMS:
        return normalized
    if normalized in CLAUSE_TYPE_TO_CATEGORY:
        return CLAUSE_TYPE_TO_CATEGORY[normalized]
    lowered = normalized.lower()
    if "liability" in lowered:
        return "Limitation of Liability"
    if "indemn" in lowered:
        return "Indemnification"
    if "termination" in lowered or "renewal" in lowered:
        return "Termination"
    if "confidential" in lowered or "non-disclosure" in lowered:
        return "Confidentiality"
    if any(term in lowered for term in ("payment", "price", "charge", "invoice", "fee")):
        return "Payment"
    if "force majeure" in lowered or "hardship" in lowered:
        return "Force Majeure"
    if "insurance" in lowered:
        return "Insurance"
    if "warrant" in lowered:
        return "Warranties"
    if "arbitr" in lowered or "mediat" in lowered or "dispute resolution" in lowered:
        return "Dispute Resolution"
    if "assign" in lowered or "change of control" in lowered or "novation" in lowered:
        return "Assignment"
    if "subcontract" in lowered:
        return "Sub-Contracting"
    if "non-solicit" in lowered or "solicitation" in lowered:
        return "Non-Solicitation"
    if "suspend" in lowered:
        return "Suspension Rights"
    if "order of precedence" in lowered or "priority" in lowered:
        return "Order of Precedence"
    if (
        "intellectual" in lowered
        or " ip " in f" {lowered} "
        or "license" in lowered
        or "licence" in lowered
        or "sublicens" in lowered
        or "ownership" in lowered
        or "source code" in lowered
    ):
        return "Intellectual Property"
    return None


def build_guidance_query(clause_text: str, clause_type: str) -> tuple[str, str | None]:
    category = map_clause_category(clause_type)
    category_terms = CATEGORY_QUERY_TERMS.get(category or "", "")
    query = f"{category or clause_type} {category_terms} {clause_text}".strip()
    return query, category


def _payload_to_result(hit) -> dict:
    payload = hit.payload or {}
    return {
        "rule_id": payload.get("rule_id") or payload.get("chunk_id"),
        "retrieved_text": payload.get("retrieved_text", ""),
        "source_name": payload.get("source_name"),
        "source_url": payload.get("source_url"),
        "title": payload.get("title"),
        "clause_category": payload.get("clause_category"),
        "relevance_score": round(float(hit.score), 4),
    }


def retrieve_legal_guidance(
    clause_text: str,
    classified_clause_type: str,
    *,
    cohere_client=None,
    qdrant_client=None,
    top_k: int = LEGAL_KNOWLEDGE_TOP_K,
    collection_name: str = LEGAL_KNOWLEDGE_COLLECTION,
    progress_callback: ProgressCallback | None = None,
) -> list[dict]:
    query, category = build_guidance_query(clause_text, classified_clause_type)
    if not category:
        return []

    cohere_client = cohere_client or make_cohere_client()
    qdrant_client = qdrant_client or make_qdrant_client()
    if progress_callback:
        progress_callback({
            "type": "progress",
            "stage": "legal_embedding",
            "message": "Embedding the legal-guidance query",
        })
    query_vector = embed_queries(cohere_client, [query])[0]

    category_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="clause_category",
                match=models.MatchValue(value=category),
            )
        ]
    )
    if progress_callback:
        progress_callback({
            "type": "progress",
            "stage": "legal_search",
            "message": f"Searching legal guidance for {category}",
        })
    response = qdrant_client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=top_k,
        query_filter=category_filter,
    )
    hits = getattr(response, "points", response)

    results = [_payload_to_result(hit) for hit in hits]
    if progress_callback:
        progress_callback({
            "type": "progress",
            "stage": "legal_search",
            "message": f"Legal-guidance search complete ({len(results)} matches)",
            "matches": len(results),
        })
    return results
