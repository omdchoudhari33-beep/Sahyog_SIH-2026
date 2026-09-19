from __future__ import annotations
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

# ==========================================
# 1. ENUMS (Preserving Original Contract Rules)
# ==========================================

class CivicDomain(str, Enum):
    ENERGY_POWER = "ENERGY_POWER"
    ROADS_BRIDGES = "ROADS_BRIDGES"
    WATER_SUPPLY = "WATER_SUPPLY"
    SANITATION_SEWAGE = "SANITATION_SEWAGE"
    WASTE_GARBAGE_COLLECTION = "WASTE_GARBAGE_COLLECTION"
    STREETLIGHTING = "STREETLIGHTING"
    DRAINAGE_WATERLOGGING = "DRAINAGE_WATERLOGGING"
    ILLEGAL_CONSTRUCTION_ENCROACHMENT = "ILLEGAL_CONSTRUCTION_ENCROACHMENT"
    STRAY_ANIMAL_MANAGEMENT = "STRAY_ANIMAL_MANAGEMENT"
    PARKS_PUBLIC_SPACES = "PARKS_PUBLIC_SPACES"
    HEALTHCARE_FACILITY_MAINTENANCE = "HEALTHCARE_FACILITY_MAINTENANCE"
    EDUCATION_FACILITY_MAINTENANCE = "EDUCATION_FACILITY_MAINTENANCE"
    TRAFFIC_SIGNAGE = "TRAFFIC_SIGNAGE"
    CIVIC_DISASTER_EMERGENCY = "CIVIC_DISASTER_EMERGENCY"
    OTHER_MUNICIPAL = "OTHER_MUNICIPAL"
    # Track B (R&D/university-routed) domains - must match
    # "3.Triage and route/app/validation.py"'s TRACK_B_DOMAINS exactly, or a
    # ticket that should route to Track B falls through to the D4
    # review_required fallback instead (these two were missing entirely
    # until this fix, so the AI could never even choose them).
    AGRICULTURAL_DISEASE = "AGRICULTURAL_DISEASE"
    UNKNOWN_STRUCTURAL_FAILURE = "UNKNOWN_STRUCTURAL_FAILURE"
    # Broader societal-challenge domains (education/healthcare/agriculture/
    # water/environment/accessibility/livelihoods/governance) - distinct
    # from the existing municipal-infrastructure domains above, which only
    # cover building upkeep or piped-utility issues, not access/quality/
    # delivery/systemic problems in those same sectors.
    HEALTHCARE_SERVICE_GAP = "HEALTHCARE_SERVICE_GAP"
    EDUCATION_ACCESS_QUALITY = "EDUCATION_ACCESS_QUALITY"
    AGRICULTURE_LIVELIHOOD = "AGRICULTURE_LIVELIHOOD"
    WATER_RESOURCE_MANAGEMENT = "WATER_RESOURCE_MANAGEMENT"
    ACCESSIBILITY_DISABILITY = "ACCESSIBILITY_DISABILITY"
    RURAL_LIVELIHOODS = "RURAL_LIVELIHOODS"
    ENVIRONMENT_POLLUTION = "ENVIRONMENT_POLLUTION"
    PUBLIC_SERVICE_DELIVERY = "PUBLIC_SERVICE_DELIVERY"

class ResearchDomain(str, Enum):
    # Preserved for Track B matching later in the pipeline
    CIVIL_STRUCTURAL_ENGINEERING = "CIVIL_STRUCTURAL_ENGINEERING"
    ENVIRONMENTAL_ENGINEERING = "ENVIRONMENTAL_ENGINEERING"
    ELECTRICAL_POWER_SYSTEMS = "ELECTRICAL_POWER_SYSTEMS"
    GEOTECHNICAL_DISASTER_SCIENCE = "GEOTECHNICAL_DISASTER_SCIENCE"
    WATER_RESOURCE_MANAGEMENT = "WATER_RESOURCE_MANAGEMENT"
    URBAN_PLANNING_GEOSPATIAL = "URBAN_PLANNING_GEOSPATIAL"
    PUBLIC_HEALTH_EPIDEMIOLOGY = "PUBLIC_HEALTH_EPIDEMIOLOGY"
    MATERIALS_SCIENCE = "MATERIALS_SCIENCE"
    AGRICULTURE_RURAL_TECHNOLOGY = "AGRICULTURE_RURAL_TECHNOLOGY"
    COMPUTER_SCIENCE_DATA_SYSTEMS = "COMPUTER_SCIENCE_DATA_SYSTEMS"
    OTHER_RESEARCH = "OTHER_RESEARCH"

