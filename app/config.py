"""
Central configuration for FinGraph Analyst.
All tunable values and model names are read from environment variables,
with sensible defaults so the app still runs without a full .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# LLM Models
# ---------------------------------------------------------------------------
SUPERVISOR_MODEL: str = os.getenv("SUPERVISOR_MODEL", "gpt-4.1-nano")
EXTRACTION_MODEL: str = os.getenv("EXTRACTION_MODEL", "gpt-4.1-mini")
ANALYSIS_MODEL: str = os.getenv("ANALYSIS_MODEL", "gpt-4.1-nano")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# ---------------------------------------------------------------------------
# Neo4j
# ---------------------------------------------------------------------------
NEO4J_URI: str = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
NEO4J_GRAPH_LIMIT: int = int(os.getenv("NEO4J_GRAPH_LIMIT", "20"))

# ---------------------------------------------------------------------------
# Vector DB (Chroma)
# ---------------------------------------------------------------------------
CHROMA_PATH: str = os.getenv("CHROMA_PATH", "data/chroma_langchain")
EMBED_CACHE_PATH: str = os.getenv("EMBED_CACHE_PATH", "data/embedding_cache")

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
RETRIEVAL_K_MAX: int = int(os.getenv("RETRIEVAL_K_MAX", "10"))

CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))

# ---------------------------------------------------------------------------
# Relation Extraction & Filtering
# ---------------------------------------------------------------------------
# Minimum confidence to keep a relation after extraction
EXTRACTION_CONFIDENCE_THRESHOLD: float = float(
    os.getenv("EXTRACTION_CONFIDENCE_THRESHOLD", "0.65")
)
# Minimum confidence for a relation to be upserted into Neo4j
GRAPH_UPSERT_CONFIDENCE: float = float(os.getenv("GRAPH_UPSERT_CONFIDENCE", "0.8"))
# Minimum confidence for weak-tail / postprocessor filter
POSTPROCESS_MIN_CONFIDENCE: float = float(
    os.getenv("POSTPROCESS_MIN_CONFIDENCE", "0.75")
)

# ---------------------------------------------------------------------------
# Hybrid Graph Weighting  (current_weight + persistent_weight should sum to ~1)
# ---------------------------------------------------------------------------
HYBRID_CURRENT_WEIGHT: float = float(os.getenv("HYBRID_CURRENT_WEIGHT", "0.7"))
HYBRID_PERSISTENT_WEIGHT: float = float(os.getenv("HYBRID_PERSISTENT_WEIGHT", "0.3"))
HYBRID_UPSERT_MIN_CONFIDENCE: float = float(
    os.getenv("HYBRID_UPSERT_MIN_CONFIDENCE", "0.75")
)

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
API_URL: str = os.getenv("API_URL", "http://localhost:8000")
