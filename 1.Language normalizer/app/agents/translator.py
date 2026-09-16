from app.services import bhashini


def translate_to_english(text: str, source_language: str | None) -> str:
    if not source_language or source_language.strip().lower() in {"en", "english"}:
        return text

    translated = bhashini.translate(text, source_language, target_language="en")
    return translated if translated is not None else text
