"""Retrieve curated legal guidance from Qdrant for risk review."""

from __future__ import annotations

from typing import Callable
from threading import Lock

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from qdrant_client import models

from ..config import LEGAL_ALLOWED_SOURCE_TIERS, LEGAL_CONTRACT_TYPE, LEGAL_JURISDICTION, LEGAL_HYBRID_CANDIDATES, LEGAL_KNOWLEDGE_COLLECTION, LEGAL_KNOWLEDGE_TOP_K, LEGAL_RRF_K
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

_LEXICAL_LOCK = Lock()
_LEXICAL_CACHE: dict[str, tuple[TfidfVectorizer, object, list[dict]]] = {}


def _load_lexical_index(qdrant_client, collection_name: str):
    cached = _LEXICAL_CACHE.get(collection_name)
    if cached is not None:
        return cached
    with _LEXICAL_LOCK:
        cached = _LEXICAL_CACHE.get(collection_name)
        if cached is not None:
            return cached
        records = []
        offset = None
        while True:
            points, offset = qdrant_client.scroll(
                collection_name=collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                text = str(payload.get("retrieved_text") or "").strip()
                if text:
                    records.append({"id": str(point.id), "payload": payload, "text": text})
            if offset is None:
                break
        vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), sublinear_tf=True)
        matrix = vectorizer.fit_transform([item["text"] for item in records]) if records else None
        cached = (vectorizer, matrix, records)
        _LEXICAL_CACHE[collection_name] = cached
        return cached


def _filter_payload(payload: dict, allowed_source_tiers: tuple[str, ...], jurisdiction: str | None) -> bool:
    if allowed_source_tiers and str(payload.get("source_tier") or "").upper() not in set(allowed_source_tiers):
        return False
    if jurisdiction and str(payload.get("jurisdiction") or "") not in {jurisdiction, "unspecified", "international"}:
        return False
    return True


def _lexical_search(query: str, qdrant_client, collection_name: str, limit: int, allowed_source_tiers: tuple[str, ...], jurisdiction: str | None) -> list[dict]:
    vectorizer, matrix, records = _load_lexical_index(qdrant_client, collection_name)
    if matrix is None or not records:
        return []
    query_vector = vectorizer.transform([query])
    scores = (matrix @ query_vector.T).toarray().ravel()
    order = np.argsort(-scores)
    results = []
    for idx in order:
        record = records[int(idx)]
        if not _filter_payload(record["payload"], allowed_source_tiers, jurisdiction):
            continue
        results.append({"id": record["id"], "score": float(scores[int(idx)]), "payload": record["payload"]})
        if len(results) >= limit:
            break
    return results


def _rrf_merge(dense_hits: list, lexical_hits: list, rrf_k: int, limit: int) -> list:
    merged = {}
    for rank, hit in enumerate(dense_hits, start=1):
        merged.setdefault(str(hit.id), {"id": str(hit.id), "dense_score": 0.0, "lexical_score": 0.0, "payload": hit.payload or {}})
        merged[str(hit.id)]["dense_score"] = float(hit.score)
        merged[str(hit.id)]["rrf"] = merged[str(hit.id)].get("rrf", 0.0) + 1.0 / (rrf_k + rank)
    for rank, item in enumerate(lexical_hits, start=1):
        key = str(item["id"])
        merged.setdefault(key, {"id": key, "dense_score": 0.0, "lexical_score": 0.0, "payload": item["payload"]})
        merged[key]["lexical_score"] = float(item["score"])
        merged[key]["rrf"] = merged[key].get("rrf", 0.0) + 1.0 / (rrf_k + rank)
    return sorted(merged.values(), key=lambda x: x.get("rrf", 0.0), reverse=True)[:limit]

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


def _payload_to_result(hit, *, contract_type: str | None = None) -> dict:
    payload = hit.payload or {}
    source_contract_type = payload.get("contract_type")
    transferability = (
        "direct"
        if not contract_type or not source_contract_type or source_contract_type in {"commercial_general", contract_type}
        else "limited_by_analogy"
    )
    return {
        "rule_id": payload.get("rule_id") or payload.get("chunk_id"),
        "retrieved_text": payload.get("retrieved_text", ""),
        "source_name": payload.get("source_name"),
        "source_url": payload.get("source_url"),
        "title": payload.get("title"),
        "source_title": payload.get("source_title") or payload.get("title"),
        "clause_category": payload.get("clause_category"),
        "source_tier": payload.get("source_tier"),
        "authority_status": payload.get("authority_status"),
        "jurisdiction": payload.get("jurisdiction"),
        "effective_date": payload.get("effective_date"),
        "contract_type": source_contract_type,
        "retrieval_date": payload.get("retrieval_date"),
        "access_type": payload.get("access_type"),
        "license_status": payload.get("license_status"),
        "supporting_quote_or_paraphrase": payload.get("supporting_quote_or_paraphrase"),
        "transferability": transferability,
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
    allowed_source_tiers: tuple[str, ...] = LEGAL_ALLOWED_SOURCE_TIERS,
    jurisdiction: str | None = LEGAL_JURISDICTION,
    contract_type: str | None = LEGAL_CONTRACT_TYPE,
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

    must_filters = [
        models.FieldCondition(
            key="clause_category",
            match=models.MatchValue(value=category),
        )
    ]
    if allowed_source_tiers:
        must_filters.append(
            models.FieldCondition(
                key="source_tier",
                match=models.MatchAny(any=list(allowed_source_tiers)),
            )
        )
    if jurisdiction:
        must_filters.append(
            models.FieldCondition(
                key="jurisdiction",
                match=models.MatchValue(value=jurisdiction),
            )
        )
    category_filter = models.Filter(must=must_filters)
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

    results = [_payload_to_result(hit, contract_type=contract_type) for hit in hits]
    if progress_callback:
        progress_callback({
            "type": "progress",
            "stage": "legal_search",
            "message": f"Legal-guidance search complete ({len(results)} matches)",
            "matches": len(results),
        })
    return results
