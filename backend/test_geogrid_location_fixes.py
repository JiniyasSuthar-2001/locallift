import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.models.ranking import GeoGridScan
from app.schemas.ranking import GeoGridScanOut
from app.services.serp.base import SERPProvider, SERPResponse, SERPItem
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.serp.mock_provider import MockSERPProvider
from app.services.geocoding import GeocodingService
from app.services.template_service import TemplateEngine, SYSTEM_TEMPLATES
from app.models.template import Template
from app.models.project import Project, Location
from app.models.user import User, Organization, OrganizationMember, OrgRole
from sqlalchemy.future import select
from app.database import AsyncSessionLocal, Base, engine

# ---------------------------------------------------------------------------
# 1. Custom Mock Providers for Deterministic Failure Testing
# ---------------------------------------------------------------------------

class PartialFailureSERPProvider(SERPProvider):
    """Fails specific points (e.g. 5 out of 25) to test partial failure handling."""
    def __init__(self, fail_count: int = 5):
        self.call_count = 0
        self.fail_count = fail_count

    @property
    def is_configured(self) -> bool:
        return True

    async def search_keyword(self, keyword: str, location: str = None, country: str = "us", language: str = "en", device: str = "desktop", num_results: int = 100):
        return SERPResponse(provider="mock_partial", keyword=keyword, success=True)

    async def search_local_grid_point(self, keyword: str, lat: float, lng: float, location_name: str = None, zoom: int = 14):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            return SERPResponse(
                provider="mock_partial",
                keyword=keyword,
                success=False,
                error_code="RATE_LIMIT",
                error_message="Mocked rate limit error on grid node"
            )
        return SERPResponse(
            provider="mock_partial",
            keyword=keyword,
            success=True,
            local_pack_results=[
                SERPItem(
                    position=1,
                    title="Real Target Business",
                    link="https://targetbusiness.com",
                    domain="targetbusiness.com",
                    item_type="local_pack",
                    rating=4.9,
                    reviews_count=120
                )
            ]
        )

class UnconfiguredSERPProvider(SERPProvider):
    """Simulates an unconfigured SERP provider."""
    @property
    def is_configured(self) -> bool:
        return False

    async def search_keyword(self, keyword: str, location: str = None, country: str = "us", language: str = "en", device: str = "desktop", num_results: int = 100):
        return SERPResponse(
            provider="serpapi",
            keyword=keyword,
            success=False,
            error_code="SERP_PROVIDER_NOT_CONFIGURED",
            error_message="SERP provider API key not configured."
        )

    async def search_local_grid_point(self, keyword: str, lat: float, lng: float, location_name: str = None, zoom: int = 14):
        return SERPResponse(
            provider="serpapi",
            keyword=keyword,
            success=False,
            error_code="SERP_PROVIDER_NOT_CONFIGURED",
            error_message="SERP provider API key not configured."
        )

# ---------------------------------------------------------------------------
# Test Functions
# ---------------------------------------------------------------------------

def test_geogrid_all_successful():
    GeoGridScanner.clear_cache()
    async def _test():
        preset = [
            {"position": 1, "link": "https://denverplumbingpros.com/services", "title": "Denver Plumbing Pros", "type": "local_pack"}
        ]
        provider = MockSERPProvider(preset_results=preset)
        res = await GeoGridScanner.scan_grid(
            provider=provider,
            keyword="denver plumber",
            target_domain="denverplumbingpros.com",
            center_lat=39.7392,
            center_lng=-104.9903,
            radius_km=10.0,
            grid_size=5
        )
        assert res["total_points"] == 25
        assert res["successful_points"] == 25
        assert res["failed_points"] == 0
        assert res["scan_status"] == "completed"
        assert res["average_rank"] == 1.0
        assert res["local_visibility_pct"] == 100.0
    asyncio.run(_test())

