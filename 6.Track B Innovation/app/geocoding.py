"""Reverse geocoding for the University Portal's match display - turns a
ticket's raw lat/lon into a human-readable place name, so a university sees
"Kanke, Ranchi, Jharkhand" instead of "23.34, 85.31".

Opposite direction from "4.Orchestrator/app/geocoding.py"'s forward
geocoding (address text -> lat/lon, for when the citizen types an address);
same free OpenStreetMap Nominatim service, no API key, same usage-policy
constraints (descriptive User-Agent, ~1 req/s on the public instance) - so
this caches by rounded coordinates (the dashboard re-renders the same
tickets' locations on every page load/poll) and fails soft to raw
coordinates rather than ever blocking or breaking the dashboard.
"""
from __future__ import annotations

from typing import Optional

import httpx

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "SahyogTrackB/0.1 (hackathon prototype)"

# Module-level, process-lifetime cache - good enough for hackathon-scale
# traffic (a handful of tickets, reloaded often by the same few HEI users).
# Keyed by coordinates rounded to ~1m precision, not exact floats, so
# floating-point noise doesn't create spurious cache misses.
_cache: dict[tuple[float, float], str] = {}


def _cache_key(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat, 5), round(lon, 5))


def maps_link(lat: float, lon: float) -> str:
    """A plain Google Maps URL that drops a pin at (lat, lon) - no API key
    needed, works as a normal <a href>."""
    return f"https://www.google.com/maps?q={lat},{lon}"


def reverse_geocode(lat: Optional[float], lon: Optional[float]) -> Optional[str]:
    """Returns a human-readable place name, or None if the coordinates are
    missing or the lookup fails/times out - callers must fall back to
    showing raw coordinates (+ maps_link) in that case, never block on this."""
    if lat is None or lon is None:
        return None

    key = _cache_key(lat, lon)
    if key in _cache:
        return _cache[key]

    try:
        response = httpx.get(
            NOMINATIM_REVERSE_URL,
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 16},
            headers={"User-Agent": USER_AGENT},
            timeout=4.0,
        )
        response.raise_for_status()
        result = response.json()
    except Exception as exc:
        print(f"Reverse geocoding failed for ({lat}, {lon}): {exc}")
        return None

    display_name = result.get("display_name") if isinstance(result, dict) else None
    if display_name:
        _cache[key] = display_name
    return display_name
