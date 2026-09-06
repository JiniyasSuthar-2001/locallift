import asyncio
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.serp.mock_provider import MockSERPProvider

def test_grid_matrix_generation():
    center_lat = -27.4698
    center_lng = 153.0251
    radius_km = 10.0
    grid_size = 5

    points = GeoGridScanner.calculate_grid_coordinates(
        center_lat=center_lat,
        center_lng=center_lng,
        radius_km=radius_km,
        grid_size=grid_size
    )

    assert len(points) == 25
    center_point = next(p for p in points if p["row"] == 2 and p["col"] == 2)
    assert center_point["lat"] == center_lat
    assert center_point["lng"] == center_lng

def test_geogrid_live_scan_execution():
    async def _test():
        provider = MockSERPProvider()
        res = await GeoGridScanner.scan_grid(
            provider=provider,
            keyword="electrician brisbane",
            target_domain="queenshineelectricals.com.au",
            center_lat=-27.4698,
            center_lng=153.0251,
            radius_km=10.0,
            grid_size=5,
            concurrency_limit=3
        )

        assert res["total_points"] == 25
        assert res["successful_points"] == 25
        assert res["scan_status"] == "completed"
        assert res["average_rank"] > 0
        assert res["local_visibility_pct"] > 0
        assert len(res["grid_points"]) == 25

        # Verify caching works on second run
        cached_res = await GeoGridScanner.scan_grid(
            provider=provider,
            keyword="electrician brisbane",
            target_domain="queenshineelectricals.com.au",
            center_lat=-27.4698,
            center_lng=153.0251,
            radius_km=10.0,
            grid_size=5
        )
        assert cached_res["total_points"] == 25

    asyncio.run(_test())

def test_geogrid_partial_failure_resilience():
    GeoGridScanner.clear_cache()
    async def _test():
        # Provider that returns error
        err_provider = MockSERPProvider(simulate_error="rate_limit")
        res = await GeoGridScanner.scan_grid(
            provider=err_provider,
            keyword="electrician brisbane",
            target_domain="queenshineelectricals.com.au",
            center_lat=-27.4698,
            center_lng=153.0251,
            radius_km=10.0,
            grid_size=5
        )

        assert res["total_points"] == 25
        assert res["failed_points"] == 25
        assert res["scan_status"] == "failed"
        for pt in res["grid_points"]:
            assert pt["status"] == "failed"
            assert pt["error"] is not None

    asyncio.run(_test())

def run_all_tests():
    test_grid_matrix_generation()
    test_geogrid_live_scan_execution()
    test_geogrid_partial_failure_resilience()
    print("[OK] All GeoGrid Scanner automated test suites PASSED successfully!")

if __name__ == "__main__":
    run_all_tests()