def test_geogrid_partial_failure():
    GeoGridScanner.clear_cache()
    async def _test():
        provider = PartialFailureSERPProvider(fail_count=5)
        res = await GeoGridScanner.scan_grid(
            provider=provider,
            keyword="denver plumber",
            target_domain="targetbusiness.com",
            center_lat=39.7392,
            center_lng=-104.9903,
            radius_km=10.0,
            grid_size=5,
            concurrency_limit=1  # Sequential to control exact count
        )
        assert res["total_points"] == 25
        assert res["successful_points"] == 20
        assert res["failed_points"] == 5
        assert res["scan_status"] == "completed_with_errors"
    asyncio.run(_test())

def test_geogrid_all_failed():
    GeoGridScanner.clear_cache()
    async def _test():
        provider = PartialFailureSERPProvider(fail_count=25)
        res = await GeoGridScanner.scan_grid(
            provider=provider,
            keyword="denver plumber",
            target_domain="targetbusiness.com",
            center_lat=39.7392,
            center_lng=-104.9903,
            radius_km=10.0,
            grid_size=5,
            concurrency_limit=1
        )
        assert res["total_points"] == 25
        assert res["successful_points"] == 0
        assert res["failed_points"] == 25
        assert res["scan_status"] == "failed"
        assert res["average_rank"] is None
        assert res["local_visibility_pct"] == 0.0
    asyncio.run(_test())

def test_geogrid_unconfigured_provider():
    GeoGridScanner.clear_cache()
    async def _test():
        provider = UnconfiguredSERPProvider()
        res = await GeoGridScanner.scan_grid(
            provider=provider,
            keyword="denver plumber",
            target_domain="targetbusiness.com",
            center_lat=39.7392,
            center_lng=-104.9903,
            radius_km=10.0,
            grid_size=5
        )
        assert res["total_points"] == 25
        assert res["successful_points"] == 0
        assert res["failed_points"] == 25
        assert res["scan_status"] == "failed"
        assert res["average_rank"] is None
    asyncio.run(_test())

def test_geocoding_service():
    async def _test():
        # 1. Geocoding failure / empty
        with patch("httpx.AsyncClient.get", side_effect=Exception("Timeout")):
            coords = await GeocodingService.geocode_address(address="Invalid Address Nowhere 99999999")
            assert coords is None  # Must be None, NEVER Brisbane!

        # 2. Geocoding successful resolution
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: [{"lat": "39.7392358", "lon": "-104.990251"}]
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            coords = await GeocodingService.geocode_address(address="1 Main St", city="Denver", state="CO", postal_code="80202", country="US")
            assert coords is not None
            lat, lng = coords
            assert round(lat, 4) == 39.7392
            assert round(lng, 4) == -104.9903
    asyncio.run(_test())

