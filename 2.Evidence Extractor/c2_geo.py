from typing import Optional
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from schemas import Geolocation, GeoOrigin


def _convert_to_degrees(dms) -> float:
    """Convert an EXIF (degrees, minutes, seconds) tuple to decimal degrees."""
    degrees, minutes, seconds = dms[0], dms[1], dms[2]
    return float(degrees) + (float(minutes) / 60.0) + (float(seconds) / 3600.0)


def extract_gps_coordinates(gps_info: dict) -> Optional[tuple[float, float]]:
    """Decode real decimal-degree coordinates from an EXIF GPSInfo dict."""
    try:
        lat_dms = gps_info.get("GPSLatitude")
        lat_ref = gps_info.get("GPSLatitudeRef")
        lon_dms = gps_info.get("GPSLongitude")
        lon_ref = gps_info.get("GPSLongitudeRef")

        if not (lat_dms and lat_ref and lon_dms and lon_ref):
            return None

        latitude = _convert_to_degrees(lat_dms)
        if str(lat_ref).upper() == "S":
            latitude = -latitude

        longitude = _convert_to_degrees(lon_dms)
        if str(lon_ref).upper() == "W":
            longitude = -longitude

        return round(latitude, 6), round(longitude, 6)
    except (TypeError, IndexError, ValueError, ZeroDivisionError):
        return None


def get_exif_data(image_path: str):
    """Extracts raw EXIF data securely without external APIs."""
    try:
        image = Image.open(image_path)
        image.verify()
        image = Image.open(image_path)
        exif = image._getexif()
        if not exif:
            return None
            
        exif_data = {}
        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                gps_data = {}
                for gps_tag_id in value:
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_data[gps_tag] = value[gps_tag_id]
                exif_data["GPSInfo"] = gps_data
            else:
                exif_data[tag] = value
        return exif_data
    except Exception:
        return None

def resolve_geo_data(
    image_path: Optional[str] = None, 
    device_lat: Optional[float] = None, 
    device_lon: Optional[float] = None, 
    device_timestamp: Optional[str] = None
) -> Geolocation:
    
    make = None
    model = None
    
    if image_path:
        exif = get_exif_data(image_path)
        if exif:
            make = exif.get("Make")
            model = exif.get("Model")
            
            if "GPSInfo" in exif:
                coordinates = extract_gps_coordinates(exif["GPSInfo"])
                if coordinates:
                    latitude, longitude = coordinates
                    return Geolocation(
                        latitude=latitude,
                        longitude=longitude,
                        origin=GeoOrigin.EXIF_IMAGE,
                        timestamp=device_timestamp,
                        device_make=make,
                        device_model=model,
                        is_timestamp_valid=True
                    )

    if device_lat is not None and device_lon is not None:
        return Geolocation(
            latitude=device_lat,
            longitude=device_lon,
            origin=GeoOrigin.CLIENT_DEVICE_FALLBACK,
            timestamp=device_timestamp,
            device_make=make,
            device_model=model,
            is_timestamp_valid=True if device_timestamp else False
        )
        
    return Geolocation(
        latitude=None,
        longitude=None,
        origin=GeoOrigin.NONE,
        timestamp=device_timestamp,
        device_make=make,
        device_model=model,
        is_timestamp_valid=False
    )