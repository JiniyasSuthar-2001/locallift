"""
LocalLift — SERP Production Integrity & Zero False Data Regression Test Suite

Tests the critical production integrity guarantee:
The application must NEVER return fabricated mock rankings or competitor intelligence
(such as Queenshine Electricals) to real users when a live SERP provider is unconfigured,
fails, times out, or encounters errors.
"""

import asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project, Location
from app.models.ranking import Keyword, GeoGridScan
from app.core.security import get_password_hash
from app.services.serp.factory import get_serp_provider
from app.services.serp.serpapi import SerpApiProvider
from app.services.serp.mock_provider import MockSERPProvider
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.serp.base import SERPProvider, SERPResponse, SERPItem
from app.test_helper import init_test_db

# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

class PartialMockProvider(SERPProvider):
    """Simulates 20 successful responses and 5 failed responses across 25 grid points."""
    def __init__(self):
        self.call_count = 0

    @property
    def is_configured(self) -> bool:
        return True

    async def search_keyword(self, keyword: str, **kwargs):
        return SERPResponse(provider="partial_mock", keyword=keyword, success=True)

    async def search_local_grid_point(self, keyword: str, lat: float, lng: float, **kwargs):
        self.call_count += 1
        # Points 1-20 succeed, 21-25 fail with 429 rate limit
        if self.call_count > 20:
            return SERPResponse(
                provider="partial_mock",
                keyword=keyword,
                location=f"@{lat},{lng}",
                success=False,
                error_code="SERP_PROVIDER_RATE_LIMIT",
                error_message="Provider rate limit exceeded on cell."
            )
        return SERPResponse(
            provider="partial_mock",
            keyword=keyword,
            location=f"@{lat},{lng}",
            local_pack_results=[
                SERPItem(
                    position=1,
                    title="Real Denver Competitor",
                    link="https://realdenvercompetitor.com",
                    domain="realdenvercompetitor.com",
                    item_type="local_pack"
                )
            ],
            success=True
        )

# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

