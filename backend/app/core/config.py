#config.py
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


# The workspace shell is configured with a dead localhost proxy. Clear it
# here so Cohere/httpx can reach the real API while keeping localhost
# requests for Ollama and Qdrant unaffected.
for proxy_var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
    proxy_value = os.getenv(proxy_var, "")
    if proxy_value.startswith("http://127.0.0.1:9") or proxy_value.startswith(
        "https://127.0.0.1:9"
    ):
        os.environ.pop(proxy_var, None)
        os.environ.pop(proxy_var.lower(), None)


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Cohere (must match the model used to build the Qdrant index in
# embed_train.py, or retrieval similarity will be meaningless)
# --------------------------------------------------------------------------
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
COHERE_MODEL = os.getenv(
    "COHERE_MODEL",
    os.getenv("COHERE_EMBED_MODEL", "embed-english-v3.0"),
)
COHERE_EMBED_BATCH_SIZE = int(os.getenv("COHERE_BATCH_SIZE", "96"))
COHERE_MAX_RETRY_ATTEMPTS = int(os.getenv("COHERE_MAX_RETRY_ATTEMPTS", "8"))


# --------------------------------------------------------------------------
# Qdrant (same collection built by build_qdrant_collection.py)
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Retrieval + model providers
# --------------------------------------------------------------------------
TOP_K = int(os.getenv("TOP_K", "5"))

CONTRACT_CONTEXT_TOP_K = int(os.getenv("CONTRACT_CONTEXT_TOP_K", "5"))

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
    """Return safe provider configuration metadata without exposing secrets."""
    return {
        "api_key_configured": bool(OPENROUTER_API_KEY),
        "model": OPENROUTER_MODEL,
        "base_url": OPENROUTER_BASE_URL,
    }


def validate_openrouter_configuration(api_key: str | None = None) -> None:
    """Raise a clear runtime error only when a provider call is requested."""
    if not (OPENROUTER_API_KEY if api_key is None else api_key):
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured. Set it in the environment "
            "or in backend/.env before running classification or risk analysis."
        )

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300"))
OLLAMA_MAX_RETRY_ATTEMPTS = int(os.getenv("OLLAMA_MAX_RETRY_ATTEMPTS", "3"))


def load_labels() -> list[str]:
    """The fixed set of substantive clause-type labels the model is allowed
    to choose from -- derived from the TRAIN split so it always matches
    exactly what's indexed in Qdrant (metadata fields like Document Name /
    Parties / dates are excluded, same as in embed_train.py).
    """
    import pandas as pd

    df = pd.read_csv(TRAIN_DATA_PATH)
    if "is_metadata" not in df.columns:
        df["is_metadata"] = False
    labels = sorted(df.loc[~df["is_metadata"].astype(bool), "clause_type"].unique())
    return labels
