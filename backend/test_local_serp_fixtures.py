"""
LocalLift — Local SERP Fixture & Aggregation Tests

Tests SERP parsing, domain matching, rank calculation, competitor extraction,
and 5x5 Geo-Grid scanner matrix generation using deterministic offline fixtures.
"""

import pytest
import unittest
from datetime import datetime, timezone

from app.services.serp.base import SERPResponse, SERPItem
from app.services.serp.matcher import DomainMatcher
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.serp.mock_provider import MockSERPProvider


class TestLocalSERPFixtures(unittest.IsolatedAsyncioTestCase):

    def test_01_domain_matching_canonical_normalization(self):
        """DomainMatcher correctly normalizes hostnames and avoids false substring matches."""
        assert DomainMatcher.normalize_host("https://www.example.com/path") == "example.com"
        assert DomainMatcher.normalize_host("http://sub.example.com/") == "sub.example.com"
        assert DomainMatcher.get_registrable_domain("sub.example.com") == "example.com"

        # Matching logic checks
        assert DomainMatcher.matches_target("https://www.example.com/about", "example.com") is True
        assert DomainMatcher.matches_target("https://notexample.com/about", "example.com") is False

    def test_02_find_rank_in_serp_response(self):
        """DomainMatcher identifies accurate rank positions from local pack or organic results."""
        resp = SERPResponse(
            provider="mock",
            keyword="plumber",
            organic_results=[
                SERPItem(position=1, title="City Plumbing", link="https://cityplumbing.com", domain="cityplumbing.com"),
                SERPItem(position=2, title="Target Plumber", link="https://targetplumber.com/services", domain="targetplumber.com")
            ],
            local_pack_results=[
                SERPItem(position=1, title="Target Plumber Local", link="https://targetplumber.com", domain="targetplumber.com")
            ]
        )

        rank, url, serp_type = DomainMatcher.find_rank_in_serp(resp, "targetplumber.com")
        assert rank == 1
        assert serp_type == "Local Pack"
        assert url == "https://targetplumber.com"

    def test_03_grid_scanner_coordinate_generation(self):
        """GeoGridScanner generates accurate 5x5 GPS grid coordinates around a center point."""
        coords = GeoGridScanner.calculate_grid_coordinates(40.7128, -74.0060, radius_km=10.0, grid_size=5)
        assert len(coords) == 25
        assert coords[0]["row"] == 0 and coords[0]["col"] == 0
        assert coords[12]["row"] == 2 and coords[12]["col"] == 2
        assert abs(coords[12]["lat"] - 40.7128) < 0.0001
        assert abs(coords[12]["lng"] - (-74.0060)) < 0.0001

    async def test_04_geo_grid_scanner_aggregation(self):
        """GeoGridScanner scans 25 points and produces accurate visibility and rank averages."""
        preset = [
            {"position": 1, "title": "Top Plumber", "link": "https://targetbiz.com", "type": "local_pack"},
            {"position": 2, "title": "Competitor A", "link": "https://compa.com", "type": "local_pack"}
        ]
        mock_prov = MockSERPProvider(preset_results=preset)

        scan_res = await GeoGridScanner.scan_grid(
            provider=mock_prov,
            keyword="plumber",
            target_domain="targetbiz.com",
            center_lat=40.7128,
            center_lng=-74.0060,
            radius_km=5.0,
            grid_size=5
        )

        assert scan_res["scan_status"] == "completed"
        assert scan_res["total_points"] == 25
        assert scan_res["successful_points"] == 25
        assert scan_res["failed_points"] == 0
        assert scan_res["average_rank"] == 1.0
        assert scan_res["local_visibility_pct"] == 100.0
        assert len(scan_res["grid_points"]) == 25


if __name__ == "__main__":
    unittest.main()
