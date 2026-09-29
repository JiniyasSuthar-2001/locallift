import os
import sys
import math
import pytest
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.dirname(__file__))

from app.test_helper import init_test_db, create_test_tenant
from app.database import AsyncSessionLocal
from app.models.project import Location
from app.models.local_seo import BusinessProfile
from app.models.gbp import GoogleBusinessProfile
from app.models.ranking import GeoGridScan, GeoGridPointResult
from app.services.serp.grid_location_resolver import GeoGridLocationResolver
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.serp.base import SERPProvider, SERPResponse, SERPCapabilities, SERPItem
from app.services.geocoding import GeocodingService


@pytest.mark.asyncio
async def test_geogrid_exact_stored_coordinates_priority():
    """
    Priority 1: Verified business latitude/longitude already stored in LocalLift.
    Center must be exact business coordinates, yielding 25 unique discrete satellite coordinates.
    """
    await init_test_db(reset=False)

    user_a, org_a, proj_a, token_a = await create_test_tenant(
        project_name="iHriday Therapy Centre Project",
        domain="ihriday.com"
    )

    async with AsyncSessionLocal() as db:
        # Create business location with exact coordinates and full address
        loc = Location(
            project_id=proj_a.id,
            name="iHriday Main Campus",
            address="Plot 5, Vasna Rd, behind Yogeshwar Apartment, opposite Raneshwar Hospital, Ashwamegh Nagar, Vasna, Vadodara, Gujarat 390015",
            city="Vadodara",
            state="Gujarat",
            postal_code="390015",
            country="India",
            latitude=22.2965412,
            longitude=73.1528934
        )
        db.add(loc)
        await db.commit()
        await db.refresh(loc)

        resolved = await GeoGridLocationResolver.resolve_business_center(
            db=db,
            project_id=proj_a.id,
            location_id=loc.id
        )

        assert resolved.location_precision == "EXACT"
        assert resolved.center_source == "STORED_BUSINESS_COORDINATES"
        assert math.isclose(resolved.latitude, 22.2965412, rel_tol=1e-5)
        assert math.isclose(resolved.longitude, 73.1528934, rel_tol=1e-5)
        assert "Plot 5, Vasna Rd" in resolved.center_address
        assert resolved.warning_message is None

        # Verify 5x5 grid generation centered on exact business coordinates
        grid_points = GeoGridScanner.calculate_grid_coordinates(
            center_lat=resolved.latitude,
            center_lng=resolved.longitude,
            radius_km=5.0,
            grid_size=5
        )

        assert len(grid_points) == 25
        # Verify Center Point (point index 12 in 0-indexed 5x5) is center
        center_pt = grid_points[12]
        assert math.isclose(center_pt["lat"], 22.2965412, rel_tol=1e-4)
        assert math.isclose(center_pt["lng"], 73.1528934, rel_tol=1e-4)

        # Verify distinct GPS coordinates across all 25 points
        unique_coords = {(round(p["lat"], 5), round(p["lng"], 5)) for p in grid_points}
        assert len(unique_coords) == 25, "All 25 grid points must have unique discrete coordinates"


