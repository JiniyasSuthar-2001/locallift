import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import unittest
import json
from datetime import datetime, timezone
from app.services.crawler import URLNormalizer, SSRFValidator, RobotsSitemapService, WebsiteCrawler
from app.models.audit import AuditJob, AuditJobStatus, SEOAudit, WebsitePage
from app.models.project import Project, Website, Location
from app.models.user import User, Organization
from app.database import AsyncSessionLocal, engine, Base
from app.test_helper import init_test_db

import uuid

class TestCrawlerAndJobSystem(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_test_db(seed_demo=False)

        rand_suffix = uuid.uuid4().hex[:6]
        async with AsyncSessionLocal() as session:
            # Create Test Org & User with unique identifiers
            org = Organization(name=f"Test Crawler Org {rand_suffix}", slug=f"test-crawler-org-{rand_suffix}")
            session.add(org)
            await session.flush()

            user = User(
                email=f"crawler_tester_{rand_suffix}@example.com",
                hashed_password="fakehashedpassword",
                full_name="Crawler Tester",
                is_active=True
            )
            session.add(user)
            await session.flush()

            # Create Test Project
            proj = Project(
                organization_id=org.id,
                name="Test Local Business",
                domain="example.com",
                primary_category="Plumber",
                country="United States"
            )
            session.add(proj)
            await session.flush()

            loc = Location(
                project_id=proj.id,
                name="Main Plumbing Store",
                address="123 Main St",
                city="Austin",
                state="TX",
                postal_code="78701",
                country="United States",
                phone="+15125550199"
            )
            session.add(loc)
            await session.commit()

            self.org_id = org.id
            self.user_id = user.id
            self.project_id = proj.id

    async def test_01_url_normalizer(self):
        raw = "  HTTP://WWW.Example.COM:80/path/to/page/?b=2&a=1#section1  "
        normalized = URLNormalizer.normalize(raw)
        self.assertEqual(normalized, "http://www.example.com/path/to/page/?a=1&b=2")

        origin = URLNormalizer.get_origin("https://sub.example.com/foo/bar")
        self.assertEqual(origin, "https://sub.example.com")

        self.assertTrue(URLNormalizer.is_same_domain("https://example.com", "http://www.example.com/about"))
        self.assertFalse(URLNormalizer.is_same_domain("https://example.com", "https://google.com"))

    async def test_02_ssrf_validator_blocks_internal_networks(self):
        # 127.0.0.1
        safe, msg, *_ = SSRFValidator.validate_url("http://127.0.0.1/admin")
        self.assertFalse(safe)
        self.assertIn("SSRF_BLOCKED", msg)

        # localhost
        safe, msg, *_ = SSRFValidator.validate_url("http://localhost:8080")
        self.assertFalse(safe)

        # Cloud Metadata (169.254.169.254)
        safe, msg, *_ = SSRFValidator.validate_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("SSRF_BLOCKED", msg)

        # Private IPv4 (10.0.0.1)
        safe, msg, *_ = SSRFValidator.validate_url("http://10.0.0.1/secret")
        self.assertFalse(safe)

    async def test_03_robots_disallow_rules(self):
        robots = RobotsSitemapService()
        robots.robot_parser.parse([
            "User-agent: *",
            "Disallow: /admin/",
            "Disallow: /private-page"
        ])

        self.assertFalse(robots.is_allowed("https://example.com/admin/dashboard"))
        self.assertTrue(robots.is_allowed("https://example.com/public-services"))

    async def test_04_audit_job_lifecycle_persistence(self):
        async with AsyncSessionLocal() as session:
            job = AuditJob(
                project_id=self.project_id,
                organization_id=self.org_id,
                job_type="website_audit",
                status=AuditJobStatus.QUEUED,
                progress=0.0,
                current_stage="Job queued",
                start_url="https://example.com"
            )
            session.add(job)
            await session.commit()
            job_id = job.id

        # Update to RUNNING -> CRAWLING -> COMPLETED
        async with AsyncSessionLocal() as session:
            from sqlalchemy.future import select
            j_res = await session.execute(select(AuditJob).where(AuditJob.id == job_id))
            job = j_res.scalars().first()
            self.assertIsNotNone(job)
            self.assertIn(job.status, (AuditJobStatus.QUEUED, AuditJobStatus.QUEUED.value))

            # Update progress
            job.status = AuditJobStatus.CRAWLING
            job.progress = 45.0
            job.current_stage = "Crawling page 3 of 15"
            await session.commit()

        async with AsyncSessionLocal() as session:
            from sqlalchemy.future import select
            j_res = await session.execute(select(AuditJob).where(AuditJob.id == job_id))
            job = j_res.scalars().first()
            self.assertIn(job.status, (AuditJobStatus.CRAWLING, AuditJobStatus.CRAWLING.value))
            self.assertEqual(job.progress, 45.0)

            # Finish job
            job.status = AuditJobStatus.COMPLETED
            job.progress = 100.0
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()

        async with AsyncSessionLocal() as session:
            from sqlalchemy.future import select
            j_res = await session.execute(select(AuditJob).where(AuditJob.id == job_id))
            job = j_res.scalars().first()
            self.assertIn(job.status, (AuditJobStatus.COMPLETED, AuditJobStatus.COMPLETED.value))
            self.assertIsNotNone(job.completed_at)

    async def test_05_crawler_execution_safety_and_links(self):
        crawler = WebsiteCrawler(start_url="https://example.com", max_pages=3)
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Austin Plumbing Pros - Emergency 24/7 Plumbers</title>
            <meta name="description" content="Top rated Austin plumbers offering 24/7 emergency pipe repair, drain cleaning, and water heater installation.">
            <link rel="canonical" href="https://example.com/" />
        </head>
        <body>
            <h1>Austin Plumbing Pros</h1>
            <h2>Emergency Drain Cleaning Services</h2>
            <p>Call us today at (512) 555-0199 for fast local plumbing assistance in Austin TX.</p>
            <a href="/services">Our Services</a>
            <a href="https://example.com/contact">Contact Us</a>
            <a href="https://external-directory.com/listing">External Directory</a>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Plumber",
                "name": "Austin Plumbing Pros",
                "telephone": "+15125550199"
            }
            </script>
        </body>
        </html>
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        page_data, extracted_links = crawler._analyze_html_and_extract_links(
            url="https://example.com/",
            status_code=200,
            soup=soup,
            load_time_ms=120,
            source="manual_seed"
        )

        self.assertEqual(page_data["title"], "Austin Plumbing Pros - Emergency 24/7 Plumbers")
        self.assertEqual(page_data["h1"], "Austin Plumbing Pros")
        self.assertIn("Plumber", page_data["schema_types"])
        self.assertEqual(len(extracted_links), 3)

        internal_links = [l for l in extracted_links if l["is_internal"]]
        external_links = [l for l in extracted_links if not l["is_internal"]]
        self.assertEqual(len(internal_links), 2)
        self.assertEqual(len(external_links), 1)

if __name__ == "__main__":
    unittest.main()
