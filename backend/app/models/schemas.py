from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RiskFinding(BaseModel):
    clause_id: int | None = None
    clause_type: str | None = None
    check_id: str | None = None
    question: str | None = None
    answer: str | None = None
    risk_status: str = "INSUFFICIENT_EVIDENCE"
    risk: bool = False
    risk_type: str | None = None
    risk_level: str | None = None
    raw_support_score: float | None = None
    severity_signal: float | None = None
    confidence: float | None = None
    confidence_status: str = "UNCALIBRATED"
    severity_status: str = "UNCALIBRATED"
    ground_truth_status: str = "NOT_AVAILABLE"
    why_flagged: str = ""
    evidence: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)
    supporting_sources: list[dict[str, Any]] = Field(default_factory=list)
    related_contract_context: list[dict[str, Any]] = Field(default_factory=list)
    severity_factors: dict[str, Any] = Field(default_factory=dict)


class ContractRiskAssessment(BaseModel):
    status: str = "NOT_AVAILABLE"
    overall_risk: str | None = None
    overall_confidence: float | None = None
    confidence_status: str = "UNCALIBRATED"
    overall_raw_risk_score: float | None = None
    severity_status: str = "UNCALIBRATED"
    risk_domains: list[dict[str, Any]] = Field(default_factory=list)
    key_risks: list[dict[str, Any]] = Field(default_factory=list)
    affected_clauses: list[int] = Field(default_factory=list)
    reason: str = ""
    gold_status: str = "NOT_AVAILABLE"
    playbook_hash: str | None = None
    clause_findings: list[dict[str, Any]] = Field(default_factory=list)
    cross_clause_findings: list[dict[str, Any]] = Field(default_factory=list)
    document_findings: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_check_count: int = 0


class ContractMetadata(BaseModel):
    name: str | None = None
    parties: list[str] = Field(default_factory=list)
    agreement_date: str | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    governing_law: str | None = None
    source_filename: str | None = None


class ClauseResult(BaseModel):
    clause_index: int
    clause_text: str
    predicted_label: str = "NO_APPLICABLE_LABEL"
    clause_type: str | None = None
    retrieved_labels: list[str] = Field(default_factory=list)
    retrieved_scores: list[float | None] = Field(default_factory=list)
    candidate_labels: list[str] = Field(default_factory=list)
    retrieved_examples: list[dict[str, Any]] = Field(default_factory=list)
    raw_retrieved_labels: list[str] = Field(default_factory=list)
    raw_retrieved_scores: list[float | None] = Field(default_factory=list)
    raw_retrieved_examples: list[dict[str, Any]] = Field(default_factory=list)
    classification_status: str = "UNKNOWN"
    classification_source: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    classification_confidence: float | None = None
    retrieval_status: str = "ok"
    retrieval_error: str | None = None
    risk_findings: list[dict[str, Any]] = Field(default_factory=list)
    risk_status: str = "NOT_ANALYZED"
    risk: bool = False
    risk_type: str | None = None
    risk_level: str | None = None
    risk_confidence: float | None = None
    risk_confidence_status: str = "UNCALIBRATED"
    risk_severity_signal: float | None = None
    risk_severity_status: str = "UNCALIBRATED"
    risk_provenance: dict[str, Any] = Field(default_factory=dict)
    why_flagged: str = ""
    evidence: str = ""


class ContractClassificationResponse(BaseModel):
    filename: str
    total_clauses: int
    analysis_id: str | None = None
    pipeline_status: str = "COMPLETED"
    contract_metadata: ContractMetadata = Field(default_factory=ContractMetadata)
    clauses: list[ClauseResult] = Field(default_factory=list)
    contract_risk_assessment: ContractRiskAssessment = Field(
        default_factory=ContractRiskAssessment
    )
    downloads: dict[str, str] = Field(default_factory=dict)
