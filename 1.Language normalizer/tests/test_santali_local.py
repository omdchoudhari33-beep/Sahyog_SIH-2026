from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services import santali_local


def _fake_response(json_body=None, content=b""):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_body or {}
    resp.content = content
    return resp


def test_transcribe_santali_posts_wav_and_parses_result():
    with patch("httpx.post", return_value=_fake_response({"transcript": "ᱡᱚᱦᱟᱨ", "confidence": 0.82})) as mock_post:
        transcript, confidence = santali_local.transcribe_santali(b"fake-wav-bytes")
    assert transcript == "ᱡᱚᱦᱟᱨ"
    assert confidence == 0.82
    assert mock_post.call_args.args[0].endswith("/asr")


def test_transcribe_santali_wraps_network_error():
    with patch("httpx.post", side_effect=httpx.ConnectError("connection refused")):
        with pytest.raises(santali_local.SantaliLocalError):
            santali_local.transcribe_santali(b"fake-wav-bytes")


def test_translate_santali_to_english_sends_correct_language_pair():
    with patch("httpx.post", return_value=_fake_response({"text": "there is a pothole"})) as mock_post:
        result = santali_local.translate_santali_to_english("ᱚᱰᱚᱠ ᱠᱟᱛᱮ")
    assert result == "there is a pothole"
    assert mock_post.call_args.kwargs["json"] == {"text": "ᱚᱰᱚᱠ ᱠᱟᱛᱮ", "source": "sat", "target": "en"}


def test_synthesize_speech_via_local_model_returns_raw_audio_bytes():
    with patch("httpx.post", return_value=_fake_response(content=b"RIFF....WAVEfmt ")):
        audio = santali_local.synthesize_speech_via_local_model("ᱡᱚᱦᱟᱨ")
    assert audio == b"RIFF....WAVEfmt "


def test_synthesize_speech_via_local_model_works_for_urdu_text_too():
    """The underlying model isn't Santali-only - webhook.py's /speak also
    routes Urdu replies through this same function (Bhashini has no Urdu
    TTS, but this model's own language list includes Urdu)."""
    with patch("httpx.post", return_value=_fake_response(content=b"RIFF....WAVEfmt ")) as mock_post:
        audio = santali_local.synthesize_speech_via_local_model("یہ ایک جانچ ہے")
    assert audio == b"RIFF....WAVEfmt "
    assert mock_post.call_args.kwargs["json"] == {"text": "یہ ایک جانچ ہے"}


def test_synthesize_speech_via_local_model_wraps_failure():
    with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
        with pytest.raises(santali_local.SantaliLocalError):
            santali_local.synthesize_speech_via_local_model("ᱡᱚᱦᱟᱨ")
