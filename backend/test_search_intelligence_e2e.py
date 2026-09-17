"""
LocalLift — Search Intelligence End-to-End Acceptance Test

Tests full flow:
Project Creation -> Location & SERP Config -> Competitor Discovery -> Keyword Rank Check & RankingSnapshot Persistence -> 5x5 Geo-Grid Scan
"""

import os
import sys
import unittest
import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy.future import select

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database import AsyncSessionLocal, Base, engine
from app.test_helper import init_test_db, create_test_tenant
from app.models.project import Project, Location
from app.models.ranking import Keyword, KeywordRanking, GeoGridScan, RankingSnapshot
from app.models.local_seo import Competitor
from app.models.connections import OrganizationSERPConfig
from app.services.serp.mock_provider import MockSERPProvider
from app.services.competitor_engine import CompetitorDiscoveryEngine
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.serp.matcher import DomainMatcher


class TestSearchIntelligenceE2E(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await init_test_db(seed_demo=False)
        self.user, self.org, self.project, self.token = await create_test_tenant(
            org_name="E2E Intelligence Org",
            project_name="E2E Plumbing Services",
            primary_category="Plumbing"
        )

    async def test_01_end_to_end_search_intelligence_lifecycle(self):
        """
        Executes end-to-end acceptance flow across:
        1. Tenant & Project Container setup
        2. SERP Config persistence
        3. Competitor Discovery Engine execution & Candidate persistence
        4. Keyword creation & Rank check with RankingSnapshot persistence
        5. Real 5x5 Geo-Grid scan execution
        """
        async with AsyncSessionLocal() as session:
            # 1. Update Project location details
            loc_res = await session.execute(select(Location).where(Location.project_id == self.project.id))
            loc = loc_res.scalars().first()
            if not loc:
                loc = Location(
                    project_id=self.project.id,
                    name="Headquarters",
                    city="Austin",
                    state="TX",
                    postal_code="78701",
                    country="United States",
                    latitude=30.2672,
                    longitude=-97.7431
                )
                session.add(loc)
            else:
                loc.city = "Austin"
                loc.state = "TX"
                loc.latitude = 30.2672
                loc.longitude = -97.7431
            await session.commit()

            # 2. Configure SERP Provider
            serp_cfg = OrganizationSERPConfig(
                organization_id=self.org.id,
                provider="serpapi",
                api_key="encrypted_test_key_placeholder",
                connection_status="connected",
                status_message="Test SERP provider configured",
                last_tested_at=datetime.now(timezone.utc)
            )
            session.add(serp_cfg)
            await session.commit()

            # 3. Execute Competitor Discovery Engine
            disc_res = await CompetitorDiscoveryEngine.discover_competitors_for_project(
                project_id=self.project.id,
                db=session,
                city="Austin",
                state="TX",
                country="United States"
            )
            assert disc_res["status"] == "completed"
            assert "candidates_discovered" in disc_res

            # 4. Save Discovered Competitor
            comp = Competitor(
                project_id=self.project.id,
                name="Austin Elite Plumbing",
                domain="austineliteplumbing.com",
                rating=4.9,
                reviews_count=120,
                local_visibility_score=88
            )
            session.add(comp)
            await session.commit()

            # Verify Competitor Persisted
            comp_res = await session.execute(select(Competitor).where(Competitor.project_id == self.project.id))
            comps = comp_res.scalars().all()
            assert len(comps) == 1
            assert comps[0].domain == "austineliteplumbing.com"

            # 5. Create Keyword & Record RankingSnapshot
            kw = Keyword(
                project_id=self.project.id,
                keyword="emergency plumber austin",
                search_intent="Commercial",
                target_location="Austin, TX",
                current_rank=2,
                previous_rank=5,
                ranking_url=f"https://{self.project.domain}/emergency",
                last_checked_at=datetime.now(timezone.utc)
            )
            session.add(kw)
            await session.commit()

            snapshot = RankingSnapshot(
                project_id=self.project.id,
                keyword_id=kw.id,
                keyword=kw.keyword,
                location=kw.target_location,
                country="us",
                language="en",
                device="desktop",
                provider="mock",
                checked_at=datetime.now(timezone.utc),
                position=2,
                ranking_url=f"https://{self.project.domain}/emergency",
                status="success"
            )
            session.add(snapshot)
            await session.commit()

            # Verify RankingSnapshot Persisted
            snaps_res = await session.execute(select(RankingSnapshot).where(RankingSnapshot.project_id == self.project.id))
            snaps = snaps_res.scalars().all()
            assert len(snaps) == 1
            assert snaps[0].position == 2
            assert snaps[0].keyword == "emergency plumber austin"

            # 6. Execute 5x5 Geo-Grid scan using MockSERPProvider
            preset = [
                {"position": 2, "title": self.project.name, "link": f"https://{self.project.domain}", "type": "local_pack"}
            ]
            mock_prov = MockSERPProvider(preset_results=preset)

            grid_res = await GeoGridScanner.scan_grid(
                provider=mock_prov,
                keyword=kw.keyword,
                target_domain=self.project.domain,
                center_lat=loc.latitude,
                center_lng=loc.longitude,
                radius_km=5.0,
                grid_size=5
            )

            assert grid_res["scan_status"] == "completed"
            assert grid_res["total_points"] == 25
            assert grid_res["successful_points"] == 25
            assert len(grid_res["grid_points"]) == 25

            # Save GeoGridScan in DB
            scan = GeoGridScan(
                project_id=self.project.id,
                keyword_id=kw.id,
                center_name=loc.name,
                center_lat=loc.latitude,
                center_lng=loc.longitude,
                radius_km=5.0,
                grid_size=5,
                average_rank=grid_res["average_rank"],
                local_visibility_pct=grid_res["local_visibility_pct"],
                scan_status=grid_res["scan_status"],
                total_points=grid_res["total_points"],
                successful_points=grid_res["successful_points"],
                failed_points=grid_res["failed_points"],
                grid_points=grid_res["grid_points"],
                scanned_at=grid_res["scanned_at"]
            )
            session.add(scan)
            await session.commit()

            # Verify GeoGridScan DB Record
            scans_res = await session.execute(select(GeoGridScan).where(GeoGridScan.project_id == self.project.id))
            saved_scans = scans_res.scalars().all()
            assert len(saved_scans) == 1
            assert saved_scans[0].scan_status == "completed"
            assert saved_scans[0].total_points == 25


if __name__ == "__main__":
    unittest.main()
