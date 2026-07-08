"""Central configuration: paths, env vars, model/index settings."""
import os
from pathlib import Path

from dotenv import load_dotenv

RAG_ROOT = Path(__file__).resolve().parent.parent   # rag/
PROJECT_ROOT = RAG_ROOT.parent                       # repo root — where the tools' md files live
DATA_DIR = RAG_ROOT / "data"

load_dotenv(RAG_ROOT / ".env")

# NetFree environments intercept TLS; the starter's workaround is optional here.
try:  # pragma: no cover
    from netfree_unstrict_ssl import unstrict_ssl

    unstrict_ssl()
except ImportError:
    pass

COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")

PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "agentic-coding-docs")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "agentic-md")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# The corpus is mostly Hebrew + English — the multilingual model is a must
# (embed-english-v3.0 gives poor Hebrew recall).
EMBED_MODEL = os.getenv("COHERE_EMBED_MODEL", "embed-multilingual-v3.0")
EMBED_DIM = 1024
LLM_MODEL = os.getenv("COHERE_LLM_MODEL", "command-a-03-2025")

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50

# Retrieval / validation thresholds used by the workflow
TOP_K = 6
RETRY_TOP_K = 12
SIMILARITY_CUTOFF = 0.2      # postprocessor: drop clearly-irrelevant nodes
MIN_CONFIDENCE = 0.4         # best-score below this triggers a broadened retry
MAX_RETRIES = 1
MAX_QUERY_CHARS = 2000

KNOWLEDGE_FILE = DATA_DIR / "extracted_knowledge.json"
SCHEMA_VERSION = "1.0"


def require_env(*names: str) -> None:
    """Fail fast with a clear message instead of a deep stack trace later."""
    missing = [n for n in names if not os.getenv(n)]
    if missing:
        raise SystemExit(
            f"Missing environment variables: {', '.join(missing)}. "
            f"Copy rag/.env.example to rag/.env and fill in the keys."
        )
