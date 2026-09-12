import asyncio
from app.schemas.project import LocationBase, LocationCreate
from app.schemas.ranking import GeoGridScanRequest
from pydantic import ValidationError

def test_location_coordinate_validation():
    """Verify coordinate bounds validation in LocationBase and GeoGridScanRequest."""
    # Valid coordinates
    loc_valid = LocationCreate(name="Test Loc", latitude=37.7749, longitude=-122.4194)
    assert loc_valid.latitude == 37.7749
    assert loc_valid.longitude == -122.4194

    # Invalid latitude > 90
    try:
        LocationCreate(name="Invalid Lat", latitude=95.0, longitude=-122.4194)
        assert False, "Expected ValidationError for latitude 95.0"
    except ValidationError:
        pass

    # Invalid latitude < -90
    try:
        LocationCreate(name="Invalid Lat", latitude=-95.0, longitude=-122.4194)
        assert False, "Expected ValidationError for latitude -95.0"
    except ValidationError:
        pass

    # Invalid longitude > 180
    try:
        LocationCreate(name="Invalid Lng", latitude=37.7749, longitude=200.0)
        assert False, "Expected ValidationError for longitude 200.0"
    except ValidationError:
        pass

    # GeoGridScanRequest valid & invalid bounds
    scan_req_valid = GeoGridScanRequest(center_lat=40.7128, center_lng=-74.0060)
    assert scan_req_valid.center_lat == 40.7128

    try:
        GeoGridScanRequest(center_lat=100.0, center_lng=0.0)
        assert False, "Expected ValidationError for center_lat 100.0"
    except ValidationError:
        pass

def test_geogrid_multi_location_resolution():
    """Verify GeoGridScanner location resolution and calculation."""
    from app.services.serp.grid_scanner import GeoGridScanner
    coords = GeoGridScanner.calculate_grid_coordinates(
        center_lat=37.7749,
        center_lng=-122.4194,
        radius_km=7.5,
        grid_size=5
    )
    assert len(coords) == 25
    center_pt = next(p for p in coords if p["row"] == 2 and p["col"] == 2)
    assert center_pt["lat"] == 37.7749
    assert center_pt["lng"] == -122.4194

if __name__ == "__main__":
    test_location_coordinate_validation()
    test_geogrid_multi_location_resolution()
    print("[PASS] Multi-location & Geo-Grid coordinate validation tests passed!")
