from unittest.mock import MagicMock, patch

from app.seed_jharkhand_ulbs import (
    CITIES,
    STATE_BOUNDS,
    build_city_rectangles,
    seed_jharkhand_ulbs,
)


def test_build_city_rectangles_returns_one_per_city():
    rects = build_city_rectangles()
    names = {r[0] for r in rects}
    assert len(rects) == len(CITIES)
    assert names == {c[0] for c in CITIES}


def test_rectangles_fully_tile_the_state_bounds_with_no_gaps_or_overlaps():
    """Regression guard for the actual routing bug this seed fixes: any
    point inside STATE_BOUNDS must land in exactly one rectangle - zero
    matches means "no usable contact found" (silently unrouted), more than
    one means AmbiguousUlbMatchError. Checked on a grid of sample points."""
    rects = build_city_rectangles()

    def containing_rects(lat: float, lon: float) -> list[str]:
        hits = []
        for name, _district, lat_lo, lat_hi, lon_lo, lon_hi in rects:
            # Half-open on the upper edge so shared borders aren't double-counted.
            if lat_lo <= lat < lat_hi and lon_lo <= lon < lon_hi:
                hits.append(name)
        return hits

    lat_min, lat_max = STATE_BOUNDS["lat_min"], STATE_BOUNDS["lat_max"]
    lon_min, lon_max = STATE_BOUNDS["lon_min"], STATE_BOUNDS["lon_max"]
    samples = 40
    for i in range(samples):
        lat = lat_min + (lat_max - lat_min) * (i + 0.5) / samples
        for j in range(samples):
            lon = lon_min + (lon_max - lon_min) * (j + 0.5) / samples
            hits = containing_rects(lat, lon)
            assert len(hits) == 1, f"point ({lat},{lon}) matched {hits}"


def test_seed_inserts_one_ulb_and_one_catchall_contact_per_city():
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with patch("app.seed_jharkhand_ulbs.SessionLocal", return_value=db):
        result = seed_jharkhand_ulbs()

    assert result["ulbs_inserted"] == len(CITIES)
    assert result["contacts_inserted"] == len(CITIES)
    assert result["ulbs_skipped_already_present"] == 0
    assert db.commit.called


def test_seed_skips_ulbs_already_present():
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = MagicMock()
    with patch("app.seed_jharkhand_ulbs.SessionLocal", return_value=db):
        result = seed_jharkhand_ulbs()

    assert result["ulbs_inserted"] == 0
    assert result["ulbs_skipped_already_present"] == len(CITIES)
