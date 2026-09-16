import json
import requests
from pydantic import ValidationError
from schemas import StructuredEvidence, CivicDomain, Severity, Track, ProcessingEngine

def extract_text_evidence(raw_text: str) -> StructuredEvidence:
    """Processes text locally via Ollama into the hybrid schema[cite: 1]."""
    url = "http://localhost:11434/api/generate"
    
    prompt = f"""
    Analyze the following citizen report and extract the details into a strict JSON format.
    Report: "{raw_text}"

    Rules:
    1. normalized_english: A FAITHFUL, LITERAL English translation of the report.
       - Preserve every concrete detail exactly as stated: the type of problem,
         the objects/infrastructure involved, the location, and any numbers,
         durations, or descriptions.
       - Only fix grammar and translate to English. Do NOT summarize loosely,
         paraphrase creatively, add details that were not stated, or drop
         details that were stated.
       - Never substitute a different object or problem type than what was
         reported (e.g. if the report says "pothole", the output must say
         "pothole" - not "tree", "crack", or any other word - even if a
         source-language word is ambiguous or unfamiliar to you).
       - If you are not confident in part of the translation, translate that
         part as literally as possible rather than guessing a related concept.
    2. civic_domain: Assign one exact category: ENERGY_POWER, ROADS_BRIDGES, WATER_SUPPLY, SANITATION_SEWAGE, WASTE_GARBAGE_COLLECTION, STREETLIGHTING, DRAINAGE_WATERLOGGING, ILLEGAL_CONSTRUCTION_ENCROACHMENT, STRAY_ANIMAL_MANAGEMENT, PARKS_PUBLIC_SPACES, HEALTHCARE_FACILITY_MAINTENANCE, EDUCATION_FACILITY_MAINTENANCE, TRAFFIC_SIGNAGE, CIVIC_DISASTER_EMERGENCY, OTHER_MUNICIPAL.
    3. severity: LOW, MEDIUM, HIGH, or CRITICAL.
    4. suggested_track: TRACK_A, TRACK_B, or UNSURE.
    5. entities: List of locations or objects mentioned.
    6. language_detected: e.g., "Hindi", "English".
    7. confidence: float between 0.0 and 1.0.
    8. is_actionable: true or false.
    9. rationale: A short sentence explaining the score and track.

    Return ONLY JSON:
    {{
      "normalized_english": "...",
      "civic_domain": "...",
      "severity": "...",
      "suggested_track": "...",
      "entities": ["..."],
      "language_detected": "...",
      "confidence": 0.0,
      "is_actionable": true,
      "rationale": "..."
    }}
    """

    payload = {
        "model": "llama3.2:3b",
        "prompt": prompt,
        "stream": False,
        "format": "json",
        # Low temperature: this is factual extraction/translation, not
        # creative writing - keep it as deterministic and literal as possible
        # to reduce the model quietly swapping in a different word/object.
        "options": {"temperature": 0.1, "num_predict": 500},
        # Keep resident so the C3 vision call moments later doesn't force
        # Ollama to evict this model and then reload it on the next report.
        "keep_alive": "30m",
    }

    try:
        response = requests.post(url, json=payload, timeout=90)
        response.raise_for_status()
        result_text = response.json().get("response", "").strip()
        
        # Defensively strip markdown[cite: 1]
        if result_text.startswith("```json"): result_text = result_text[7:]
        if result_text.startswith("```"): result_text = result_text[3:]
        if result_text.endswith("```"): result_text = result_text[:-3]
            
        data = json.loads(result_text.strip())
        
        return StructuredEvidence(
            original_text=raw_text,
            normalized_english=data.get("normalized_english", raw_text),
            civic_domain=data.get("civic_domain", "OTHER_MUNICIPAL"),
            severity=data.get("severity", "LOW"),
            suggested_track=data.get("suggested_track", "UNSURE"),
            confidence=float(data.get("confidence", 0.5)),
            entities=data.get("entities", []),
            language_detected=data.get("language_detected", "unknown"),
            is_actionable=bool(data.get("is_actionable", True)),
            rationale=data.get("rationale", "Processed successfully."),
            engine_used=ProcessingEngine.LOCAL_OLLAMA
        )
        
    except Exception as e:
        print(f"C1 Model Failure: {e}")
        return StructuredEvidence(
            original_text=raw_text,
            normalized_english="Failed to process text.",
            civic_domain=CivicDomain.OTHER_MUNICIPAL,
            severity=Severity.LOW,
            suggested_track=Track.UNSURE,
            confidence=0.0,
            language_detected="unknown",
            is_actionable=False,
            rationale=f"System error: {e}",
            engine_used=ProcessingEngine.LOCAL_OLLAMA
        )