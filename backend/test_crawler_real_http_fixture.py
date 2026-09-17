import asyncio
import time
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import pytest
from app.services.crawler import WebsiteCrawler, URLNormalizer, SSRFValidator

class FixtureHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress HTTP server stderr logs during pytest

    def do_GET(self):
        parsed = self.path
        if parsed == "/":
            body = f"""<!DOCTYPE html>
<html>
<head><title>Test Fixture Home Page - LocalLift Audit Engine</title><meta name="description" content="Official home page of test fixture local HTTP server for real crawler testing." /></head>
<body>
<h1>Welcome to Test Fixture Service</h1>
<p>This is a real HTTP test fixture server providing actual web server responses for forensic crawler verification.</p>
<a href="/about">About Us Page</a>
<a href="/services">Our Services Page</a>
<a href="/missing">Missing Page (404)</a>
<a href="/broken-link">Permanently Gone Link (410)</a>
<a href="/redirect">Redirect Page (301)</a>
<a href="/js-route">JavaScript SPA Route</a>
<a href="/large-response">Large File Response</a>
<a href="/admin">Disallowed Admin Path</a>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        elif parsed == "/about":
            body = """<!DOCTYPE html>
<html>
<head><title>About Us - LocalLift Test Fixture Platform</title><meta name="description" content="Learn about our team, mission, and localized software services." /></head>
<body>
<h1>About Our Platform</h1>
<p>Detailed information about our local engineering services and features.</p>
<a href="/">Home</a>
<a href="/services">Services</a>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        elif parsed == "/services":
            body = """<!DOCTYPE html>
<html>
<head><title>Our Professional Services - LocalLift Fixture</title><meta name="description" content="Explore local SEO audit, citation management, and rank tracking services." /></head>
<body>
<h1>Our Local SEO Services</h1>
<p>We provide comprehensive search engine optimization and audit tools.</p>
<a href="/">Back to Home</a>
<a href="/missing">Broken Link Check Target</a>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        elif parsed == "/robots.txt":
            body = """User-agent: *
Disallow: /admin
Crawl-delay: 0
Sitemap: /sitemap.xml
"""
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        elif parsed == "/sitemap.xml":
            port = self.server.server_port
            body = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>http://127.0.0.1:{port}/</loc></url>
  <url><loc>http://127.0.0.1:{port}/about</loc></url>
  <url><loc>http://127.0.0.1:{port}/services</loc></url>
</urlset>"""
            self.send_response(200)
            self.send_header("Content-Type", "application/xml; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        elif parsed == "/js-route":
            body = """<!DOCTYPE html>
<html>
<head><title>SPA Shell Route</title></head>
<body>
<div id="app"></div>
<script>console.log("Single Page Application shell");</script>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        elif parsed == "/redirect":
            self.send_response(301)
            self.send_header("Location", "/about")
            self.end_headers()

        elif parsed == "/redirect-chain":
            self.send_response(302)
            self.send_header("Location", "/redirect-chain-2")
            self.end_headers()

        elif parsed == "/redirect-chain-2":
            self.send_response(302)
            self.send_header("Location", "/redirect-chain-3")
            self.end_headers()

        elif parsed == "/redirect-chain-3":
            self.send_response(302)
            self.send_header("Location", "/redirect-chain-4")
            self.end_headers()

        elif parsed == "/redirect-chain-4":
            self.send_response(302)
            self.send_header("Location", "/redirect-chain-5")
            self.end_headers()

        elif parsed == "/redirect-chain-5":
            self.send_response(302)
            self.send_header("Location", "/redirect-chain-6")
            self.end_headers()

        elif parsed == "/redirect-chain-6":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>Chain End</body></html>")

        elif parsed == "/redirect-loop-a":
            self.send_response(302)
            self.send_header("Location", "/redirect-loop-b")
            self.end_headers()

        elif parsed == "/redirect-loop-b":
            self.send_response(302)
            self.send_header("Location", "/redirect-loop-a")
            self.end_headers()

        elif parsed == "/missing":
            self.send_response(404)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>404 Page Not Found</body></html>")

        elif parsed == "/broken-link":
            self.send_response(410)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>410 Resource Gone</body></html>")

        elif parsed == "/large-response":
            self.send_response(200)
            self.send_header("Content-Length", "15000000")  # 15MB > 10MB limit
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"A" * 1000)

        elif parsed == "/slow-response":
            time.sleep(2.0)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>Slow Page</body></html>")

        else:
            self.send_response(404)
            self.end_headers()

    def do_HEAD(self):
        parsed = self.path
        if parsed in ("/", "/about", "/services", "/robots.txt", "/sitemap.xml", "/js-route"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
        elif parsed == "/missing":
            self.send_response(404)
            self.end_headers()
        elif parsed == "/broken-link":
            self.send_response(410)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


def get_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="module")
def http_server_fixture():
    port = get_free_port()
    server = HTTPServer(("127.0.0.1", port), FixtureHTTPHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    server.shutdown()
    server.server_close()


def test_crawler_real_http_fixture_execution(http_server_fixture):
    async def _test():
        start_url = http_server_fixture
        crawler = WebsiteCrawler(
            start_url=start_url,
            max_pages=10,
            respect_robots=True,
            allow_local_dev=True,
            check_external_links=True
        )

        pages = await crawler.crawl()
        assert len(pages) > 0

        # Verify real status codes
        status_codes = [p["status_code"] for p in pages]
        assert 200 in status_codes

        # Verify robots.txt inspection
        assert crawler.robots_service.fetch_status == "200_ok"

        # Verify link graph verification
        assert crawler.broken_link_check_status == "completed"
        assert crawler.links_checked_count > 0

        # Verify broken links identified with exact status codes (404, 410)
        broken_destinations = [b["destination_url"] for b in crawler.broken_links]
        assert any("/missing" in d or "/broken-link" in d for d in broken_destinations)

        # Verify detailed link records structure
        assert len(crawler.link_records) > 0
        rec = crawler.link_records[0]
        assert "source_url" in rec
        assert "destination_url" in rec
        assert "status_code" in rec
        assert "verification_state" in rec

    asyncio.run(_test())


def test_crawler_redirect_chain_and_limits(http_server_fixture):
    async def _test():
        start_url = f"{http_server_fixture}/redirect-chain"
        crawler = WebsiteCrawler(
            start_url=start_url,
            max_pages=5,
            allow_local_dev=True
        )
        pages = await crawler.crawl()
        # Chain of 6 redirects exceeds SERVER_MAX_REDIRECTS (5)
        assert crawler.redirect_limit_reached is True

    asyncio.run(_test())


def test_crawler_cancellation(http_server_fixture):
    async def _test():
        cancel_requested = False

        def check_cancel():
            return cancel_requested

        crawler = WebsiteCrawler(
            start_url=http_server_fixture,
            max_pages=50,
            allow_local_dev=True,
            cancellation_check=check_cancel
        )

        # Trigger cancellation
        cancel_requested = True
        pages = await crawler.crawl()
        # Crawler stopped early due to cancellation
        assert len(pages) <= 1

    asyncio.run(_test())
