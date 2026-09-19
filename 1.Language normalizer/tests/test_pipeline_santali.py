from pathlib import Path
from unittest.mock import patch

import pytest

from app.media.pipeline import AsrFailedError, transcribe_with_cleanup
from app.services import santali_local


@pytest.fixture
def fake_wav_file(tmp_path):
    path = tmp_path / "input.webm"
    path.write_bytes(b"fake-source-audio")
    return path


def test_transcribe_with_cleanup_routes_santali_to_local_service(fake_wav_file):
    normalized_path = fake_wav_file.parent / "normalized.wav"
    normalized_path.write_bytes(b"RIFF....WAVEfmt ")

    with patch("app.media.pipeline.normalize_audio", return_value=normalized_path):
        with patch.object(santali_local, "transcribe_santali", return_value=("ᱡᱚᱦᱟᱨ", 0.77)) as mock_asr:
            result = transcribe_with_cleanup(fake_wav_file, source_language="sat")

    assert result.transcript == "ᱡᱚᱦᱟᱨ"
    assert result.language == "sat"
    assert result.confidence == 0.77
    mock_asr.assert_called_once_with(b"RIFF....WAVEfmt ")
    assert not normalized_path.exists()  # temp file cleaned up


def test_transcribe_with_cleanup_wraps_santali_service_failure(fake_wav_file):
    normalized_path = fake_wav_file.parent / "normalized.wav"
    normalized_path.write_bytes(b"RIFF....WAVEfmt ")

    with patch("app.media.pipeline.normalize_audio", return_value=normalized_path):
        with patch.object(
            santali_local, "transcribe_santali", side_effect=santali_local.SantaliLocalError("service unreachable")
        ):
            with pytest.raises(AsrFailedError):
                transcribe_with_cleanup(fake_wav_file, source_language="sat")