class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class Track(str, Enum):
    TRACK_A = "TRACK_A"
    TRACK_B = "TRACK_B"
    UNSURE = "UNSURE"

class GeoOrigin(str, Enum):
    EXIF_IMAGE = "EXIF_IMAGE"
    CLIENT_DEVICE_FALLBACK = "CLIENT_DEVICE_FALLBACK"
    NONE = "NONE"

class ProcessingEngine(str, Enum):
    CLOUD = "CLOUD"
    LOCAL_OLLAMA = "LOCAL_OLLAMA"

# ==========================================
# 2. HYBRID DATA MODELS 
# ==========================================

class StructuredEvidence(BaseModel):
    # Original core fields
    original_text: str
    normalized_english: str
    civic_domain: CivicDomain
    research_domain: Optional[ResearchDomain] = None 
    severity: Severity
    suggested_track: Track
    confidence: float = Field(..., ge=0.0, le=1.0)
    entities: List[str] = Field(default_factory=list)
    language_detected: str
    engine_used: ProcessingEngine = ProcessingEngine.LOCAL_OLLAMA
    
    # NEW Value-Add Fields
    is_actionable: bool = True
    rationale: str = ""

class VisualEvidence(BaseModel):
    # Original core fields
    detected_visual_elements: List[str] = Field(default_factory=list)
    damage_type: Optional[str] = None
    image_matches_report: bool = False
    discrepancy_notes: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    engine_used: ProcessingEngine = ProcessingEngine.LOCAL_OLLAMA
    
    # NEW Value-Add Fields
    image_analyzed: bool = False
    detailed_visual_analysis: str = ""
    correlation_reasoning: str = ""

class Geolocation(BaseModel):
    # Original core fields
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: Optional[str] = None
    origin: GeoOrigin
    
    # NEW Value-Add Fields
    device_make: Optional[str] = None
    device_model: Optional[str] = None
    is_timestamp_valid: bool = False

class MediaRef(BaseModel):
    """Object storage reference for the persisted original photo - see
    storage.py and "3.Triage and route/schema_003_media_objects.sql".
    media_id is None if the media_objects DB registration was skipped
    (DATABASE_URL not configured) or failed; the file itself is still safely
    in object storage whenever this whole object is present."""
    media_id: Optional[int] = None
    bucket: str
    object_key: str
    url: str


class UnifiedEvidencePayload(BaseModel):
    report_id: str
    structured_evidence: StructuredEvidence
    geolocation: Geolocation
    visual_evidence: Optional[VisualEvidence] = None
    requires_human_review: bool = False
    media: Optional[MediaRef] = None

def compute_requires_human_review(
    text_result: StructuredEvidence,
    vision_result: Optional[VisualEvidence],
    geo_result: Geolocation,
    confidence_threshold: float = 0.6,
) -> bool:
    """The gatekeeper function: routes to human if AI is unsure or lacks info."""
    if text_result.confidence < confidence_threshold or not text_result.is_actionable:
        return True
    if text_result.civic_domain == CivicDomain.OTHER_MUNICIPAL:
        return True
    if text_result.suggested_track == Track.UNSURE:
        return True
    if vision_result is not None:
        if vision_result.confidence < confidence_threshold:
            return True
        if not vision_result.image_matches_report:
            return True
    if geo_result.origin == GeoOrigin.NONE:
        return True
    return False