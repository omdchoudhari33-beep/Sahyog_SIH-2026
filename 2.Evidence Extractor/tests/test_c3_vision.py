import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from c3_vision import audit_vision_evidence


def test_audit_vision_evidence_never_leaks_raw_exception_on_ollama_failure(tmp_path):
    """Regression guard: discrepancy_notes is shown directly to the citizen
    (see 4.Orchestrator's conversation_photo) - an Ollama connection failure
    must produce a safe generic message, never the raw exception text."""
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"fake-jpeg-bytes")

    with patch("c3_vision.requests.post", side_effect=requests.exceptions.ConnectionError("WinError 10061 boom")):
        result = audit_vision_evidence(str(image_path), "There is a pothole")

    assert result.image_analyzed is False
    assert result.confidence == 0.0
    assert "10061" not in (result.discrepancy_notes or "")
    assert "boom" not in (result.discrepancy_notes or "")
    assert result.discrepancy_notes


def test_audit_vision_evidence_never_leaks_raw_exception_on_unreadable_image():
    with patch("builtins.open", side_effect=OSError("disk exploded")):
        result = audit_vision_evidence("/nonexistent/path.jpg", "There is a pothole")

    assert result.image_analyzed is False
    assert "disk exploded" not in (result.discrepancy_notes or "")


def test_audit_vision_evidence_parses_a_successful_response(tmp_path):
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"fake-jpeg-bytes")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": (
            '{"detected_visual_elements": ["road", "pothole"], "damage_type": "pothole", '
            '"image_matches_report": true, "discrepancy_notes": null, "confidence": 0.85, '
            '"image_analyzed": true, "detailed_visual_analysis": "A pothole on a road.", '
            '"correlation_reasoning": "matches"}'
        )
    }
    mock_response.raise_for_status = MagicMock()

    with patch("c3_vision.requests.post", return_value=mock_response):
        result = audit_vision_evidence(str(image_path), "There is a pothole")

    assert result.image_matches_report is True
    assert result.confidence == 0.85
