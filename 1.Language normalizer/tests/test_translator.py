from app.agents.translator import translate_to_english
from app.services import bhashini


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