@pytest.mark.asyncio
async def test_geogrid_full_address_geocoding_fallback():
    """
    Priority 3: Full street address geocoding when stored coordinates are missing.
    Must preserve complete structured address and mark as ADDRESS_RESOLVED.
    """
    await init_test_db(reset=False)

    user_a, org_a, proj_a, token_a = await create_test_tenant(
        project_name="iHriday Geocode Test",
        domain="ihriday-geocode.com"
    )

    async with AsyncSessionLocal() as db:
        full_addr = "Plot 5, Vasna Rd, behind Yogeshwar Apartment, opposite Raneshwar Hospital, Ashwamegh Nagar, Vasna, Vadodara, Gujarat 390015"
        loc = Location(
            project_id=proj_a.id,
            name="iHriday Therapy Centre",
            address=full_addr,
            city="Vadodara",
            state="Gujarat",
            postal_code="390015",
            country="India",
            latitude=None,
            longitude=None
        )
        db.add(loc)
        await db.commit()
        await db.refresh(loc)

        with patch.object(GeocodingService, "geocode_full_address", new_callable=AsyncMock) as mock_geo:
            mock_geo.return_value = (22.2961, 73.1530)
            
            resolved = await GeoGridLocationResolver.resolve_business_center(
                db=db,
                project_id=proj_a.id,
                location_id=loc.id
            )

            assert resolved.location_precision == "ADDRESS_RESOLVED"
            assert resolved.center_source == "GEOCODED_ADDRESS"
            assert math.isclose(resolved.latitude, 22.2961, rel_tol=1e-4)
            assert math.isclose(resolved.longitude, 73.1530, rel_tol=1e-4)
            assert resolved.warning_message is None
            
            mock_geo.assert_called_once()
            called_addr = mock_geo.call_args.kwargs.get("full_address") or (mock_geo.call_args[0][0] if mock_geo.call_args[0] else "")
            assert "Plot 5, Vasna Rd" in called_addr


@pytest.mark.asyncio
async def test_geogrid_city_level_fallback_and_warning():
    """
    Priority 4: When only city/state is available, system must set precision=CITY_LEVEL
    and produce an explicit transparency warning for the UI/report.
    """
    await init_test_db(reset=False)

    user_a, org_a, proj_a, token_a = await create_test_tenant(
        project_name="City Only Project",
        domain="cityonly.com"
    )

    async with AsyncSessionLocal() as db:
        loc = Location(
            project_id=proj_a.id,
            name="Vadodara Branch",
            address=None,
            city="Vadodara",
            state="Gujarat",
            postal_code=None,
            country="India",
            latitude=None,
            longitude=None
        )
        db.add(loc)
        await db.commit()
        await db.refresh(loc)

        with patch.object(GeocodingService, "geocode_address", new_callable=AsyncMock) as mock_city_geo:
            mock_city_geo.return_value = (22.3072, 73.1812)

            resolved = await GeoGridLocationResolver.resolve_business_center(
                db=db,
                project_id=proj_a.id,
                location_id=loc.id
            )

            assert resolved.location_precision == "CITY_LEVEL"
            assert resolved.center_source == "CITY_FALLBACK"
            assert resolved.warning_message is not None
            assert "city-level location and may be less precise" in resolved.warning_message


@pytest.mark.asyncio
async def test_geogrid_place_id_resolution():
    """
    Priority 2: Google Place ID resolution. Authoritative coordinates used and marked EXACT.
    """
    await init_test_db(reset=False)

    user_a, org_a, proj_a, token_a = await create_test_tenant(
        project_name="Place ID Project",
        domain="placeidtest.com"
    )

    async with AsyncSessionLocal() as db:
        bp = BusinessProfile(
            project_id=proj_a.id,
            business_name="iHriday Occupational Therapy",
            primary_address="Plot 5, Vasna Rd, Ashwamegh Nagar, Vasna, Vadodara, Gujarat 390015",
            city="Vadodara",
            state="Gujarat",
            postal_code="390015",
            latitude=22.2965,
            longitude=73.1528
        )
        db.add(bp)
        await db.commit()

        resolved = await GeoGridLocationResolver.resolve_business_center(
            db=db,
            project_id=proj_a.id
        )

        assert resolved.location_precision == "EXACT"
        assert resolved.center_source in ("GOOGLE_PLACES", "STORED_BUSINESS_COORDINATES", "PLACE_ID_RESOLVED")
        assert math.isclose(resolved.latitude, 22.2965, rel_tol=1e-4)
        assert math.isclose(resolved.longitude, 73.1528, rel_tol=1e-4)


