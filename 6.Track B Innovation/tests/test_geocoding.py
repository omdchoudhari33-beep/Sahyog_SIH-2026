from unittest.mock import MagicMock, patch

from app import geocoding


def setup_function():
    geocoding._cache.clear()


def test_reverse_geocode_returns_none_when_coordinates_missing():
    assert geocoding.reverse_geocode(None, None) is None
    assert geocoding.reverse_geocode(23.34, None) is None


def test_reverse_geocode_returns_display_name_on_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {"display_name": "Kanke, Ranchi, Jharkhand, India"}
    mock_response.raise_for_status = MagicMock()
    with patch.object(geocoding.httpx, "get", return_value=mock_response) as mock_get:
        result = geocoding.reverse_geocode(23.34, 85.31)
    assert result == "Kanke, Ranchi, Jharkhand, India"
    mock_get.assert_called_once()


def test_reverse_geocode_caches_by_rounded_coordinates():
    mock_response = MagicMock()
    mock_response.json.return_value = {"display_name": "Ranchi, Jharkhand"}
    mock_response.raise_for_status = MagicMock()
    with patch.object(geocoding.httpx, "get", return_value=mock_response) as mock_get:
        geocoding.reverse_geocode(23.340001, 85.310001)
        geocoding.reverse_geocode(23.340002, 85.310002)  # same place, tiny float noise below 5-decimal rounding
    mock_get.assert_called_once()  # second call served from cache


def test_reverse_geocode_fails_soft_on_network_error():
    with patch.object(geocoding.httpx, "get", side_effect=Exception("timed out")):
        result = geocoding.reverse_geocode(23.34, 85.31)
    assert result is None


def test_maps_link_format():
    assert geocoding.maps_link(23.34, 85.31) == "https://www.google.com/maps?q=23.34,85.31"
