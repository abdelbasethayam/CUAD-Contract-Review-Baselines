# config.py
"""Central configuration for the CUAD classification + risk pipeline.

Includes hybrid retrieval (dense + TF-IDF RRF) settings for the improved
Qwen shortlist + letter-logprob path.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]

for dotenv_path in (
    PROJECT_ROOT / "backend" / ".env",
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / "scripts" / ".env",
):
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
        break


for proxy_var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
    proxy_value = os.getenv(proxy_var, "")
    if proxy_value.startswith("http://127.0.0.1:9") or proxy_value.startswith(
        "https://127.0.0.1:9"
    ):
        os.environ.pop(proxy_var, None)
        os.environ.pop(proxy_var.lower(), None)


TRAIN_DATA_PATH = (
    PROJECT_ROOT / "data" / "splits" / "train" / "master_clauses_train.csv"
)
TEST_DATA_PATH = (
    PROJECT_ROOT / "data" / "splits" / "test" / "master_clauses_test.csv"
)

RESULTS_DIR = PROJECT_ROOT / "data" / "results"
LABEL_DEFINITIONS_PATH = (
    PROJECT_ROOT / "data" / "metadata" / "cuad_label_definitions.json"
)
PREDICTIONS_PATH = RESULTS_DIR / "test_predictions.csv"
METRICS_PATH = RESULTS_DIR / "metrics.json"
CLASSIFICATION_REPORT_PATH = RESULTS_DIR / "classification_report.csv"
CONFUSION_MATRIX_PNG_PATH = RESULTS_DIR / "confusion_matrix.png"
CONFUSION_MATRIX_CSV_PATH = RESULTS_DIR / "confusion_matrix.csv"

RUNS_DIR = PROJECT_ROOT / "data" / "runs"
RISK_DATA_DIR = PROJECT_ROOT / "data" / "risk"
RISK_PLAYBOOK_PATH = Path(
    os.getenv(
        "RISK_PLAYBOOK_PATH",
        str(RISK_DATA_DIR / "commercial_clause_risk_playbook.json"),
    )
)
RISK_PLAYBOOK_VERSION = os.getenv("RISK_PLAYBOOK_VERSION", "starter-v1")
RISK_MODEL = os.getenv("RISK_MODEL", os.getenv("OLLAMA_MODEL", "qwen3:8b"))
RISK_NUM_CTX = int(os.getenv("RISK_NUM_CTX", "16384"))
RISK_TEMPERATURE = float(os.getenv("RISK_TEMPERATURE", "0.0"))
RISK_MAX_TOKENS = int(os.getenv("RISK_MAX_TOKENS", "1800"))
RISK_SELF_CONSISTENCY_PASSES = int(os.getenv("RISK_SELF_CONSISTENCY_PASSES", "3"))
RISK_CONTEXT_TOP_K = int(os.getenv("RISK_CONTEXT_TOP_K", "5"))
RISK_USE_PLAYBOOK = os.getenv("RISK_USE_PLAYBOOK", "true").strip().lower() in {"1", "true", "yes"}
RISK_USE_CONTEXT = os.getenv("RISK_USE_CONTEXT", "true").strip().lower() in {"1", "true", "yes"}
RISK_USE_LEGAL_GUIDANCE = os.getenv("RISK_USE_LEGAL_GUIDANCE", "true").strip().lower() in {"1", "true", "yes"}
RISK_ENABLE_CROSS_CLAUSE = os.getenv("RISK_ENABLE_CROSS_CLAUSE", "true").strip().lower() in {"1", "true", "yes"}
RISK_ENABLE_DOCUMENT_CHECKS = os.getenv("RISK_ENABLE_DOCUMENT_CHECKS", "true").strip().lower() in {"1", "true", "yes"}

RISK_GOLD_PATH = RISK_DATA_DIR / "gold" / "gold_annotations.csv"
RISK_CALIBRATION_PATH = RISK_DATA_DIR / "gold" / "calibration.json"
RISK_EXTERNAL_BENCHMARKS_PATH = RISK_DATA_DIR / "external_benchmarks.json"

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
COHERE_MODEL = os.getenv(
    "COHERE_MODEL",
    os.getenv("COHERE_EMBED_MODEL", "embed-english-v3.0"),
)
COHERE_EMBED_BATCH_SIZE = int(os.getenv("COHERE_BATCH_SIZE", "96"))
COHERE_MAX_RETRY_ATTEMPTS = int(os.getenv("COHERE_MAX_RETRY_ATTEMPTS", "8"))

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_PATH = os.getenv(
    "QDRANT_PATH", str(PROJECT_ROOT / "data" / "qdrant_local")
)
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "cuad_train")
LEGAL_KNOWLEDGE_COLLECTION = os.getenv(
    "LEGAL_KNOWLEDGE_COLLECTION", "legal_knowledge"
)
LEGAL_KNOWLEDGE_TOP_K = int(os.getenv("LEGAL_KNOWLEDGE_TOP_K", "3"))
_LEGAL_KNOWLEDGE_PATH_VALUE = os.getenv(
    "LEGAL_KNOWLEDGE_PATH",
    str(PROJECT_ROOT / "backend" / "data" / "legal_knowledge"),
)
LEGAL_KNOWLEDGE_PATH = Path(_LEGAL_KNOWLEDGE_PATH_VALUE)
if not LEGAL_KNOWLEDGE_PATH.is_absolute():
    LEGAL_KNOWLEDGE_PATH = PROJECT_ROOT / LEGAL_KNOWLEDGE_PATH

TOP_K = int(os.getenv("TOP_K", "12"))
CONTRACT_CONTEXT_TOP_K = int(os.getenv("CONTRACT_CONTEXT_TOP_K", "5"))
MIN_RETRIEVAL_CONFIDENCE = float(os.getenv("MIN_RETRIEVAL_CONFIDENCE", "0.32"))

# Hybrid dense + TF-IDF RRF (Claude / measured path)
HYBRID_COLLECTION = os.getenv("HYBRID_COLLECTION", "cuad_train_mpnet")
HYBRID_INDEX_CACHE = os.getenv(
    "HYBRID_INDEX_CACHE",
    str(PROJECT_ROOT / "output" / "cache" / "cuad_train_mpnet_hybrid.npz"),
)
HYBRID_K = int(os.getenv("HYBRID_K", "30"))
HYBRID_SHORTLIST = int(os.getenv("HYBRID_SHORTLIST", "8"))
HYBRID_EMBEDDING_MODEL = os.getenv(
    "HYBRID_EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2"
)
HYBRID_RERANKER_MODEL = os.getenv(
    "HYBRID_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"
)
HYBRID_RERANK = os.getenv("HYBRID_RERANK", "true").strip().lower() in {"1", "true", "yes"}
HYBRID_RERANK_TOP_K = int(os.getenv("HYBRID_RERANK_TOP_K", "30"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free"
)
OPENROUTER_RISK_MODEL = os.getenv(
    "OPENROUTER_RISK_MODEL", "nex-agi/nex-n2.5-pro:free"
)
OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
).rstrip("/")
OPENROUTER_TIMEOUT_SECONDS = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "120"))
OPENROUTER_MAX_RETRY_ATTEMPTS = int(os.getenv("OPENROUTER_MAX_RETRY_ATTEMPTS", "3"))
OPENROUTER_TEMPERATURE = float(os.getenv("OPENROUTER_TEMPERATURE", "0"))
OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "700"))


def openrouter_config_status() -> dict[str, str | bool]:
    return {
        "api_key_configured": bool(OPENROUTER_API_KEY),
        "model": OPENROUTER_MODEL,
        "base_url": OPENROUTER_BASE_URL,
    }


def validate_openrouter_configuration(api_key: str | None = None) -> None:
    if not (OPENROUTER_API_KEY if api_key is None else api_key):
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured. Set it in the environment "
            "or in backend/.env before running classification or risk analysis."
        )


OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
)
# Prefer Instruct-style 7B for letter-logprob MCQ; override as needed.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))
OLLAMA_MAX_RETRY_ATTEMPTS = int(os.getenv("OLLAMA_MAX_RETRY_ATTEMPTS", "3"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
CLASSIFIER_TEMPERATURE = float(os.getenv("CLASSIFIER_TEMPERATURE", "0.0"))
CLASSIFIER_TOP_LOGPROBS = int(os.getenv("CLASSIFIER_TOP_LOGPROBS", "20"))
CLASSIFIER_THINK = os.getenv("CLASSIFIER_THINK", "false").strip().lower() in {"1", "true", "yes"}

HF_CLASSIFIER_MODEL = os.getenv(
    "HF_CLASSIFIER_MODEL", "Qwen/Qwen2.5-7B-Instruct"
)


def load_labels() -> list[str]:
    import pandas as pd

    df = pd.read_csv(TRAIN_DATA_PATH)
    if "is_metadata" not in df.columns:
        df["is_metadata"] = False
    labels = sorted(
        df.loc[~df["is_metadata"].astype(bool), "clause_type"].unique()
    )
    return labels
