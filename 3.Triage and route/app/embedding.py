"""
Free, self-hosted embedding model for the D2 semantic pass.

Loaded once at process startup and reused for every request -
no external API calls, no per-call cost.
"""
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def get_embedding_model() -> "SentenceTransformer":
    # Downloads once from HuggingFace hub, then cached locally.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.EMBEDDING_MODEL_NAME)


def embed_text(text: str) -> list[float]:
    """
    Embed a single standardized_problem_statement.
    Returns a plain python list so it can be stored directly
    in the pgvector column.
    """
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)  # cosine-ready
    return vector.tolist()
