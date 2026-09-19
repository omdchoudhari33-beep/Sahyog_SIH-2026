"""Seeds real Jharkhand higher-education institutions into hei_registry /
hei_capabilities, so Track B has an actual state-wide pool to match/broadcast
against instead of the single throwaway SEED_DEMO_DATA row.

Run manually (same "not auto-run at startup" convention as every schema
migration in this repo):
    python -m app.seed_jharkhand_heis

Idempotent: matches on institution_name, skips any institution already
present, safe to re-run after adding new entries below.

Institution names, home districts, and general fields of established
academic strength are public, well-documented facts (these are Jharkhand's
major central/state/deemed universities and NITs/IITs). Contact emails are
NOT real registrar addresses - I have no way to verify those - they are
clearly-marked placeholders (`trackb-onboarding@<slug>.example-pending.ac.in`)
that MUST be replaced with verified contacts before any real email is sent
(EMAIL_DRY_RUN should stay true until then). Capability descriptions are
reasonable characterizations of each institution's relevant department, not
verbatim quotes from any department charter.
"""
from __future__ import annotations

import logging
import secrets

from app.auth import hash_password
from app.db import HeiCapability, HeiRegistry, SessionLocal
from app.embedding import embed_text

logger = logging.getLogger("trackb_seed")

# domain -> matches app/onboarding.py's upper-casing convention. The three
# domains 3.Triage and route's TRACK_B_DOMAINS actually routes on
# (AGRICULTURAL_DISEASE, UNKNOWN_STRUCTURAL_FAILURE,
# ILLEGAL_CONSTRUCTION_ENCROACHMENT) plus adjacent R&D domains this pool of
# institutions realistically covers - the domain tag is informational/display
# only, matching itself runs on capability-description embeddings.
JHARKHAND_HEIS: list[dict] = [
    {
        "institution_name": "Birla Institute of Technology, Mesra",
        "district": "Ranchi",
        "incubator_name": "BIT Mesra Innovation and Incubation Centre",
        "capacity_active_projects": 5,
        "capabilities": [
            ("UNKNOWN_STRUCTURAL_FAILURE", "Civil Engineering",
             "Structural health assessment and failure-cause diagnostics for buildings, "
             "bridges, and retaining structures - cracking, settlement, and collapse investigation."),
        ],
    },
    {
        "institution_name": "Indian Institute of Technology (Indian School of Mines), Dhanbad",
        "district": "Dhanbad",
        "incubator_name": "IIT-ISM Dhanbad Technology Business Incubator",
        "capacity_active_projects": 5,
        "capabilities": [
            ("UNKNOWN_STRUCTURAL_FAILURE", "Mining Engineering / Geotechnical Engineering",
             "Ground subsidence, rock/soil instability, and mine-affected structural failure "
             "investigation - geotechnical root-cause analysis for cracked or sinking structures."),
        ],
    },
    {
        "institution_name": "National Institute of Technology, Jamshedpur",
        "district": "East Singhbhum",
        "incubator_name": "NIT Jamshedpur Technology Incubation Centre",
        "capacity_active_projects": 4,
        "capabilities": [
            ("UNKNOWN_STRUCTURAL_FAILURE", "Civil Engineering",
             "Urban infrastructure structural assessment - roads, bridges, and municipal "
             "building failure diagnostics, materials testing."),
        ],
    },
    {
        "institution_name": "Birsa Agricultural University, Ranchi",
        "district": "Ranchi",
        "incubator_name": None,
        "capacity_active_projects": 4,
        "capabilities": [
            ("AGRICULTURAL_DISEASE", "Plant Pathology & Entomology",
             "Crop disease and pest outbreak diagnosis, plant pathology field investigation, "
             "and agricultural extension for Jharkhand's staple and cash crops."),
        ],
    },
    {
        "institution_name": "Central University of Jharkhand",
        "district": "Ranchi",
        "incubator_name": None,
        "capacity_active_projects": 3,
        "capabilities": [
            ("ILLEGAL_CONSTRUCTION_ENCROACHMENT", "Environmental Science / Urban & Regional Planning",
             "GIS-based land-use mapping and encroachment detection, environmental impact "
             "assessment for unauthorized construction on public/forest land."),
        ],
    },
    {
        "institution_name": "Jharkhand University of Technology, Ranchi",
        "district": "Ranchi",
        "incubator_name": None,
        "capacity_active_projects": 3,
        "capabilities": [
            ("UNKNOWN_STRUCTURAL_FAILURE", "Civil Engineering",
             "Applied civil engineering R&D for municipal infrastructure - drainage, roads, "
             "and small-structure failure assessment."),
        ],
    },
    {
        "institution_name": "Vinoba Bhave University, Hazaribagh",
        "district": "Hazaribagh",
        "incubator_name": None,
        "capacity_active_projects": 3,
        "capabilities": [
            ("AGRICULTURAL_DISEASE", "Botany / Agricultural Sciences",
             "Regional crop disease surveillance and soil science research for the "
             "Hazaribagh plateau agrarian belt."),
        ],
    },
    {
        "institution_name": "Sido Kanhu Murmu University, Dumka",
        "district": "Dumka",
        "incubator_name": None,
        "capacity_active_projects": 3,
        "capabilities": [
            ("AGRICULTURAL_DISEASE", "Agricultural Sciences / Rural Development",
             "Crop disease and rural agrarian distress investigation for the Santhal "
             "Pargana region, tribal-belt farming practices."),
        ],
    },
    {
        "institution_name": "Nilamber Pitamber University, Palamu",
        "district": "Palamu",
        "incubator_name": None,
        "capacity_active_projects": 3,
        "capabilities": [
            ("AGRICULTURAL_DISEASE", "Agricultural Sciences",
             "Drought-prone agriculture and crop disease investigation for the Palamu "
             "plateau region."),
        ],
    },
    {
        "institution_name": "Kolhan University, Chaibasa",
        "district": "West Singhbhum",
        "incubator_name": None,
        "capacity_active_projects": 3,
        "capabilities": [
            ("UNKNOWN_STRUCTURAL_FAILURE", "Civil Engineering / Geology",
             "Mining-belt structural and ground-stability investigation for the Chaibasa "
             "iron-ore region."),
        ],
    },
    {
        "institution_name": "St. Xavier's College, Ranchi",
        "district": "Ranchi",
        "incubator_name": None,
        "capacity_active_projects": 2,
        "capabilities": [
            ("AGRICULTURAL_DISEASE", "Botany / Environmental Science",
             "Botanical and environmental field research relevant to crop disease and "
             "ecological assessment."),
        ],
    },
    {
        "institution_name": "Xavier Institute of Social Service (XISS), Ranchi",
        "district": "Ranchi",
        "incubator_name": None,
        "capacity_active_projects": 2,
        "capabilities": [
            ("ILLEGAL_CONSTRUCTION_ENCROACHMENT", "Urban & Rural Development Policy",
             "Land-use policy research, urban planning, and encroachment/rehabilitation "
             "case studies for Jharkhand's municipalities."),
        ],
    },
    {
        "institution_name": "Ranchi University",
        "district": "Ranchi",
        "incubator_name": None,
        "capacity_active_projects": 3,
        "capabilities": [
            ("UNKNOWN_STRUCTURAL_FAILURE", "Civil Engineering / Geology",
             "General structural and geological field investigation across affiliated "
             "engineering and science departments."),
        ],
    },
    {
        "institution_name": "Dr. Shyama Prasad Mukherjee University, Ranchi",
        "district": "Ranchi",
        "incubator_name": None,
        "capacity_active_projects": 2,
        "capabilities": [
            ("AGRICULTURAL_DISEASE", "Botany",
             "Plant science and crop health research for the Ranchi urban-agricultural "
             "interface."),
        ],
    },
    {
        "institution_name": "Government Polytechnic, Ranchi",
        "district": "Ranchi",
        "incubator_name": None,
        "capacity_active_projects": 2,
        "capabilities": [
            ("UNKNOWN_STRUCTURAL_FAILURE", "Civil Engineering (Diploma)",
             "Applied structural assessment of municipal buildings and small bridges, "
             "field-testing focused."),
        ],
    },
    {
        "institution_name": "Government Polytechnic, Dhanbad",
        "district": "Dhanbad",
        "incubator_name": None,
        "capacity_active_projects": 2,
        "capabilities": [
            ("UNKNOWN_STRUCTURAL_FAILURE", "Mining & Civil Engineering (Diploma)",
             "Coal-belt ground subsidence and structural damage field assessment."),
        ],
    },
    {
        "institution_name": "Government Polytechnic, Bokaro",
        "district": "Bokaro",
        "incubator_name": None,
        "capacity_active_projects": 2,
        "capabilities": [
            ("UNKNOWN_STRUCTURAL_FAILURE", "Civil Engineering (Diploma)",
             "Industrial-belt structural assessment - steel-town municipal infrastructure "
             "and housing failure diagnostics."),
        ],
    },
]


