import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Postgres connection (PostGIS + pgvector enabled)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/dno_triage",
    )

    # Free, self-hosted embedding model (sentence-transformers)
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "384"))

    # RAG Q&A ("Ask Sahyog"). Same Ollama instance and model already used by
    # "2.Evidence Extractor" for C1/C3 - reusing it here means no second
    # model download and no risk of Ollama evicting one to load the other.
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    RAG_MODEL_NAME: str = os.getenv("RAG_MODEL_NAME", "llama3.2:3b")
    RAG_TOP_K_KB: int = int(os.getenv("RAG_TOP_K_KB", "4"))
    RAG_TOP_K_TICKETS: int = int(os.getenv("RAG_TOP_K_TICKETS", "3"))

    # D2 tuning knobs
    GEO_RADIUS_METERS: float = float(os.getenv("GEO_RADIUS_METERS", "100"))
    SIMILARITY_MERGE_THRESHOLD: float = float(
        os.getenv("SIMILARITY_MERGE_THRESHOLD", "0.85")
    )
    GEO_CANDIDATE_LIMIT: int = int(os.getenv("GEO_CANDIDATE_LIMIT", "25"))

    # G1 priority-score weights
    PRIORITY_SEVERITY_WEIGHT: float = float(os.getenv("PRIORITY_SEVERITY_WEIGHT", "1.0"))
    PRIORITY_CLUSTER_SIZE_WEIGHT: float = float(os.getenv("PRIORITY_CLUSTER_SIZE_WEIGHT", "1.0"))
    PRIORITY_AGE_HOURS_WEIGHT: float = float(os.getenv("PRIORITY_AGE_HOURS_WEIGHT", "0.1"))
    PRIORITY_POPULATION_IMPACT_WEIGHT: float = float(os.getenv("PRIORITY_POPULATION_IMPACT_WEIGHT", "1.0"))

    # Object storage (MinIO / any S3-compatible endpoint) - this service only
    # ever READS media_objects rows (to build a URL for the DNO dashboard),
    # it never uploads anything itself, so it needs no access keys, just the
    # public base URL the "sahyog-audio"/"sahyog-images" buckets are served
    # from. See "3.Triage and route/schema_003_media_objects.sql" and the
    # object_storage.py module in the services that DO upload (1, 2, 5, 8).
    S3_PUBLIC_BASE_URL: str = os.getenv("S3_PUBLIC_BASE_URL", "http://localhost:9000")

    # Comma-separated list of origins allowed to call this service from a
    # browser (CORS). Defaults to the local citizen-portal dev server.
    FRONTEND_ORIGINS: str = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")


settings = Settings()
