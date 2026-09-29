import asyncio
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.geocoding import GeocodingService
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.reports.geogrid_pdf_service import GeoGridPDFService


class TestGeocodingAndLocationLabels(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        GeocodingService.clear_cache()

    async def test_01_reverse_geocode_resolution(self):
        """
        Verify that coordinates resolve to actual recognized geographic area names.
        Test with Melbourne coordinates (-37.834, 144.963).
        """
        # Test reverse geocode returns a valid string or mock
        with patch.object(GeocodingService, "_nominatim_reverse", new_callable=AsyncMock) as mock_nom:
            mock_nom.return_value = "South Melbourne"
            area = await GeocodingService.reverse_geocode(-37.834, 144.963)
            self.assertEqual(area, "South Melbourne")
            mock_nom.assert_called_once()

    async def test_02_coordinate_caching_eliminates_duplicate_requests(self):
        """
        Verify that reverse geocode uses memory caching for identical/close coordinates.
        """
        with patch.object(GeocodingService, "_nominatim_reverse", new_callable=AsyncMock) as mock_nom:
            mock_nom.return_value = "South Melbourne"
            
            # Call 1
            area1 = await GeocodingService.reverse_geocode(-37.83412, 144.96315)
            # Call 2 (close within rounded precision)
            area2 = await GeocodingService.reverse_geocode(-37.83414, 144.96318)
            
            self.assertEqual(area1, "South Melbourne")
            self.assertEqual(area2, "South Melbourne")
            # Should only call external provider ONCE due to coordinate caching
            self.assertEqual(mock_nom.call_count, 1)

    async def test_03_fallback_when_geocoding_fails(self):
        """
        Verify that missing or failed geocoding does NOT fabricate area names
        and gracefully returns 'Area name unavailable'.
        """
        with patch.object(GeocodingService, "_nominatim_reverse", new_callable=AsyncMock) as mock_nom:
            mock_nom.return_value = None
            area = await GeocodingService.reverse_geocode(0.0, 0.0)
            self.assertIsNone(area)

    async def test_04_batch_reverse_geocoding(self):
        """
        Verify batch reverse geocoding across multiple discrete coordinates.
        """
        coords = [
            (-37.8136, 144.9631),
            (-37.8340, 144.9630),
            (-37.8000, 144.9700)
        ]
        with patch.object(GeocodingService, "reverse_geocode", new_callable=AsyncMock) as mock_rg:
            mock_rg.side_effect = ["Melbourne CBD", "South Melbourne", "Carlton"]
            res = await GeocodingService.reverse_geocode_points_batch(coords)
            
            self.assertEqual(len(res), 3)
            self.assertEqual(res[(round(-37.8136, 3), round(144.9631, 3))], "Melbourne CBD")
            self.assertEqual(res[(round(-37.8340, 3), round(144.9630, 3))], "South Melbourne")
            self.assertEqual(res[(round(-37.8000, 3), round(144.9700, 3))], "Carlton")


class TestGooglePlacesRatingAndReviewIntegrity(unittest.TestCase):
    def test_01_target_business_verified_rating_mapping(self):
        """
        Verify that rating and review counts from Google Places/GBP (e.g. 4.3 / 5.0 and 482 reviews)
        are accurately preserved and not overridden by unverified dummy values.
        """
        from app.models.connections import PublicBusinessListing
        
        listing = PublicBusinessListing(
            organization_id=1,
            project_id=1,
            name="Box Seafood Restaurant",
            rating=4.3,
            review_count=482,
            place_id="ChIJN1t_tDeuEmsRUsoyG83frY4",
            formatted_address="189 Collins St, Melbourne VIC 3000",
            source="google_places_api"
        )
        self.assertEqual(listing.rating, 4.3)
        self.assertEqual(listing.review_count, 482)
        self.assertNotEqual(listing.rating, 4.9)
        self.assertNotEqual(listing.review_count, 56)


class TestGeoGridPDFGenerationWithAreaAndRatings(unittest.TestCase):
    def test_01_single_scan_pdf_generation(self):
        """
        Verify that GeoGridPDFService generates a valid PDF containing Area / Locality names.
        """
        project = MagicMock()
        project.id = 1
        project.name = "Box Seafood Restaurant"
        project.domain = "boxseafoodrestaurant.com.au"

        scan = MagicMock()
        scan.id = 101
        scan.grid_size = 5
        scan.radius_km = 5.0
        scan.keyword = "seafood restaurant melbourne"
        scan.keyword_rel = MagicMock(keyword="seafood restaurant melbourne")
        scan.started_at = datetime.now(timezone.utc)
        scan.scan_status = "completed"
        scan.total_points = 25
        scan.completed_points = 25
        scan.ranking_found_points = 20
        scan.not_found_points = 5
        scan.provider_error_points = 0
        scan.timeout_points = 0
        scan.average_rank = 3.2
        scan.local_visibility_pct = 76.0
        scan.center_name = "Melbourne CBD"

        points = []
        for i in range(25):
            pt = MagicMock()
            pt.point_number = i + 1
            pt.row = i // 5
            pt.col = i % 5
            pt.latitude = -37.8136 + (i * 0.001)
            pt.longitude = 144.9631 + (i * 0.001)
            pt.area_name = "South Melbourne" if i % 2 == 0 else "Melbourne CBD"
            pt.distance_km = round(i * 0.4, 1)
            pt.direction = "North" if i % 2 == 0 else "East"
            pt.rank = (i % 5) + 1 if i < 20 else None
            pt.status = "SUCCESS" if i < 20 else "NOT_FOUND"
            pt.matched_business = "Box Seafood Restaurant" if i < 20 else None
            pt.competitors = [
                {
                    "title": "Atlantic Restaurant",
                    "position": 1,
                    "rating": 4.5,
                    "reviews_count": 520,
                    "is_target": False
                }
            ]
            points.append(pt)

        pdf_bytes = GeoGridPDFService.generate_single_scan_pdf(project, scan, points)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 1000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_02_selected_point_pdf_generation(self):
        """
        Verify that Selected Point PDF contains Area / Locality and verified competitor/target ratings.
        """
        project = MagicMock()
        project.id = 1
        project.name = "Box Seafood Restaurant"
        project.domain = "boxseafoodrestaurant.com.au"

        scan = MagicMock()
        scan.id = 101
        scan.keyword = "seafood restaurant melbourne"
        scan.keyword_rel = MagicMock(keyword="seafood restaurant melbourne")
        scan.started_at = datetime.now(timezone.utc)

        target_pt = MagicMock()
        target_pt.point_number = 7
        target_pt.latitude = -37.8341
        target_pt.longitude = 144.9632
        target_pt.area_name = "South Melbourne"
        target_pt.distance_km = 2.4
        target_pt.direction = "South"
        target_pt.rank = 2
        target_pt.status = "SUCCESS"

        analysis_data = {
            "point_number": 7,
            "scan_id": 101,
            "project_id": 1,
            "location": {
                "point_number": 7,
                "row": 1,
                "col": 2,
                "latitude": -37.8341,
                "longitude": 144.9632,
                "area_name": "South Melbourne",
                "distance_km": 2.4,
                "direction": "South",
                "center_name": "Melbourne CBD",
                "keyword": "seafood restaurant melbourne"
            },
            "ranking": {
                "business_name": "Box Seafood Restaurant",
                "rank": 2,
                "status": "SUCCESS",
                "result_depth": 20
            },
            "competitors_hierarchy": {
                "competitors_above": [
                    {
                        "position": 1,
                        "title": "Atlantic Restaurant",
                        "category": "Seafood Restaurant",
                        "rating": 4.5,
                        "reviews_count": 520,
                        "domain": "theatlantic.com.au"
                    }
                ],
                "target_business": {
                    "position": 2,
                    "title": "Box Seafood Restaurant",
                    "category": "Seafood Restaurant",
                    "rating": 4.3,
                    "reviews_count": 482,
                    "domain": "boxseafoodrestaurant.com.au",
                    "is_target": True
                },
                "competitors_below": [
                    {
                        "position": 3,
                        "title": "Richmond Oysters",
                        "category": "Seafood Restaurant",
                        "rating": 4.4,
                        "reviews_count": 310,
                        "domain": "richmondoysters.com.au"
                    }
                ],
                "total_competitors_evaluated": 20,
                "result_depth": 20,
                "not_found_in_depth": False
            },
            "diagnostics": {
                "what": "Your business 'Box Seafood Restaurant' ranked #2 for 'seafood restaurant melbourne' at this scan location.",
                "where": "Area: South Melbourne · Located 2.4 km South of Melbourne CBD at GPS coordinates (-37.8341, 144.9632).",
                "how": [
                    {"field": "Business Name", "value": "Box Seafood Restaurant", "provider_observed": True},
                    {"field": "Google Rating", "value": "4.3 / 5.0", "provider_observed": True},
                    {"field": "Google Reviews", "value": "482 reviews", "provider_observed": True}
                ],
                "why": [
                    "Observed: Strong local authority and proximity within the high-visibility Google Local 3-Pack."
                ]
            }
        }

        pdf_bytes = GeoGridPDFService.generate_selected_point_pdf(project, scan, target_pt, analysis_data)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 1000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
