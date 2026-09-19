import json
import requests
from pydantic import ValidationError
from config import settings
from schemas import StructuredEvidence, CivicDomain, Severity, Track, ProcessingEngine


def _coerce_enum(enum_cls, value, default):
    """Best-effort match of a small local model's raw string output onto
    enum_cls: exact match first, then substring containment either way
    (handles "STRUCTURAL_FAILURE" -> UNKNOWN_STRUCTURAL_FAILURE), else the
    given default - never raises, so one bad field can't take down the
    whole classification (see extract_text_evidence)."""
    if not value:
        return default
    normalized = str(value).strip().upper()
    try:
        return enum_cls(normalized)
    except ValueError:
        pass
    for member in enum_cls:
        if normalized in member.value or member.value in normalized:
            return member
    return default


def extract_text_evidence(raw_text: str) -> StructuredEvidence:
    """Processes text locally via Ollama into the hybrid schema[cite: 1]."""
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    
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
    2. civic_domain: Assign one exact category:
       ENERGY_POWER, ROADS_BRIDGES, WATER_SUPPLY, SANITATION_SEWAGE, WASTE_GARBAGE_COLLECTION,
       STREETLIGHTING, DRAINAGE_WATERLOGGING, ILLEGAL_CONSTRUCTION_ENCROACHMENT,
       STRAY_ANIMAL_MANAGEMENT, PARKS_PUBLIC_SPACES, HEALTHCARE_FACILITY_MAINTENANCE,
       EDUCATION_FACILITY_MAINTENANCE, TRAFFIC_SIGNAGE, CIVIC_DISASTER_EMERGENCY,
       AGRICULTURAL_DISEASE, UNKNOWN_STRUCTURAL_FAILURE,
       HEALTHCARE_SERVICE_GAP, EDUCATION_ACCESS_QUALITY, AGRICULTURE_LIVELIHOOD,
       WATER_RESOURCE_MANAGEMENT, ACCESSIBILITY_DISABILITY, RURAL_LIVELIHOODS,
       ENVIRONMENT_POLLUTION, PUBLIC_SERVICE_DELIVERY, OTHER_MUNICIPAL.
       - HEALTHCARE_FACILITY_MAINTENANCE is building/equipment upkeep at a
         health facility; HEALTHCARE_SERVICE_GAP is access/staffing/medicine
         shortage/quality of care instead.
       - EDUCATION_FACILITY_MAINTENANCE is building upkeep at a school;
         EDUCATION_ACCESS_QUALITY is dropout, teacher shortage, or learning
         quality instead.
       - AGRICULTURAL_DISEASE is specifically a crop/livestock disease
         outbreak; AGRICULTURE_LIVELIHOOD is irrigation access, market
         linkage, pricing, or farm-input issues instead.
       - WATER_SUPPLY is a municipal piped-water problem;
         WATER_RESOURCE_MANAGEMENT is groundwater, watershed, or irrigation
         infrastructure instead.
       - ACCESSIBILITY_DISABILITY: physical or digital access barriers for
         persons with disabilities (e.g. a missing ramp, no accessible
         signage).
       - RURAL_LIVELIHOODS: rural employment/income-scheme access issues
         (e.g. a government job/income scheme not reaching eligible people).
       - ENVIRONMENT_POLLUTION: river/air pollution, deforestation - beyond
         routine waste collection or drainage.
       - PUBLIC_SERVICE_DELIVERY: governance/welfare-scheme/documentation
         delivery failures that don't fit any physical-infrastructure domain.
    3. severity: LOW, MEDIUM, HIGH, or CRITICAL.
    4. suggested_track: TRACK_A, TRACK_B, or UNSURE.
       - TRACK_A: a routine issue with a known cause and a standard fix by
         the relevant department (potholes, streetlights, garbage
         collection, water/sewage leaks, broken signage, a missing
         wheelchair ramp, etc.) - the responsible body just needs to act on
         it, no investigation required.
       - TRACK_B: the cause is NOT obvious/known, or the fix needs
         research/investigation before any action can be taken - e.g. a
         structural crack with an unexplained cause
         (UNKNOWN_STRUCTURAL_FAILURE), an unfamiliar crop/livestock disease
         outbreak (AGRICULTURAL_DISEASE), repeated unexplained crop failures
         or irrigation planning (AGRICULTURE_LIVELIHOOD /
         WATER_RESOURCE_MANAGEMENT), a pollution source that needs
         identifying (ENVIRONMENT_POLLUTION), a livelihood scheme that
         needs redesigning, not just re-issuing (RURAL_LIVELIHOODS), or
         illegal construction/encroachment needing investigation - these
         need a university or research institution, not a routine repair
         or clerical fix.
       - UNSURE: you genuinely cannot tell from the report which applies.
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

        # A small local model occasionally returns a near-miss enum value
        # (e.g. "STRUCTURAL_FAILURE" instead of "UNKNOWN_STRUCTURAL_FAILURE").
        # That must only cost us that ONE field's precision, not the whole
        # classification - suggested_track in particular (TRACK_A/TRACK_B) is
        # exactly the field the D4 human gate relies on, and a bad
        # civic_domain string must never take it down too.
        civic_domain = _coerce_enum(CivicDomain, data.get("civic_domain"), CivicDomain.OTHER_MUNICIPAL)
        severity = _coerce_enum(Severity, data.get("severity"), Severity.LOW)
        suggested_track = _coerce_enum(Track, data.get("suggested_track"), Track.UNSURE)

        return StructuredEvidence(
            original_text=raw_text,
            normalized_english=data.get("normalized_english", raw_text),
            civic_domain=civic_domain,
            severity=severity,
            suggested_track=suggested_track,
            confidence=float(data.get("confidence", 0.5)),
            entities=data.get("entities", []),
            language_detected=data.get("language_detected", "unknown"),
            is_actionable=bool(data.get("is_actionable", True)),
            rationale=data.get("rationale", "Processed successfully."),
            engine_used=ProcessingEngine.LOCAL_OLLAMA
        )
        
    except Exception as e:
        print(f"C1 Model Failure: {e}")
        # Never fabricate content or leak the raw exception into a field a
        # citizen/operator can see - fall back to the citizen's own raw text
        # (already real, already available) instead of a placeholder string,
        # and force human review via confidence=0.0/is_actionable=False/
        # suggested_track=UNSURE (see compute_requires_human_review).
        return StructuredEvidence(
            original_text=raw_text,
            normalized_english=raw_text,
            civic_domain=CivicDomain.OTHER_MUNICIPAL,
            severity=Severity.LOW,
            suggested_track=Track.UNSURE,
            confidence=0.0,
            language_detected="unknown",
            is_actionable=False,
            rationale="Automatic classification is temporarily unavailable - flagged for human review.",
            engine_used=ProcessingEngine.LOCAL_OLLAMA
        )