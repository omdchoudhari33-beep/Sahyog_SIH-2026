from unittest.mock import patch

from app.agents.translator import translate_to_english
from app.services import bhashini, santali_local


def test_passthrough_when_already_english():
    assert translate_to_english("hello world", "en") == "hello world"
    assert translate_to_english("hello world", None) == "hello world"


def test_falls_back_to_original_text_for_romanized_input():
    # Bhashini expects native-script text (e.g. Devanagari for Hindi), not
    # romanized transliteration - it returns the input unchanged rather
    # than translating it, and translate_to_english() must not crash on
    # that (whether or not real credentials are configured).
    result = translate_to_english("kal barish hogi", "hi")
    assert result == "kal barish hogi"


def test_translate_returns_none_on_missing_credentials(monkeypatch):
    monkeypatch.setattr(bhashini.settings, "bhashini_user_id", "")
    monkeypatch.setattr(bhashini.settings, "bhashini_ulca_api_key", "")
    assert bhashini.translate("some text", "hi") is None


def test_is_language_supported_true_for_bhashini_languages():
    for lang in ("hi", "bn", "or", "ne", "mai", "ur", "en", "Hindi", "Bengali"):
        assert bhashini.is_language_supported(lang) is True


def test_is_language_supported_false_for_santali():
    """Santali has no Bhashini model at all - is_language_supported() is
    what lets webhook.py route it to human review instead of silently
    mislabeling untranslated script as English (see its docstring)."""
    assert bhashini.is_language_supported("sat") is False
    assert bhashini.is_language_supported("santali") is False


def test_is_language_supported_true_when_no_language_given():
    """None means "no language specified" - treated as English/passthrough,
    not as an unsupported-language rejection."""
    assert bhashini.is_language_supported(None) is True


def test_translate_to_english_routes_santali_to_local_service():
    """Bhashini has no Santali model, but translate_to_english() must still
    attempt a real translation via the self-hosted fallback - not give up
    and return the untranslated text outright (that's webhook.py's
    review_required path's job when even the local service fails)."""
    with patch.object(santali_local, "translate_santali_to_english", return_value="hello there") as mock_translate:
        assert translate_to_english("ᱡᱚᱦᱟᱨ", "sat") == "hello there"
    mock_translate.assert_called_once_with("ᱡᱚᱦᱟᱨ")


def test_translate_to_english_falls_back_to_original_text_when_santali_service_down():
    with patch.object(
        santali_local, "translate_santali_to_english", side_effect=santali_local.SantaliLocalError("unreachable")
    ):
        assert translate_to_english("ᱡᱚᱦᱟᱨ", "sat") == "ᱡᱚᱦᱟᱨ"
