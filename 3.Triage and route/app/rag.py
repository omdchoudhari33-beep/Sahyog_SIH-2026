"""
"Ask Sahyog" RAG Q&A: retrieve -> augment -> generate.

Retrieval has two legs against the same pgvector setup D2's dedup engine
already relies on (see app/dedup.py):
  1. kb_chunks    - authored how-it-works/FAQ content (app/rag_ingest.py)
  2. active_tickets - live semantic search, so a citizen can ask things like
                      "has anyone else reported this" and get a real answer
Both legs use the same embedding model (app/embedding.py) so a single query
embedding compares directly against both.

Generation reuses the exact Ollama call shape "2.Evidence Extractor/c1_text.py"
already uses (same model, already resident in Ollama) rather than inventing a
new one.
"""
from __future__ import annotations

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.embedding import embed_text

NO_CONTEXT_ANSWER = "I don't have information about that."

SYSTEM_PROMPT = """You are "Ask Sahyog", a help assistant for a civic-issue reporting platform.
Answer the citizen's question using ONLY the context sections below - never invent
facts, SLA dates, or ticket details that aren't present in the context.
If the context doesn't cover the question, reply exactly: "{no_context}"
Keep the answer short (2-4 sentences) and plain, no markdown.""".format(
    no_context=NO_CONTEXT_ANSWER
)


def _vector_literal(vec: list[float]) -> str:
    """pgvector wants a string like '[0.1,0.2,...]' for parameter binding."""
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def _retrieve_kb_chunks(db: Session, query_embedding: list[float]) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT source, title, chunk_text, 1 - (embedding <=> :q) AS similarity
            FROM kb_chunks
            ORDER BY embedding <=> :q
            LIMIT :limit
            """
        ),
        {"q": _vector_literal(query_embedding), "limit": settings.RAG_TOP_K_KB},
    ).fetchall()
    return [
        {"source": r[0], "title": r[1], "chunk_text": r[2], "similarity": round(r[3], 4)}
        for r in rows
    ]


def _retrieve_similar_tickets(db: Session, query_embedding: list[float]) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT id, standardized_problem_statement, domain, status,
                   priority_score, cluster_count,
                   1 - (embedding <=> :q) AS similarity
            FROM active_tickets
            ORDER BY embedding <=> :q
            LIMIT :limit
            """
        ),
        {"q": _vector_literal(query_embedding), "limit": settings.RAG_TOP_K_TICKETS},
    ).fetchall()
    return [
        {
            "ticket_id": r[0],
            "problem_statement": r[1],
            "domain": r[2],
            "status": r[3],
            "priority_score": r[4],
            "cluster_count": r[5],
            "similarity": round(r[6], 4),
        }
        for r in rows
    ]


def _build_prompt(question: str, kb_hits: list[dict], ticket_hits: list[dict]) -> str:
    kb_block = "\n\n".join(f"[{h['title']}]\n{h['chunk_text']}" for h in kb_hits) or "(none)"
    ticket_block = (
        "\n".join(
            f"- Ticket #{h['ticket_id']} ({h['domain'] or 'unknown domain'}): "
            f"\"{h['problem_statement']}\" - status: {h['status']}, "
            f"{h['cluster_count']} report(s) merged into it"
            for h in ticket_hits
        )
        or "(none)"
    )
    return f"""{SYSTEM_PROMPT}

Knowledge base:
{kb_block}

Currently tracked similar reports:
{ticket_block}

Citizen's question: {question}

Answer:"""


def _generate(prompt: str) -> str:
    payload = {
        "model": settings.RAG_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        # Low temperature: this must stay grounded in the retrieved context,
        # not wander into plausible-sounding but unsupported detail.
        "options": {"temperature": 0.2, "num_predict": 400},
        "keep_alive": "30m",
    }
    response = httpx.post(f"{settings.OLLAMA_BASE_URL}/api/generate", json=payload, timeout=90)
    response.raise_for_status()
    result_text = response.json().get("response", "").strip()

    # Defensively strip markdown fences, same as c1_text.py's Ollama call.
    if result_text.startswith("```"):
        result_text = result_text.split("\n", 1)[-1]
    if result_text.endswith("```"):
        result_text = result_text[:-3]
    return result_text.strip()


def answer_question(db: Session, question: str) -> dict:
    query_embedding = embed_text(question)
    kb_hits = _retrieve_kb_chunks(db, query_embedding)
    ticket_hits = _retrieve_similar_tickets(db, query_embedding)

    if not kb_hits and not ticket_hits:
        return {"answer": NO_CONTEXT_ANSWER, "sources": []}

    prompt = _build_prompt(question, kb_hits, ticket_hits)
    answer = _generate(prompt)

    sources = [{"type": "knowledge_base", "title": h["title"], "source": h["source"]} for h in kb_hits]
    sources += [
        {"type": "ticket", "ticket_id": h["ticket_id"], "status": h["status"]} for h in ticket_hits
    ]
    return {"answer": answer, "sources": sources}
