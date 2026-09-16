"""
End-to-end orchestration logic, with the three agent HTTP calls mocked -
these tests verify the wiring/mapping/early-exit logic in app.main, not the
agents themselves (each agent has its own test suite).
"""
from fastapi.testclient import TestClient

import app.main as main


async def _agent1_ok(*args, **kwargs):
    return {
        "request_id": "r1",
        "status": "completed",
        "input_type": "text",
        "english_translation": "There is a large pothole near the school",
        "standardized_text": "There is a large pothole near the school",
    }


async def _agent2_ok(*args, **kwargs):
    return {
        "report_id": "r1",
        "structured_evidence": {
            "normalized_english": "Large pothole near the school entrance",
            "civic_domain": "ROADS_BRIDGES",
            "severity": "HIGH",
            "suggested_track": "TRACK_A",
            "confidence": 0.9,
        },
        "geolocation": {"latitude": 23.3441, "longitude": 85.3096, "origin": "EXIF_IMAGE"},
        "visual_evidence": None,
        "requires_human_review": False,
    }


async def _agent3_ok(ticket):
    return {"action": "created_new", "ticket_id": 42, "cluster_count": 1}


def test_full_pipeline_routes_successfully(monkeypatch):
    monkeypatch.setattr(main, "call_agent1", _agent1_ok)
    monkeypatch.setattr(main, "call_agent2", _agent2_ok)
    monkeypatch.setattr(main, "call_agent3_ingest", _agent3_ok)

    client = TestClient(main.app)
    response = client.post("/submit", data={"text": "raasta mein gaddha hai"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "routed"
    assert body["agent3"]["ticket_id"] == 42
    assert body["agent3"]["action"] == "created_new"


def test_stops_early_when_asr_needs_review(monkeypatch):
    async def agent1_review_required(*args, **kwargs):
        return {"request_id": "r1", "status": "review_required"}

    monkeypatch.setattr(main, "call_agent1", agent1_review_required)

    client = TestClient(main.app)
    response = client.post("/submit", data={"local_audio_path": "some.wav"})

    assert response.status_code == 200
    assert response.json()["status"] == "review_required"
    assert response.json()["stage"] == "language_normalization"


def test_stops_when_no_geo_available(monkeypatch):
    async def agent2_no_geo(*args, **kwargs):
        return {
            "report_id": "r1",
            "structured_evidence": {
                "normalized_english": "text",
                "civic_domain": "ROADS_BRIDGES",
                "severity": "LOW",
                "suggested_track": "TRACK_A",
                "confidence": 0.9,
            },
            "geolocation": {"latitude": None, "longitude": None, "origin": "NONE"},
            "requires_human_review": True,
        }

    monkeypatch.setattr(main, "call_agent1", _agent1_ok)
    monkeypatch.setattr(main, "call_agent2", agent2_no_geo)

    client = TestClient(main.app)
    response = client.post("/submit", data={"text": "some report"})

    assert response.status_code == 200
    assert response.json()["status"] == "geo_required"


def test_requires_text_or_audio():
    client = TestClient(main.app)
    response = client.post("/submit", data={})
    assert response.status_code == 422
