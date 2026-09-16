import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from c2_geo import _convert_to_degrees, extract_gps_coordinates


def test_convert_to_degrees_matches_known_point():
    # 23 deg 20' 38.76" ~= 23.3441 decimal degrees (Ranchi latitude).
    assert round(_convert_to_degrees((23, 20, 38.76)), 4) == 23.3441


def test_extract_gps_coordinates_applies_hemisphere_sign():
    gps_info = {
        "GPSLatitude": (23, 20, 38.76),
        "GPSLatitudeRef": "S",
        "GPSLongitude": (85, 18, 34.56),
        "GPSLongitudeRef": "W",
    }
    lat, lon = extract_gps_coordinates(gps_info)
    assert lat < 0
    assert lon < 0


def test_extract_gps_coordinates_returns_none_when_missing():
    assert extract_gps_coordinates({}) is None
