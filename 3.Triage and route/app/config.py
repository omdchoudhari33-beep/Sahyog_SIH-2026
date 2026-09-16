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


settings = Settings()
