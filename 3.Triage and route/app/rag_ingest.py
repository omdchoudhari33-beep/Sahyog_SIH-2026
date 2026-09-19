"""Embeds knowledge_base/*.md into kb_chunks for the "Ask Sahyog" RAG
endpoint (see app/rag.py).

Run manually (same "not auto-run at startup" convention as every schema
migration/seed script in this repo):
    python -m app.rag_ingest

Idempotent: re-running replaces all chunks for a given source file, so
editing a knowledge_base/*.md file and re-running keeps kb_chunks in sync
with it rather than accumulating stale duplicates.
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import delete

from app.db import SessionLocal, KbChunk
from app.embedding import embed_text

logger = logging.getLogger("rag_ingest")

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"

# Small enough that each chunk stays topically focused for retrieval, large
# enough that a chunk isn't just one throwaway sentence with no context.
MIN_CHUNK_CHARS = 200
MAX_CHUNK_CHARS = 1200


def _chunk_markdown(text: str) -> list[tuple[str, str]]:
    """Splits a markdown file into (title, chunk_text) pairs, one chunk per
    '## '-level section (falling back to the '# ' title for content before
    the first '## '), merging short paragraphs up to MAX_CHUNK_CHARS."""
    lines = text.splitlines()
    doc_title = "Untitled"
    sections: list[tuple[str, list[str]]] = []
    current_title = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("# "):
            doc_title = line[2:].strip()
        elif line.startswith("## "):
            if current_lines:
                sections.append((current_title or doc_title, current_lines))
            current_title = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_title or doc_title, current_lines))

    chunks: list[tuple[str, str]] = []
    for title, section_lines in sections:
        paragraphs = [p.strip() for p in "\n".join(section_lines).split("\n\n") if p.strip()]
        buffer = ""
        for para in paragraphs:
            candidate = f"{buffer}\n\n{para}".strip() if buffer else para
            if len(candidate) > MAX_CHUNK_CHARS and buffer:
                chunks.append((title, buffer))
                buffer = para
            else:
                buffer = candidate
        if buffer and len(buffer) >= MIN_CHUNK_CHARS:
            chunks.append((title, buffer))
        elif buffer:
            # Too short to stand alone - still worth keeping, short KB
            # sections (e.g. a one-line "Who decides" note) are common here.
            chunks.append((title, buffer))
    return chunks


def ingest_file(db, path: Path) -> int:
    source = path.name
    text = path.read_text(encoding="utf-8")
    chunks = _chunk_markdown(text)

    db.execute(delete(KbChunk).where(KbChunk.source == source))
    for title, chunk_text in chunks:
        db.add(
            KbChunk(
                source=source,
                title=title,
                chunk_text=chunk_text,
                embedding=embed_text(chunk_text),
            )
        )
    db.commit()
    return len(chunks)


def main() -> None:
    if not KB_DIR.is_dir():
        raise SystemExit(f"No knowledge_base/ directory found at {KB_DIR}")

    db = SessionLocal()
    try:
        total = 0
        for path in sorted(KB_DIR.glob("*.md")):
            count = ingest_file(db, path)
            logger.info("Ingested %s: %d chunk(s)", path.name, count)
            total += count
        logger.info("Done: %d chunk(s) across knowledge_base/*.md", total)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