def _placeholder_email(institution_name: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in institution_name).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"trackb-onboarding@{slug}.example-pending.ac.in"


def seed_jharkhand_heis() -> dict:
    db = SessionLocal()
    inserted_institutions = 0
    inserted_capabilities = 0
    skipped = 0
    try:
        for entry in JHARKHAND_HEIS:
            existing = db.query(HeiRegistry).filter(HeiRegistry.institution_name == entry["institution_name"]).one_or_none()
            if existing is not None:
                skipped += 1
                continue

            hei = HeiRegistry(
                institution_name=entry["institution_name"],
                state="Jharkhand",
                district=entry["district"],
                contact_email=_placeholder_email(entry["institution_name"]),
                contact_phone=None,
                incubator_name=entry.get("incubator_name"),
                capacity_active_projects=entry["capacity_active_projects"],
                active=True,
                password_hash=hash_password(secrets.token_urlsafe(9)),
            )
            db.add(hei)
            db.flush()
            inserted_institutions += 1

            for domain, department_name, description in entry["capabilities"]:
                db.add(
                    HeiCapability(
                        hei_id=hei.id, domain=domain, department_name=department_name,
                        description=description, embedding=embed_text(description), active=True,
                    )
                )
                inserted_capabilities += 1

        db.commit()
    finally:
        db.close()

    return {
        "institutions_inserted": inserted_institutions,
        "capabilities_inserted": inserted_capabilities,
        "institutions_skipped_already_present": skipped,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = seed_jharkhand_heis()
    logger.info(
        "Seeded %s institutions (%s capabilities), skipped %s already present. "
        "Contact emails are PLACEHOLDERS - verify real ones before disabling EMAIL_DRY_RUN.",
        result["institutions_inserted"], result["capabilities_inserted"], result["institutions_skipped_already_present"],
    )
    print(result)
