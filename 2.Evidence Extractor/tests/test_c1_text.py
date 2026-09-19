import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from c1_text import _coerce_enum, extract_text_evidence
from schemas import CivicDomain, Severity, Track


def test_extract_text_evidence_falls_back_to_raw_text_on_ollama_failure():
    """Regression guard: an Ollama connection failure must never fabricate
    placeholder content or leak the raw exception - the citizen's own raw
    text is the safe fallback, and the result must be flagged for human
    review (confidence=0.0, is_actionable=False, suggested_track=UNSURE)."""
    with patch("c1_text.requests.post", side_effect=requests.exceptions.ConnectionError("boom")):
        result = extract_text_evidence("Sadak mein bada gaddha hai")

    assert result.normalized_english == "Sadak mein bada gaddha hai"
    assert result.original_text == "Sadak mein bada gaddha hai"
    assert result.confidence == 0.0
    assert result.is_actionable is False
    assert result.suggested_track == Track.UNSURE
    assert result.civic_domain == CivicDomain.OTHER_MUNICIPAL
    assert "boom" not in result.rationale  # no raw exception text leaked


def test_extract_text_evidence_parses_a_successful_response():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": (
            '{"normalized_english": "There is a pothole", "civic_domain": "ROADS_BRIDGES", '
            '"severity": "HIGH", "suggested_track": "TRACK_A", "entities": ["road"], '
            '"language_detected": "English", "confidence": 0.9, "is_actionable": true, '
            '"rationale": "clear pothole report"}'
        )
    }
    mock_response.raise_for_status = MagicMock()

    with patch("c1_text.requests.post", return_value=mock_response):
        result = extract_text_evidence("There is a pothole")

    assert result.civic_domain == CivicDomain.ROADS_BRIDGES
    assert result.suggested_track == Track.TRACK_A
    assert result.confidence == 0.9


def test_near_miss_domain_from_model_does_not_discard_the_whole_classification():
    """Regression guard for a real bug hit during live testing: the model
    returned civic_domain="STRUCTURAL_FAILURE" (not an exact enum match),
    which used to raise a pydantic ValidationError and fall all the way
    back to the generic-failure path - discarding a correct suggested_track
    along with it. Now it should just coerce the near-miss domain and keep
    everything else the model actually got right."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": (
            '{"normalized_english": "Unexplained wall crack", "civic_domain": "STRUCTURAL_FAILURE", '
            '"severity": "CRITICAL", "suggested_track": "TRACK_B", "entities": [], '
            '"language_detected": "English", "confidence": 0.7, "is_actionable": true, '
            '"rationale": "unexplained structural issue"}'
        )
    }
    mock_response.raise_for_status = MagicMock()

    with patch("c1_text.requests.post", return_value=mock_response):
        result = extract_text_evidence("Unexplained wall crack")

    assert result.civic_domain == CivicDomain.UNKNOWN_STRUCTURAL_FAILURE
    assert result.suggested_track == Track.TRACK_B
    assert result.confidence == 0.7


def test_coerce_enum_exact_match():
    assert _coerce_enum(Track, "TRACK_B", Track.UNSURE) == Track.TRACK_B


def test_coerce_enum_near_miss_substring_match():
    assert _coerce_enum(CivicDomain, "STRUCTURAL_FAILURE", CivicDomain.OTHER_MUNICIPAL) == CivicDomain.UNKNOWN_STRUCTURAL_FAILURE


def test_coerce_enum_falls_back_to_default_when_unrecognizable():
    assert _coerce_enum(Severity, "BANANA", Severity.LOW) == Severity.LOW


def test_coerce_enum_falls_back_to_default_when_missing():
    assert _coerce_enum(Severity, None, Severity.LOW) == Severity.LOW


def test_civic_domain_enum_includes_both_track_b_only_domains():
    """AGRICULTURAL_DISEASE and UNKNOWN_STRUCTURAL_FAILURE must exist here -
    they're two of the three domains "3.Triage and route/app/validation.py"'s
    TRACK_B_DOMAINS routes to Track B on. Without them the AI could never
    even choose to classify a ticket into those domains."""
    assert CivicDomain.AGRICULTURAL_DISEASE == "AGRICULTURAL_DISEASE"
    assert CivicDomain.UNKNOWN_STRUCTURAL_FAILURE == "UNKNOWN_STRUCTURAL_FAILURE"


def test_civic_domain_enum_includes_broader_societal_domains():
    """These eight must exist so the AI can classify a report as anything
    beyond municipal infrastructure (education/healthcare/agriculture/
    water/environment/accessibility/livelihoods/governance) - see
    "3.Triage and route/app/validation.py"'s TRACK_A_DOMAINS/TRACK_B_DOMAINS
    for which of these route where."""
    for domain in (
        "HEALTHCARE_SERVICE_GAP", "EDUCATION_ACCESS_QUALITY", "AGRICULTURE_LIVELIHOOD",
        "WATER_RESOURCE_MANAGEMENT", "ACCESSIBILITY_DISABILITY", "RURAL_LIVELIHOODS",
        "ENVIRONMENT_POLLUTION", "PUBLIC_SERVICE_DELIVERY",
    ):
        assert CivicDomain(domain) == domain


def test_near_miss_broader_domain_is_coerced_correctly():
    assert _coerce_enum(CivicDomain, "ACCESSIBILITY", CivicDomain.OTHER_MUNICIPAL) == CivicDomain.ACCESSIBILITY_DISABILITY
