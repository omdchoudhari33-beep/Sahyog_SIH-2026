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

class UnifiedEvidencePayload(BaseModel):
    report_id: str
    structured_evidence: StructuredEvidence
    geolocation: Geolocation
    visual_evidence: Optional[VisualEvidence] = None
    requires_human_review: bool = False

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