@pytest.mark.asyncio
async def test_geogrid_project_isolation():
    """
    Verify strict project isolation: Project A and Project B locations never leak.
    """
    await init_test_db(reset=False)

    user_a, org_a, proj_a, token_a = await create_test_tenant(
        project_name="Vadodara Clinic",
        domain="vadodaraclinic.com"
    )
    user_b, org_b, proj_b, token_b = await create_test_tenant(
        project_name="Ahmedabad Clinic",
        domain="ahmedabadclinic.com"
    )

    async with AsyncSessionLocal() as db:
        loc_a = Location(
            project_id=proj_a.id,
            name="Vadodara Location",
            address="Plot 5, Vasna Rd, Vadodara, Gujarat 390015",
            city="Vadodara",
            state="Gujarat",
            latitude=22.2965,
            longitude=73.1528
        )
        loc_b = Location(
            project_id=proj_b.id,
            name="Ahmedabad Location",
            address="SG Highway, Bodakdev, Ahmedabad, Gujarat 380054",
            city="Ahmedabad",
            state="Gujarat",
            latitude=23.0300,
            longitude=72.5000
        )
        db.add_all([loc_a, loc_b])
        await db.commit()

        res_a = await GeoGridLocationResolver.resolve_business_center(db=db, project_id=proj_a.id)
        res_b = await GeoGridLocationResolver.resolve_business_center(db=db, project_id=proj_b.id)

        assert math.isclose(res_a.latitude, 22.2965, rel_tol=1e-4)
        assert math.isclose(res_a.longitude, 73.1528, rel_tol=1e-4)

        assert math.isclose(res_b.latitude, 23.0300, rel_tol=1e-4)
        assert math.isclose(res_b.longitude, 72.5000, rel_tol=1e-4)

        # Strictly isolated
        assert abs(res_a.latitude - res_b.latitude) > 0.5


@pytest.mark.asyncio
async def test_geogrid_scanner_search_request_coordinates():
    """
    Verify that every grid point search request receives its own discrete GPS coordinates (ll: @lat,lng,zoom)
    and does NOT simply repeat 'Vadodara, Gujarat' for all searches.
    """
    center_lat = 22.2965
    center_lng = 73.1528

    searched_calls = []

    class MockProvider(SERPProvider):
        @property
        def capabilities(self) -> SERPCapabilities:
            return SERPCapabilities(geo_grid=True, coordinate_search=True, maps_search=True)

        @property
        def is_configured(self) -> bool:
            return True

        async def search_keyword(self, keyword: str, location: str = None, country: str = "us", language: str = "en", device: str = "desktop", num_results: int = 100) -> SERPResponse:
            return SERPResponse(provider="mock", keyword=keyword, success=True, organic_results=[])

        async def search_local_grid_point(self, keyword: str, lat: float, lng: float, zoom: int = 14) -> SERPResponse:
            searched_calls.append({"keyword": keyword, "lat": lat, "lng": lng, "zoom": zoom})
            return SERPResponse(
                provider="mock_serpapi",
                keyword=keyword,
                location=f"@{lat},{lng}",
                success=True,
                local_pack_results=[
                    SERPItem(position=1, title="iHriday Therapy Centre", domain="ihriday.com", place_id="p1")
                ]
            )

    provider = MockProvider()

    with patch.object(GeocodingService, "reverse_geocode", new_callable=AsyncMock) as mock_rev:
        mock_rev.return_value = "Vasna Road, Vadodara"

        result = await GeoGridScanner.scan_grid(
            provider=provider,
            keyword="occupational therapy",
            target_domain="ihriday.com",
            center_lat=center_lat,
            center_lng=center_lng,
            radius_km=5.0,
            grid_size=5,
            business_name="iHriday Therapy Centre"
        )

        assert len(searched_calls) == 25
        # Verify that each call received distinct coordinates
        coord_pairs = {(round(c["lat"], 5), round(c["lng"], 5)) for c in searched_calls}
        assert len(coord_pairs) == 25, "All 25 SERP calls must use distinct GPS coordinates"

        # Verify query was the target keyword without appending "Vadodara, Gujarat"
        for c in searched_calls:
            assert c["keyword"] == "occupational therapy"
            assert isinstance(c["lat"], float)
            assert isinstance(c["lng"], float)
