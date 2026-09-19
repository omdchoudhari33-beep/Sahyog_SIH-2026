import logging

from app.services import bhashini

logger = logging.getLogger(__name__)


def translate_to_english(text: str, source_language: str | None) -> str:
    if not source_language or source_language.strip().lower() in {"en", "english"}:
        return text

    if bhashini.resolve_language_code(source_language) == "sat":
        # Bhashini has no Santali model at all - use the self-hosted
        # fallback instead (see app/services/santali_local.py). Falls back
        # to the original untranslated text (not silently to "en") on any
        # failure, same contract as bhashini.translate()'s None case below.
        from app.services import santali_local

        try:
            return santali_local.translate_santali_to_english(text)
        except santali_local.SantaliLocalError:
            logger.warning("Santali local translation failed, keeping original text", exc_info=True)
            return text

    translated = bhashini.translate(text, source_language, target_language="en")
    return translated if translated is not None else text
