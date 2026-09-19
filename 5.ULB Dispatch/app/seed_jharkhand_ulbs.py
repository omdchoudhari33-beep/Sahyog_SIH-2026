"""Seeds real Jharkhand Urban Local Bodies into ulb_directory/ulb_contacts,
so Track A dispatch actually has statewide coverage instead of the single
"Demo ULB (auto-seeded)" catch-all box that only covers part of the state.

Run manually (same "not auto-run at startup" convention as every schema
migration in this repo):
    python -m app.seed_jharkhand_ulbs

Idempotent: matches on ULB name, skips any ULB already present.

Coverage approach: ulb_directory.boundary is a single POLYGON per row (see
schema.sql) - there is no real, precise municipal-boundary GIS dataset
available here, so this builds a guillotine/kd-tree partition of Jharkhand's
overall bounding box into 12 non-overlapping rectangles, one per major city
below, each assigned by simple lat/lon proximity. These are coverage ZONES
for routing purposes, not surveyed administrative boundaries - good enough
so any real in-state GPS coordinate resolves to its nearest major ULB
instead of "no usable contact found", but a real deployment should replace
these with actual municipal boundary GeoJSON.

City names/districts/approximate town-centre coordinates are public,
well-known facts. Contact emails are NOT real ULB inboxes - I have no way to
verify those - they are clearly-marked placeholders that MUST be replaced
with verified departmental contacts before EMAIL_DRY_RUN is ever disabled.
"""
from __future__ import annotations

import logging

from app.db import SessionLocal, UlbContact, UlbDirectory

logger = logging.getLogger("ulb_seed")

# Jharkhand's overall extent (approximate, generous padding beyond every
# city below so the outer bands still cover the whole state).
STATE_BOUNDS = {"lat_min": 21.9, "lat_max": 25.4, "lon_min": 83.2, "lon_max": 88.0}

# (name, district, lat, lon) - 12 major ULBs spanning the state's south,
# middle, and north (4 each), real district headquarters / municipal towns.
CITIES: list[tuple[str, str, float, float]] = [
    ("Chaibasa Municipal Council", "West Singhbhum", 22.56, 85.80),
    ("Jamshedpur (Jamshedpur Notified Area Committee)", "East Singhbhum", 22.80, 86.18),
    ("Gumla Municipal Council", "Gumla", 23.04, 84.54),
    ("Khunti Municipal Council", "Khunti", 23.08, 85.28),
    ("Ranchi Municipal Corporation", "Ranchi", 23.34, 85.31),
    ("Bokaro Steel City Municipal Corporation", "Bokaro", 23.67, 86.15),
    ("Hazaribagh Municipal Corporation", "Hazaribagh", 23.98, 85.36),
    ("Dhanbad Municipal Corporation", "Dhanbad", 23.80, 86.43),
    ("Giridih Municipal Council", "Giridih", 24.18, 86.30),
    ("Medininagar (Daltonganj) Municipal Council", "Palamu", 24.05, 84.07),
    ("Deoghar Municipal Corporation", "Deoghar", 24.48, 86.70),
    ("Dumka Municipal Council", "Dumka", 24.27, 87.25),
]

BAND_SIZE = 4  # 12 cities / 3 lat bands = 4 cities per band


def build_city_rectangles() -> list[tuple[str, str, float, float, float, float]]:
    """Returns (name, district, lat_lo, lat_hi, lon_lo, lon_hi) per city - a
    kd-tree/guillotine partition: split into 3 latitude bands by rank, then
    within each band split into 4 longitude columns by rank. Non-overlapping
    and fully covers STATE_BOUNDS by construction (no geometry library
    needed - just sorting the 12 fixed coordinates above)."""
    by_lat = sorted(CITIES, key=lambda c: c[2])
    lat_bands = [by_lat[i : i + BAND_SIZE] for i in range(0, len(by_lat), BAND_SIZE)]
    # Edge between band i and i+1 = midpoint of (max lat in band i, min lat in band i+1).
    lat_cuts = [STATE_BOUNDS["lat_min"]]
    for i in range(len(lat_bands) - 1):
        lat_cuts.append((lat_bands[i][-1][2] + lat_bands[i + 1][0][2]) / 2)
    lat_cuts.append(STATE_BOUNDS["lat_max"])

    rectangles = []
    for band_idx, band in enumerate(lat_bands):
        lat_lo, lat_hi = lat_cuts[band_idx], lat_cuts[band_idx + 1]
        by_lon = sorted(band, key=lambda c: c[3])
        lon_cuts = [STATE_BOUNDS["lon_min"]]
        for i in range(len(by_lon) - 1):
            lon_cuts.append((by_lon[i][3] + by_lon[i + 1][3]) / 2)
        lon_cuts.append(STATE_BOUNDS["lon_max"])
        for col_idx, (name, district, _lat, _lon) in enumerate(by_lon):
            rectangles.append((name, district, lat_lo, lat_hi, lon_cuts[col_idx], lon_cuts[col_idx + 1]))
    return rectangles


def _rectangle_wkt(lat_lo: float, lat_hi: float, lon_lo: float, lon_hi: float) -> str:
    # WKT is (lon, lat) pairs, closed ring - matches ulb_directory.boundary's
    # existing convention (see the pre-existing "Demo ULB" row).
    return (
        f"POLYGON(({lon_lo} {lat_lo}, {lon_hi} {lat_lo}, {lon_hi} {lat_hi}, "
        f"{lon_lo} {lat_hi}, {lon_lo} {lat_lo}))"
    )


def _placeholder_email(ulb_name: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in ulb_name).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"grievance-cell-pending@{slug}.example-pending.jh.gov.in"


def seed_jharkhand_ulbs() -> dict:
    db = SessionLocal()
    inserted_ulbs = 0
    inserted_contacts = 0
    skipped = 0
    try:
        for name, district, lat_lo, lat_hi, lon_lo, lon_hi in build_city_rectangles():
            existing = db.query(UlbDirectory).filter(UlbDirectory.name == name).one_or_none()
            if existing is not None:
                skipped += 1
                continue

            ulb = UlbDirectory(
                name=name, state="Jharkhand", district=district,
                boundary=_rectangle_wkt(lat_lo, lat_hi, lon_lo, lon_hi), active=True,
            )
            db.add(ulb)
            db.flush()
            inserted_ulbs += 1

            db.add(
                UlbContact(
                    ulb_id=ulb.id, domain=None, dept_name="Public Grievance Cell",
                    level=1, channel="email", email=_placeholder_email(name),
                    active=True,
                )
            )
            inserted_contacts += 1

        db.commit()
    finally:
        db.close()

    return {
        "ulbs_inserted": inserted_ulbs,
        "contacts_inserted": inserted_contacts,
        "ulbs_skipped_already_present": skipped,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = seed_jharkhand_ulbs()
    logger.info(
        "Seeded %s ULBs (%s contacts), skipped %s already present. "
        "Contact emails are PLACEHOLDERS - verify real ones before disabling EMAIL_DRY_RUN.",
        result["ulbs_inserted"], result["contacts_inserted"], result["ulbs_skipped_already_present"],
    )
    print(result)
