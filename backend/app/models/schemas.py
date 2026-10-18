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
    risk_level: str | None = Field(default=None, description="Deprecated: ordinal severity labels are not used.")
    raw_support_score: float | None = Field(default=None, description="Uncalibrated diagnostic support signal; not a probability.")
    severity_signal: float | None = Field(default=None, description="Deprecated: ordinal severity signals are not used.")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="Calibrated probability that the predicted YES/NO finding matches adjudicated reviewer labels; null until a validated artifact exists.")
    confidence_status: str = "UNCALIBRATED"
    confidence_target: str = "PREDICTION_CORRECTNESS"
    confidence_calibration_version: str | None = None
    severity_status: str = "DEPRECATED_NOT_USED"
    severity_probabilities: dict[str, float] = Field(default_factory=dict, description="Deprecated; no severity probabilities are generated.")
    ground_truth_status: str = "NOT_AVAILABLE"
    why_flagged: str = ""
    evidence: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)
    supporting_sources: list[dict[str, Any]] = Field(default_factory=list)
    related_contract_context: list[dict[str, Any]] = Field(default_factory=list)
    severity_factors: dict[str, Any] = Field(default_factory=dict)
    score_components: dict[str, Any] = Field(default_factory=dict)
    base_score: int | None = None
    score_modifiers: list[dict[str, Any]] = Field(default_factory=list)
    final_score: int | None = None
    score_override_reason: str | None = None
    human_review_required: bool = True
    review_escalation: str = "STANDARD_REVIEW"
    severity_score: float | None = None
    source_tier: str | None = None
    jurisdiction: str | None = None
    effective_date: str | None = None
    contract_type: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    retrieval_date: str | None = None
    supporting_quote_or_paraphrase: str | None = None
    transferability: str | None = None
    legal_guidance_sources: list[dict[str, Any]] = Field(default_factory=list)


class ContractRiskAssessment(BaseModel):
    status: str = "NOT_AVAILABLE"
    overall_risk: str | None = Field(default=None, description="Categorical review outcome such as POTENTIAL_RISK, NO_RISK, or INSUFFICIENT_EVIDENCE; not a severity label.")
    overall_confidence: float | None = Field(default=None, description="No contract-level probability is emitted without a separately validated contract-level calibrator.")
    confidence_status: str = "NOT_CALIBRATED_FOR_CONTRACT_LEVEL"
    confidence_target: str = "PREDICTION_CORRECTNESS"
    overall_raw_risk_score: float | None = Field(default=None, description="Deprecated; contract-level severity scoring is disabled.")
    severity_status: str = "DEPRECATED_NOT_USED"
    rule_registry: dict[str, Any] = Field(default_factory=dict)
    risk_domains: list[dict[str, Any]] = Field(default_factory=list)
    deterministic_cross_checks: list[dict[str, Any]] = Field(default_factory=list)
    key_risks: list[dict[str, Any]] = Field(default_factory=list)
    affected_clauses: list[int] = Field(default_factory=list)
    reason: str = ""
    gold_status: str = "NOT_AVAILABLE"
    playbook_hash: str | None = None
    clause_findings: list[dict[str, Any]] = Field(default_factory=list)
    cross_clause_findings: list[dict[str, Any]] = Field(default_factory=list)
    document_findings: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_check_count: int = 0
    overall_score: int | None = Field(default=None, description="Deprecated: contract-level numeric severity score is not generated.")
    overall_severity: str | None = Field(default=None, description="Deprecated: ordinal severity labels are not generated.")
    aggregation_adjustments: list[dict[str, Any]] = Field(default_factory=list)
    human_review_required: bool = False
    high_count: int = Field(default=0, description="Deprecated compatibility field; always zero.")
    critical_count: int = Field(default=0, description="Deprecated compatibility field; always zero.")


class ContractMetadata(BaseModel):
    name: str | None = None
    document_hash: str | None = None
    document_version: str | None = None
    contract_type: str | None = None
    jurisdiction_candidates: list[str] = Field(default_factory=list)
    parties: list[str] = Field(default_factory=list)
    agreement_date: str | None = None
    effective_date: str | None = None
    effective_date_condition: str | None = None
    expiration_date: str | None = None
    expiration_terms: str | None = None
    governing_law: str | None = None
    dispute_forum: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    provenance: str | None = None
    source_filename: str | None = None


class ClauseResult(BaseModel):
    clause_index: int
    clause_text: str
    section_path: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    defined_terms_used: list[str] = Field(default_factory=list)
    linked_sections: list[str] = Field(default_factory=list)
    parties_affected: list[str] = Field(default_factory=list)
    beneficiary: str | None = None
    direction_of_obligation: str | None = None
    transaction_role: str | None = None
    commercial_purpose: str | None = None
    operational_trigger: str | None = None
    scope: dict[str, Any] = Field(default_factory=dict)
    rights_and_duties: list[str] = Field(default_factory=list)
    exceptions_carveouts: list[str] = Field(default_factory=list)
    economic_effect: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
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
    risk_level: str | None = Field(default=None, description="Deprecated: ordinal severity labels are not used.")
    risk_confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="Calibrated prediction-correctness probability when available.")
    risk_confidence_status: str = "UNCALIBRATED"
    risk_confidence_target: str = "PREDICTION_CORRECTNESS"
    risk_confidence_calibration_version: str | None = None
    risk_raw_support_score: float | None = Field(default=None, description="Uncalibrated support diagnostic; not a probability.")
    risk_severity_signal: float | None = Field(default=None, description="Deprecated.")
    risk_severity_status: str = "DEPRECATED_NOT_USED"
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
