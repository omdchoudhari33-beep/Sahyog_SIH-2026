"""Same free, self-hosted embedding setup as 3.Triage and route's D2 pass -
loaded once per process, reused for every call. Only used here to embed HEI
*capability* descriptions at onboarding time (admin-only, not hot-path) -
ticket embeddings are read directly from active_tickets.embedding, already
computed by Agent3, never re-embedded here.
"""
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def get_embedding_model() -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.EMBEDDING_MODEL_NAME)


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)  # cosine-ready
    return vector.tolist()
