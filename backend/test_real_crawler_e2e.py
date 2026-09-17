import asyncio
import os
import sys
import time
import socket
import threading
import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Ensure backend root is in python path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.crawler import WebsiteCrawler, SSRFValidator, URLNormalizer, RobotsSitemapService
from app.services.crawl_storage import CrawlStorage
from app.models.audit import AuditJob, AuditJobStatus, SEOAudit, SEOIssue, WebsitePage
from app.models.project import Project, Website
from app.database import AsyncSessionLocal, engine, Base
from sqlalchemy.future import select


class MockWebsiteHandler(BaseHTTPRequestHandler):
    """
    Real HTTP test server handler serving a complete test website.
    """
    def do_GET(self):
        path = self.path

        if path == "/robots.txt":
            content = (
                "User-agent: *\n"
                "Disallow: /private\n"
                "Crawl-delay: 0.1\n"
                f"Sitemap: http://127.0.0.1:{self.server.server_port}/sitemap.xml\n"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
            return

        if path == "/sitemap.xml":
            content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>http://127.0.0.1:{self.server.server_port}/</loc>
  </url>
  <url>
    <loc>http://127.0.0.1:{self.server.server_port}/about</loc>
  </url>
  <url>
    <loc>http://127.0.0.1:{self.server.server_port}/services</loc>
  </url>
</urlset>"""
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
            return

        if path == "/" or path == "/index.html":
            content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Local Lift Test Business - Plumbing & HVAC Services</title>
    <meta name="description" content="Local Lift Test Business provides top-rated emergency plumbing and HVAC services in Austin TX." />
    <link rel="canonical" href="http://127.0.0.1:{self.server.server_port}/" />
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "Plumber",
      "name": "Local Lift Test Business",
      "telephone": "(512) 555-0199",
      "address": {{
        "@type": "PostalAddress",
        "streetAddress": "100 Congress Ave",
        "addressLocality": "Austin",
        "addressRegion": "TX"
      }}
    }}
    </script>
</head>
<body>
    <h1>Local Lift Plumbing & HVAC Services Austin</h1>
    <p>Welcome to our official local website. Call us at (512) 555-0199 for 24/7 service.</p>
    <a href="/about">About Our Company</a>
    <a href="/services">Services</a>
    <a href="/redirect">Redirect Page</a>
    <a href="/missing">Missing Page</a>
    <a href="/private">Private Portal</a>
    <a href="https://example-external.com/test">External Partner</a>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
            return

        if path == "/about":
            content = """<!DOCTYPE html>
<html>
<head>
    <title>About Us - Local Lift Plumbing & HVAC Team</title>
    <meta name="description" content="Learn about our certified local plumbing team serving Austin residential & commercial clients." />
    <link rel="canonical" href="http://127.0.0.1/about" />
</head>
<body>
    <h1>About Local Lift Plumbing & HVAC</h1>
    <p>We have been serving Austin TX for over 15 years with reliable local service.</p>
    <a href="/">Home Page</a>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
            return

        if path == "/services":
            content = """<!DOCTYPE html>
<html>
<head>
    <title>Plumbing & Heating Services - Local Lift</title>
    <meta name="description" content="Comprehensive emergency plumbing, drain cleaning, water heater, and furnace repairs." />
</head>
<body>
    <h1>Commercial & Residential Plumbing Services</h1>
    <p>Complete plumbing solutions for homeowners in Travis County.</p>
    <a href="/">Home</a>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
            return

        if path == "/redirect":
            self.send_response(301)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/about")
            self.end_headers()
            return

        if path == "/private":
            content = "<html><body><h1>403 Forbidden - Disallowed Path</h1></body></html>"
            self.send_response(403)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
            return

        # 404 Not Found for /missing or anything else
        content = "<html><body><h1>404 Page Not Found</h1></body></html>"
        self.send_response(404)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def do_HEAD(self):
        if self.path in ("/", "/about", "/services", "/robots.txt", "/sitemap.xml"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
        elif self.path == "/redirect":
            self.send_response(301)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/about")
            self.end_headers()
        elif self.path == "/private":
            self.send_response(403)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress HTTP server console noise during tests


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def http_server():
    port = get_free_port()
    server = HTTPServer(('127.0.0.1', port), MockWebsiteHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.mark.asyncio
async def test_real_http_crawl_execution(http_server):
    """
    Test 1: Run real SEOCrawler against local HTTP server.
    Verifies actual HTTP fetching, robots disallow enforcement, XML sitemap parsing,
    link graph analysis, and broken link detection.
    """
    crawler = WebsiteCrawler(
        start_url=http_server + "/",
        max_pages=10,
        respect_robots=True,
        crawl_delay_ms=50,
        follow_redirects=True,
        allow_local_dev=True,
        check_external_links=False
    )

    pages = await crawler.crawl()

    assert len(pages) >= 3, f"Expected at least 3 crawled pages, got {len(pages)}"
    urls = [p["url"] for p in pages]
    
    # Check seed page
    seed_page = next((p for p in pages if p["url"].endswith("/")), None)
    assert seed_page is not None
    assert seed_page["status_code"] == 200
    assert "Plumbing" in seed_page["title"]
    assert seed_page["h1"] == "Local Lift Plumbing & HVAC Services Austin"
    assert "Plumber" in seed_page["schema_types"]

    # Verify Robots.txt disallowed path /private was skipped
    assert not any(p["url"].endswith("/private") for p in pages)
    assert any(s["url"].endswith("/private") and s["reason"] == "robots_disallowed" for s in crawler.skipped_urls)

    # Verify broken link /missing was detected
    assert len(crawler.broken_links) > 0
    broken_targets = [b["destination_url"] for b in crawler.broken_links]
    assert any("/missing" in bt for bt in broken_targets)


@pytest.mark.asyncio
async def test_ssrf_security_protections():
    """
    Test 2: Verify SSRF Protection rules against private IPs, cloud metadata, and loopback.
    """
    # 1. AWS Cloud Metadata
    is_safe, msg, _ = SSRFValidator.validate_url("http://169.254.169.254/latest/meta-data/", allow_local_dev=True)
    assert not is_safe
    assert "cloud metadata" in msg.lower() or "blocked" in msg.lower()

    # 2. Localhost without allow_local_dev
    is_safe, msg, _ = SSRFValidator.validate_url("http://127.0.0.1:8000/api", allow_local_dev=False)
    assert not is_safe
    assert "SSRF_BLOCKED" in msg

    # 3. Localhost with allow_local_dev enabled (in non-prod)
    is_safe, msg, _ = SSRFValidator.validate_url("http://127.0.0.1:8000/api", allow_local_dev=True)
    assert is_safe

    # 4. Non-HTTP scheme
    is_safe, msg, _ = SSRFValidator.validate_url("file:///etc/passwd", allow_local_dev=True)
    assert not is_safe
    assert "UNSAFE_SCHEME" in msg or "INVALID_URL" in msg


@pytest.mark.asyncio
async def test_follow_redirects_policy(http_server):
    """
    Test 3: Verify follow_redirects option behavior.
    """
    # When follow_redirects=False:
    crawler_no_redirect = WebsiteCrawler(
        start_url=http_server + "/redirect",
        max_pages=2,
        respect_robots=False,
        follow_redirects=False,
        allow_local_dev=True
    )
    pages_no_redirect = await crawler_no_redirect.crawl()
    assert len(pages_no_redirect) == 1
    assert pages_no_redirect[0]["status_code"] == 301
    assert pages_no_redirect[0]["redirect_location"].endswith("/about")

    # When follow_redirects=True:
    crawler_with_redirect = WebsiteCrawler(
        start_url=http_server + "/redirect",
        max_pages=2,
        respect_robots=False,
        follow_redirects=True,
        allow_local_dev=True
    )
    pages_with_redirect = await crawler_with_redirect.crawl()
    assert len(pages_with_redirect) >= 1
    assert pages_with_redirect[0]["status_code"] == 200
    assert pages_with_redirect[0]["url"].endswith("/about")
    assert len(crawler_with_redirect.redirect_chains) > 0


@pytest.mark.asyncio
async def test_multi_tenant_storage_isolation():
    """
    Test 4: Verify multi-tenant storage directory isolation.
    Project A (ID 101) must never read or write to Project B (ID 202).
    """
    proj_a_id = 101
    proj_b_id = 202
    sess_a_id = 1001
    sess_b_id = 2002

    # Save artifacts for Project A
    ok_a, msg_a = CrawlStorage.save_crawl_session_artifacts(
        project_id=proj_a_id,
        session_id=sess_a_id,
        metadata={"project": "A", "session": sess_a_id},
        pages=[{"url": "http://example-a.com", "status_code": 200}],
        issues=[{"title": "Issue A"}],
        internal_links=[],
        external_links=[],
        broken_links=[],
        link_records=[],
        summary={"score": 85}
    )
    assert ok_a, msg_a

    # Save artifacts for Project B
    ok_b, msg_b = CrawlStorage.save_crawl_session_artifacts(
        project_id=proj_b_id,
        session_id=sess_b_id,
        metadata={"project": "B", "session": sess_b_id},
        pages=[{"url": "http://example-b.com", "status_code": 200}],
        issues=[{"title": "Issue B"}],
        internal_links=[],
        external_links=[],
        broken_links=[],
        link_records=[],
        summary={"score": 92}
    )
    assert ok_b, msg_b

    # Verify Project A storage directory
    dir_a = CrawlStorage.get_project_storage_dir(proj_a_id, sess_a_id)
    dir_b = CrawlStorage.get_project_storage_dir(proj_b_id, sess_b_id)
    assert str(proj_a_id) in str(dir_a)
    assert str(proj_b_id) in str(dir_b)
    assert str(proj_b_id) not in str(dir_a)

    # Verify loading latest artifact reads project A's data only
    latest_summary_a = CrawlStorage.load_latest_artifact(proj_a_id, "summary.json")
    latest_summary_b = CrawlStorage.load_latest_artifact(proj_b_id, "summary.json")

    assert latest_summary_a["score"] == 85
    assert latest_summary_b["score"] == 92


@pytest.mark.asyncio
async def test_job_cancellation_flow(http_server):
    """
    Test 5: Verify cancellation flow stops crawling cleanly.
    """
    is_cancelled = False
    def cancel_check():
        return is_cancelled

    crawler = WebsiteCrawler(
        start_url=http_server + "/",
        max_pages=100,
        allow_local_dev=True,
        cancellation_check=cancel_check
    )

    # Trigger cancellation immediately
    is_cancelled = True
    pages = await crawler.crawl()
    assert len(pages) == 0  # Cancelled before completing crawl