def test_schema_template_rendering():
    async def _test():
        schema_t = next(t for t in SYSTEM_TEMPLATES if t["slug"] == "localbusiness-schema-jsonld")
        tmpl = Template(
            name=schema_t["name"],
            slug=schema_t["slug"],
            category=schema_t["category"],
            template_type=schema_t["template_type"],
            content=schema_t["content"]
        )

        async with AsyncSessionLocal() as session:
            # Create Organization for multi-tenant isolation compliance
            org_slug = f"test-agency-geo-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
            org = Organization(
                name="Test Agency",
                slug=org_slug,
                plan="agency_pro"
            )
            session.add(org)
            await session.flush()

            # Create a mock project without coordinates
            proj_no_geo = Project(
                organization_id=org.id,
                name="Denver HVAC Pros",
                domain="denverhvacpros.com",
                country="United States"
            )
            session.add(proj_no_geo)
            await session.flush()

            loc_no_geo = Location(
                project_id=proj_no_geo.id,
                name="Headquarters",
                address="123 16th St",
                city="Denver",
                state="CO",
                postal_code="80202",
                country="US",
                latitude=None,
                longitude=None
            )
            session.add(loc_no_geo)
            await session.commit()

            # Render template for location WITHOUT coordinates
            rendered_no_geo, used, missing = await TemplateEngine.render_template(
                db=session,
                template=tmpl,
                project_id=proj_no_geo.id,
                location_id=loc_no_geo.id
            )

            # Assert no Brisbane coordinates
            assert "-27.4698" not in rendered_no_geo
            assert "153.0251" not in rendered_no_geo
            # Assert "geo" is omitted
            assert '"geo"' not in rendered_no_geo
            print("RENDERED_NO_GEO:\n", rendered_no_geo)
            parsed_no_geo = json.loads(rendered_no_geo)
            assert parsed_no_geo["name"] == "Denver HVAC Pros"
            assert "geo" not in parsed_no_geo

            # Now update with REAL coordinates
            loc_no_geo.latitude = 39.7392
            loc_no_geo.longitude = -104.9903
            await session.commit()

            # Render template for location WITH coordinates
            rendered_geo, used_geo, _ = await TemplateEngine.render_template(
                db=session,
                template=tmpl,
                project_id=proj_no_geo.id,
                location_id=loc_no_geo.id
            )

            assert '"geo"' in rendered_geo
            parsed_geo = json.loads(rendered_geo)
            assert "geo" in parsed_geo
            assert parsed_geo["geo"]["latitude"] == 39.7392
            assert parsed_geo["geo"]["longitude"] == -104.9903

            # Cleanup
            await session.delete(loc_no_geo)
            await session.delete(proj_no_geo)
            await session.delete(org)
            await session.commit()

    asyncio.run(_test())

async def setup_db():
    from app.main import _sync_sqlite_schema
    import app.models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_sqlite_schema)

def test_geogrid_missing_coordinates_rejection():
    """Verify that attempting a GeoGrid scan without coordinates returns 400 LOCATION_COORDINATES_REQUIRED."""
    async def _test():
        from app.api.v1.keywords import trigger_grid_scan
        from app.schemas.ranking import GeoGridScanRequest
        from app.models.ranking import Keyword
        from fastapi import HTTPException

        async with AsyncSessionLocal() as session:
            org = Organization(
                name="Denver Agency",
                slug=f"denver-agency-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                plan="agency_pro"
            )
            session.add(org)
            await session.flush()

            user = User(
                email=f"tester-{int(datetime.now(timezone.utc).timestamp() * 1000)}@denver.io",
                full_name="Denver Tester",
                hashed_password="hash",
                is_active=True
            )
            session.add(user)
            await session.flush()

            member = OrganizationMember(
                organization_id=org.id,
                user_id=user.id,
                role=OrgRole.OWNER
            )
            session.add(member)

            # Project with NO location coordinates
            proj = Project(
                organization_id=org.id,
                name="Denver No Coords Business",
                domain="nocoordsdenver.com",
                country="US"
            )
            session.add(proj)
            await session.flush()

            kw = Keyword(
                project_id=proj.id,
                keyword="denver roof repair",
                target_location="Denver Metro",
                last_checked_at=datetime.now(timezone.utc)
            )
            session.add(kw)
            await session.commit()

            scan_req = GeoGridScanRequest(keyword_id=kw.id)

            threw_expected_error = False
            try:
                await trigger_grid_scan(scan_req=scan_req, current_user=user, db=session)
            except HTTPException as e:
                if e.status_code == 400 and "LOCATION_COORDINATES_REQUIRED" in str(e.detail):
                    threw_expected_error = True

            assert threw_expected_error, "Should raise 400 LOCATION_COORDINATES_REQUIRED when no GPS coordinates exist!"

            # Cleanup
            await session.delete(kw)
            await session.delete(proj)
            await session.delete(member)
            await session.delete(user)
            await session.delete(org)
            await session.commit()

    asyncio.run(_test())

