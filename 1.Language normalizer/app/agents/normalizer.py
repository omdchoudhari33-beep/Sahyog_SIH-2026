def normalize_text(text: str, source_language: str | None) -> str:
    # MVP: preserve text and normalize whitespace.
    # Replace this with a dialect model/API in the next phase.
    return " ".join(text.split())
