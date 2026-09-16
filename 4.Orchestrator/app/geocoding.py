"""
Free-text location fallback for when browser geolocation isn't available
(permission denied, corporate firewall/policy blocking it, desktop testing).

Uses OpenStreetMap's Nominatim - free, no API key, no cost - matching this
project's "open-source, cloud-ready" cost-feasibility claims. Nominatim's
usage policy requires a descriptive User-Agent and caps public-instance use
to ~1 request/second; fine for citizen-facing lookups, not for bulk geocoding.
"""
from __future__ import annotations

from typing import Optional

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SahyogCivicReporting/0.1 (hackathon prototype)"


async def geocode_address(address_text: str) -> Optional[dict]:
    """Returns {"latitude", "longitude", "display_name"} for the best match,
    or None if nothing was found / the service is unreachable."""
    if not address_text or not address_text.strip():
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                NOMINATIM_URL,
                params={"q": address_text, "format": "json", "limit": 1},
                headers={"User-Agent": USER_AGENT},
            )
        response.raise_for_status()
        results = response.json()
    except Exception as exc:
        print(f"Geocoding failed for '{address_text}': {exc}")
        return None

    if not results:
        return None

    match = results[0]
    return {
        "latitude": float(match["lat"]),
        "longitude": float(match["lon"]),
        "display_name": match.get("display_name", address_text),
    }