def test_project_creation_without_brisbane_fallback():
    """Verify that creating a project with a new address does NOT default to Brisbane coordinates."""
    async def _test():
        from app.api.v1.projects import create_project
        from app.schemas.project import ProjectCreate, LocationCreate

        async with AsyncSessionLocal() as session:
            org = Organization(
                name="Colorado Agency",
                slug=f"co-agency-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                plan="agency_pro"
            )
            session.add(org)
            await session.flush()

            user = User(
                email=f"co-tester-{int(datetime.now(timezone.utc).timestamp() * 1000)}@colorado.io",
                full_name="Colorado Tester",
                hashed_password="hash",
                is_active=True
            )
            session.add(user)
            await session.flush()

            member = OrganizationMember(
                organization_id=org.id,
                user_id=user.id,
                role=OrgRole.OWNER
            )
            session.add(member)
            await session.commit()

            # Create project with address where geocoder fails/times out
            with patch("httpx.AsyncClient.get", side_effect=Exception("Timeout")):
                proj_in = ProjectCreate(
                    organization_id=org.id,
                    name="1 Main St Denver Shop",
                    domain="denvershop1main.com",
                    primary_category="Retail",
                    country="US",
                    location=LocationCreate(
                        name="Main Store",
                        address="1 Main St",
                        city="Denver",
                        state="CO",
                        postal_code="80202",
                        country="US"
                    )
                )

                created_proj = await create_project(project_in=proj_in, current_user=user, db=session)
                assert created_proj is not None
                assert len(created_proj.locations) > 0
                loc = created_proj.locations[0]

                # CRITICAL VERIFICATION:
                # Must NOT receive -27.4698 or 153.0251
                assert loc.latitude is None, f"Expected latitude to be None on geocoding failure, got {loc.latitude}"
                assert loc.longitude is None, f"Expected longitude to be None on geocoding failure, got {loc.longitude}"

                # Cleanup
                from app.models.project import Project as ProjectModel, Website as WebsiteModel
                loc_db = await session.get(Location, loc.id)
                proj_db = await session.get(ProjectModel, created_proj.id)
                websites = await session.execute(select(WebsiteModel).where(WebsiteModel.project_id == created_proj.id))
                for w in websites.scalars().all():
                    await session.delete(w)
                if loc_db:
                    await session.delete(loc_db)
                if proj_db:
                    await session.delete(proj_db)
                await session.delete(member)
                await session.delete(user)
                await session.delete(org)
                await session.commit()

    asyncio.run(_test())

def run_all():
    asyncio.run(setup_db())

    print("--- Running Test 1: GeoGrid All Successful ---")
    test_geogrid_all_successful()
    print("[PASS] GeoGrid All Successful")

    print("--- Running Test 2: GeoGrid Partial Failure ---")
    test_geogrid_partial_failure()
    print("[PASS] GeoGrid Partial Failure (completed_with_errors)")

    print("--- Running Test 3: GeoGrid All Failed ---")
    test_geogrid_all_failed()
    print("[PASS] GeoGrid All Failed")

    print("--- Running Test 4: GeoGrid Unconfigured Provider ---")
    test_geogrid_unconfigured_provider()
    print("[PASS] GeoGrid Unconfigured Provider")

    print("--- Running Test 5: Geocoding Service ---")
    test_geocoding_service()
    print("[PASS] Geocoding Service & Fallback Prevention")

    print("--- Running Test 6: Schema Template Rendering ---")
    test_schema_template_rendering()
    print("[PASS] Schema Template Real / Missing Coordinates Rendering")

    print("--- Running Test 7: Missing Coordinates 400 Rejection ---")
    test_geogrid_missing_coordinates_rejection()
    print("[PASS] Missing Coordinates Rejection (LOCATION_COORDINATES_REQUIRED)")

    print("--- Running Test 8: Project Creation Without Brisbane Fallback ---")
    test_project_creation_without_brisbane_fallback()
    print("[PASS] Project Creation Without Brisbane Fallback")

    print("\n[SUCCESS] ALL PART 1 GEO-GRID & LOCATION TESTS PASSED!")

if __name__ == "__main__":
    run_all()