async def test_serp_production_integrity():
    # 1. Initialize DB schema cleanly
    await init_test_db(seed_demo=False)

    print("\n=======================================================")
    print(">> TEST 1: DEFAULT CONFIGURATION & ENVIRONMENT GUARDS")
    print("=======================================================")

    # Assert default SERP provider in config is openserp, NOT mock
    assert settings.SERP_PROVIDER == "openserp", f"Expected SERP_PROVIDER == 'openserp', got '{settings.SERP_PROVIDER}'"
    print("[OK] Default settings.SERP_PROVIDER is 'openserp'")

    # When requesting serpapi with no SERPAPI_KEY, SerpApiProvider reports is_configured=False
    unconfigured_provider = get_serp_provider("serpapi")
    assert isinstance(unconfigured_provider, SerpApiProvider)
    assert unconfigured_provider.is_configured is False
    print("[OK] SerpApiProvider initialized with empty key is unconfigured (is_configured=False)")

    # Assert mock provider is strictly blocked when ENVIRONMENT is development or production
    for env in ["development", "production", "staging"]:
        original_env = settings.ENVIRONMENT
        try:
            settings.ENVIRONMENT = env
            blocked = False
            try:
                get_serp_provider("mock")
            except RuntimeError as e:
                blocked = True
                assert "strictly prohibited" in str(e)
            assert blocked, f"Mock provider should be blocked in '{env}' mode!"
        finally:
            settings.ENVIRONMENT = original_env
    print("[OK] MockSERPProvider is strictly prohibited in 'development', 'production', and 'staging' modes")

    # In testing environment, MockSERPProvider is allowed
    original_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "testing"
        mock_prov = get_serp_provider("mock")
        assert isinstance(mock_prov, MockSERPProvider)
    finally:
        settings.ENVIRONMENT = original_env
    print("[OK] MockSERPProvider is allowed when ENVIRONMENT == 'testing'")

    # Clean MockSERPProvider with no presets must return empty results (never Australian electrician domains)
    empty_mock = MockSERPProvider()
    empty_resp = await empty_mock.search_keyword("plumber denver", location="Denver, CO")
    assert empty_resp.success is True
    assert len(empty_resp.organic_results) == 0
    assert len(empty_resp.local_pack_results) == 0
    for r in empty_resp.organic_results + empty_resp.local_pack_results:
        assert "queenshine" not in r.domain.lower()
        assert "electrical" not in r.title.lower()
    print("[OK] Empty MockSERPProvider returns clean empty results without hardcoded Australian domains")

    print("\n=======================================================")
    print(">> TEST 2: DENVER PLUMBING 5x5 GEO-GRID (UNCONFIGURED SERP)")
    print("=======================================================")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create Denver plumbing user & project
        uid = uuid.uuid4().hex[:8]
        user_email = f"denver_plumber_{uid}@example.com"

        reg_res = await client.post("/api/v1/auth/register", json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "Denver Plumbing Owner",
            "organization_name": "Denver Plumbing LLC"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create Denver Plumbing project with Denver coordinates
        proj_res = await client.post("/api/v1/projects", json={
            "name": "Mile High Denver Plumbing",
            "domain": "milehighdenverplumbing.com",
            "primary_category": "Plumber",
            "country": "United States",
            "location": {
                "name": "Denver Downtown Shop",
                "address": "1600 17th St",
                "city": "Denver",
                "state": "CO",
                "postal_code": "80202",
                "country": "United States",
                "latitude": 39.7527,
                "longitude": -104.9995,
                "phone": "+1 303 555 0199"
            }
        }, headers=headers)
        assert proj_res.status_code == 200
        project = proj_res.json()
        proj_id = project["id"]
        print(f"[OK] Created Denver Plumbing project #{proj_id}: {project['name']} in Denver, CO")

        # Add target keyword
        add_kw_res = await client.post("/api/v1/keywords", json={
            "project_id": proj_id,
            "keyword": "emergency plumber denver",
            "target_location": "Denver, CO",
            "search_intent": "Commercial",
            "search_volume": 720
        }, headers=headers)
        assert add_kw_res.status_code == 200
        kw_data = add_kw_res.json()
        kw_id = kw_data["id"]

        # Initial rank must be None (not fabricated)
        assert kw_data["current_rank"] is None
        assert kw_data["ranking_url"] is None
        print(f"[OK] Added keyword #{kw_id}: initial rank is None")

        # Execute 5x5 Geo-Grid scan with unconfigured provider
        GeoGridScanner.clear_cache()
        grid_res = await client.post(f"/api/v1/keywords/{proj_id}/grid/rescan", json={
            "keyword_id": kw_id,
            "keyword": "emergency plumber denver",
            "radius_km": 7.5,
            "grid_size": 5
        }, headers=headers)
        assert grid_res.status_code == 200, f"Grid scan failed: {grid_res.text}"
        scan_data = grid_res.json()

        # Validate Geo-Grid honest unconfigured/failed response
        assert scan_data["scan_status"] == "failed"
        assert scan_data["total_points"] == 25
        assert scan_data["successful_points"] == 0
        assert scan_data["failed_points"] == 25
        assert scan_data["average_rank"] is None
        assert scan_data["local_visibility_pct"] == 0.0

        for pt in scan_data["grid_points"]:
            assert pt["rank"] is None, f"Fabricated rank found: {pt['rank']}"
            assert pt["status"] == "failed"
            assert pt["pin_status"] == "failed"
            assert pt["competitor_ahead"] is None, f"Fabricated competitor found: {pt['competitor_ahead']}"
            assert pt.get("ranking_url") is None, f"Fabricated URL found: {pt.get('ranking_url')}"
            # STRICT REGRESSION ASSERTION: Queenshine domain must NEVER appear
            assert "queenshine" not in str(pt).lower()
            assert "electrical" not in str(pt).lower()

        print("[OK] Denver Plumbing Geo-Grid scan failed closed: 25 failed pins, 0 fake ranks, competitor_ahead is None")

        print("\n=======================================================")
        print(">> TEST 3: DENVER PLUMBING KEYWORD TRACKER (UNCONFIGURED SERP)")
        print("=======================================================")

        # Add target keyword
        add_kw_res = await client.post("/api/v1/keywords", json={
            "project_id": proj_id,
            "keyword": "drain cleaning denver",
            "target_location": "Denver, CO",
            "search_intent": "Commercial",
            "search_volume": 720
        }, headers=headers)
        assert add_kw_res.status_code == 200
        kw_data = add_kw_res.json()
        kw_id = kw_data["id"]

        # Initial rank must be None (not fabricated)
        assert kw_data["current_rank"] is None
        assert kw_data["ranking_url"] is None
        print(f"[OK] Added keyword #{kw_id}: initial rank is None")

        # Perform live rank check on keyword
        check_kw_res = await client.post(f"/api/v1/keywords/{kw_id}/check", headers=headers)
        assert check_kw_res.status_code == 200
        check_data = check_kw_res.json()

        assert check_data["status"] in ["not_configured", "provider_error"]
        assert check_data["current_rank"] is None
        assert check_data["ranking_url"] is None
        print(f"[OK] Keyword single check returned status='{check_data['status']}' with rank=None")

        # Perform check-all on project keywords
        check_all_res = await client.post(f"/api/v1/keywords/{proj_id}/check-all", headers=headers)
        assert check_all_res.status_code == 200
        check_all_data = check_all_res.json()
        assert check_all_data["checked_count"] == 0
        assert check_all_data["error_count"] == 2
        for r in check_all_data["results"]:
            assert r["status"] in ["not_configured", "provider_error"]
            assert r["current_rank"] is None
            assert r["ranking_url"] is None
        print("[OK] Keywords check-all returned honest unconfigured/error count (0 ranked, 2 errors)")

        print("\n=======================================================")
        print(">> TEST 4: PARTIAL GEO-GRID FAILURE (NO DATA INJECTION)")
        print("=======================================================")

        GeoGridScanner.clear_cache()
        partial_prov = PartialMockProvider()
        partial_scan = await GeoGridScanner.scan_grid(
            provider=partial_prov,
            keyword="plumber denver",
            target_domain="milehighdenverplumbing.com",
            center_lat=39.7527,
            center_lng=-104.9995,
            radius_km=7.5,
            grid_size=5
        )

        assert partial_scan["scan_status"] == "completed_with_errors"
        assert partial_scan["total_points"] == 25
        assert partial_scan["successful_points"] == 20
        assert partial_scan["failed_points"] == 5

        # Check that the 5 failed points are strictly failed with NO fabricated competitor
        failed_pts = [p for p in partial_scan["grid_points"] if p["status"] == "failed"]
        assert len(failed_pts) == 5
        for p in failed_pts:
            assert p["rank"] is None
            assert p["competitor_ahead"] is None
            assert p["pin_status"] == "failed"
            assert "rate" in p["error"].lower()

        # Check that successful points have valid competitors from actual SERP
        success_pts = [p for p in partial_scan["grid_points"] if p["status"] != "failed"]
        assert len(success_pts) == 20
        for p in success_pts:
            assert p["competitor_ahead"] == "Real Denver Competitor"

        print("[OK] Partial Geo-Grid scan strictly isolated: 5 failed points have rank=None, competitor_ahead=None")

        print("\n=======================================================")
        print(">> TEST 5: CACHE SAFETY & ZERO MOCK LEAKAGE")
        print("=======================================================")

        # Ensure unconfigured provider results are never cached
        GeoGridScanner.clear_cache()
        unconf_prov = SerpApiProvider(api_key="")
        _ = await GeoGridScanner.scan_grid(
            provider=unconf_prov,
            keyword="plumber denver",
            target_domain="milehighdenverplumbing.com",
            center_lat=39.7527,
            center_lng=-104.9995
        )
        assert len(GeoGridScanner._CACHE) == 0, "Unconfigured failed queries must NEVER populate the Geo-Grid cache!"
        print("[OK] Geo-Grid cache is 100% safe: unconfigured/failed queries are never stored in cache")

    print("\n=======================================================")
    print(">> ALL SERP PRODUCTION INTEGRITY REGRESSION TESTS PASSED 100%!")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(test_serp_production_integrity())
