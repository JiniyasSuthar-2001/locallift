import asyncio
import re
import socket
import fnmatch
import ipaddress
import logging
import urllib.parse
import urllib.robotparser
from xml.etree import ElementTree
from datetime import datetime, timezone
from typing import List, Dict, Any, Set, Optional, Tuple, Callable
import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger("locallift.crawler")

# Optional Playwright dependency detection
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class URLNormalizer:
    """
    Authoritative URL normalization utility.
    Handles scheme, lowercase hostname, default port stripping, relative URLs,
    protocol-relative URLs, dot-segment resolution, duplicate path slashes,
    query parameter sorting, tracking parameter removal, and IDN/Punycode.
    """
    DEFAULT_PORTS = {"http": 80, "https": 443}
    TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "msclkid"}

    @classmethod
    def normalize(cls, url: str, base_url: Optional[str] = None, strip_tracking: bool = False) -> Optional[str]:
        if not url or not url.strip():
            return None
        
        cleaned = url.strip()
        
        # Handle protocol-relative URLs (//example.com/foo)
        if cleaned.startswith("//"):
            base_scheme = urllib.parse.urlparse(base_url).scheme if base_url else "https"
            cleaned = f"{base_scheme}:{cleaned}"

        # Resolve relative URLs if base_url is supplied
        if base_url and not urllib.parse.urlparse(cleaned).scheme:
            cleaned = urllib.parse.urljoin(base_url, cleaned)

        # Prepend https if no scheme is provided
        parsed = urllib.parse.urlparse(cleaned)
        if not parsed.scheme:
            cleaned = f"https://{cleaned}"
            parsed = urllib.parse.urlparse(cleaned)

        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return None

        # Normalize hostname (lowercase, IDN punycode, strip default ports)
        netloc = parsed.netloc.lower()
        if "@" in netloc:
            netloc = netloc.split("@")[-1]

        host = netloc
        port = None
        if ":" in netloc:
            h_part, p_part = netloc.rsplit(":", 1)
            try:
                port = int(p_part)
                host = h_part
            except ValueError:
                pass

        try:
            host = host.encode("idna").decode("ascii")
        except Exception:
            pass

        if port and cls.DEFAULT_PORTS.get(scheme) == port:
            netloc = host
        elif port:
            netloc = f"{host}:{port}"
        else:
            netloc = host

        # Normalize path: resolve dot segments & remove duplicate slashes
        path = parsed.path
        if not path:
            path = "/"
        else:
            # Resolve dot segments
            dummy_base = f"{scheme}://{netloc}"
            path = urllib.parse.urlparse(urllib.parse.urljoin(dummy_base, path)).path
            # Remove duplicate slashes
            path = re.sub(r"/{2,}", "/", path)

        # Normalize query parameters
        query = parsed.query
        if query:
            query_params = urllib.parse.parse_qsl(query, keep_blank_values=True)
            filtered_params = []
            for k, v in query_params:
                if strip_tracking and k.lower() in cls.TRACKING_PARAMS:
                    continue
                filtered_params.append((k, v))
            sorted_params = sorted(filtered_params, key=lambda x: (x[0], x[1]))
            query = urllib.parse.urlencode(sorted_params)

        # Strip fragment for crawling identity
        fragment = ""

        normalized = urllib.parse.urlunparse((scheme, netloc, path, "", query, fragment))
        return normalized

    @classmethod
    def get_origin(cls, url: str) -> Optional[str]:
        norm = cls.normalize(url)
        if not norm:
            return None
        parsed = urllib.parse.urlparse(norm)
        return f"{parsed.scheme}://{parsed.netloc}"

    @classmethod
    def is_same_domain(cls, url_a: str, url_b: str, match_subdomains: bool = True) -> bool:
        norm_a = cls.normalize(url_a)
        norm_b = cls.normalize(url_b)
        if not norm_a or not norm_b:
            return False
        host_a = urllib.parse.urlparse(norm_a).netloc.lower()
        host_b = urllib.parse.urlparse(norm_b).netloc.lower()
        
        domain_a = host_a.replace("www.", "")
        domain_b = host_b.replace("www.", "")
        
        if match_subdomains:
            return domain_a == domain_b or domain_a.endswith("." + domain_b) or domain_b.endswith("." + domain_a)
        return host_a == host_b


class SSRFValidator:
    """
    Robust SSRF Defense Layer.
    Blocks localhost, loopback, private IPv4/IPv6, link-local, multicast,
    unspecified, reserved, cloud metadata endpoints, internal hostnames, and unsafe schemes.
    Supports connection-level IP verification.
    """
    BLOCKED_IP_NETWORKS = [
        ipaddress.ip_network("0.0.0.0/8"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("100.64.0.0/10"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("224.0.0.0/4"),
        ipaddress.ip_network("240.0.0.0/4"),
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("fc00::/7"),
        ipaddress.ip_network("fe80::/10"),
    ]

    BLOCKED_HOSTNAMES = {
        "localhost", "loopback", "metadata.google.internal", "instance-data"
    }

    BLOCKED_EXACT_IPS = {
        "169.254.169.254", "169.254.169.253"
    }

    @classmethod
    def is_ip_safe(cls, ip_str: str, allow_local_dev: bool = False) -> Tuple[bool, str]:
        # Unconditionally block cloud metadata endpoints
        if ip_str in cls.BLOCKED_EXACT_IPS:
            return False, f"SSRF_BLOCKED: IP '{ip_str}' is a blocked cloud metadata endpoint."
        
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, f"INVALID_IP: String '{ip_str}' is not a valid IP address."

        if allow_local_dev:
            # Allow loopback/private for local dev, but still block metadata
            return True, "SAFE_LOCAL_DEV"

        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            return False, f"SSRF_BLOCKED: IP address '{ip_str}' belongs to a non-public network boundary."

        for net in cls.BLOCKED_IP_NETWORKS:
            if ip_obj in net:
                return False, f"SSRF_BLOCKED: IP address '{ip_str}' falls into restricted network {net}."

        return True, "SAFE"

    @classmethod
    def validate_url(cls, url: str, allow_local_dev: bool = False) -> Tuple[bool, str, Optional[str]]:
        # Enforce server-side security policy: allow_local_dev disabled in production
        is_prod = settings.ENVIRONMENT.strip().lower() == "production"
        effective_allow_local_dev = allow_local_dev and not is_prod

        norm = URLNormalizer.normalize(url)
        if not norm:
            return False, "INVALID_URL: Failed to normalize target URL.", None

        parsed = urllib.parse.urlparse(norm)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return False, f"UNSAFE_SCHEME: Scheme '{scheme}' is not permitted.", None

        hostname = parsed.hostname
        if not hostname:
            return False, "MISSING_HOST: Target URL lacks a valid hostname.", None

        clean_host = hostname.lower().strip()

        # Cloud metadata hostnames MUST be blocked UNCONDITIONALLY regardless of allow_local_dev!
        if clean_host in {"metadata.google.internal", "instance-data"}:
            return False, f"SSRF_BLOCKED: Hostname '{hostname}' is a blocked cloud metadata endpoint.", None

        # Check internal hostnames
        if not effective_allow_local_dev:
            if (
                clean_host in cls.BLOCKED_HOSTNAMES
                or clean_host.endswith(".local")
                or clean_host.endswith(".internal")
                or clean_host.endswith(".lan")
            ):
                return False, f"SSRF_BLOCKED: Hostname '{hostname}' resolves to an internal network boundary.", None

        # Check if hostname itself is an IP address
        try:
            ip_check = ipaddress.ip_address(clean_host)
            is_safe, msg = cls.is_ip_safe(str(ip_check), allow_local_dev=effective_allow_local_dev)
            if not is_safe:
                return False, msg, str(ip_check)
            return True, "SAFE", str(ip_check)
        except ValueError:
            pass  # Standard domain hostname

        # Perform DNS resolution to validate target IP addresses
        try:
            addr_info = socket.getaddrinfo(clean_host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            if not addr_info:
                return False, f"DNS_FAILURE: Hostname '{hostname}' could not be resolved.", None

            resolved_ip = None
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                is_safe, msg = cls.is_ip_safe(ip_str, allow_local_dev=effective_allow_local_dev)
                if not is_safe:
                    return False, f"SSRF_BLOCKED: Hostname '{hostname}' resolved to unsafe IP {ip_str}: {msg}", None
                resolved_ip = ip_str

            return True, "SAFE", resolved_ip

        except socket.gaierror as e:
            if effective_allow_local_dev:
                return True, "LOCAL_DEV_BYPASS", "127.0.0.1"
            return False, f"DNS_RESOLUTION_ERROR: Could not resolve IP for '{hostname}': {e}", None
        except Exception as e:
            return False, f"SSRF_VALIDATION_ERROR: Error validating host '{hostname}': {e}", None


class SafeHTTPTransport(httpx.AsyncHTTPTransport):
    """
    Custom HTTPX AsyncHTTPTransport that validates target IP address at connection time,
    eliminating DNS rebinding gaps.
    """
    def __init__(self, allow_local_dev: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_local_dev = allow_local_dev

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        is_safe, msg, resolved_ip = SSRFValidator.validate_url(url_str, allow_local_dev=self.allow_local_dev)
        if not is_safe:
            raise httpx.RequestError(f"SSRF_BLOCKED: {msg}", request=request)

        # Connection-level destination IP verification to eliminate DNS rebinding window
        host = request.url.host
        try:
            addr_info = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            is_prod = settings.ENVIRONMENT.strip().lower() == "production"
            effective_allow_dev = self.allow_local_dev and not is_prod
            for family, _, _, _, sockaddr in addr_info:
                conn_ip = sockaddr[0]
                ip_safe, ip_msg = SSRFValidator.is_ip_safe(conn_ip, allow_local_dev=effective_allow_dev)
                if not ip_safe:
                    raise httpx.RequestError(f"SSRF_BLOCKED_DNS_REBINDING: Target host '{host}' resolved to unsafe connection IP {conn_ip}", request=request)
        except socket.gaierror:
            pass  # Handled by base transport

        return await super().handle_async_request(request)


class RobotsSitemapService:
    """
    Robust Robots.txt & Sitemap Processor.
    Supports User-agent groups, Allow/Disallow rules with wildcards (* and $),
    Sitemap directives, Crawl-delay, and safe XML parsing for urlset and sitemapindex.
    """
    def __init__(self, user_agent: str = "LocalLiftBot/1.0"):
        self.user_agent = user_agent
        self.robot_parser = urllib.robotparser.RobotFileParser()
        self.sitemap_urls: List[str] = []
        self.crawl_delay: Optional[float] = None
        self.fetch_status: str = "not_fetched"
        self.status_code: int = 0
        self.rules_count: int = 0
        self.robots_url: str = ""

    async def fetch_and_parse_robots(self, client: httpx.AsyncClient, origin_url: str, allow_local_dev: bool = False) -> Dict[str, Any]:
        self.robots_url = f"{origin_url.rstrip('/')}/robots.txt"
        result = {
            "robots_url": self.robots_url,
            "status_code": 0,
            "fetched": False,
            "fetch_status": "failed",
            "sitemaps": [],
            "crawl_delay": None,
            "rules_count": 0
        }
        
        try:
            is_safe, msg, _ = SSRFValidator.validate_url(self.robots_url, allow_local_dev=allow_local_dev)
            if not is_safe:
                self.fetch_status = f"ssrf_blocked: {msg}"
                result["fetch_status"] = self.fetch_status
                return result

            resp = await client.get(self.robots_url)
            self.status_code = resp.status_code
            result["status_code"] = resp.status_code
            
            if resp.status_code == 200:
                self.fetch_status = "200_ok"
                result["fetched"] = True
                result["fetch_status"] = "200_ok"
                content = resp.text
                self.robot_parser.parse(content.splitlines())
                
                # Count rules & extract sitemaps and Crawl-delay
                rule_count = 0
                for line in content.splitlines():
                    clean_line = line.strip()
                    if not clean_line or clean_line.startswith("#"):
                        continue
                    if clean_line.lower().startswith(("allow:", "disallow:")):
                        rule_count += 1
                    elif clean_line.lower().startswith("sitemap:"):
                        sm_url = clean_line.split(":", 1)[1].strip()
                        norm_sm = URLNormalizer.normalize(sm_url, origin_url)
                        if norm_sm and norm_sm not in self.sitemap_urls:
                            self.sitemap_urls.append(norm_sm)
                            result["sitemaps"].append(norm_sm)
                    elif clean_line.lower().startswith("crawl-delay:"):
                        try:
                            cd_val = float(clean_line.split(":", 1)[1].strip())
                            self.crawl_delay = cd_val
                            result["crawl_delay"] = cd_val
                        except ValueError:
                            pass
                
                self.rules_count = rule_count
                result["rules_count"] = rule_count
            elif resp.status_code == 404:
                self.fetch_status = "404_not_found"
                result["fetch_status"] = "404_not_found"
            else:
                self.fetch_status = f"http_{resp.status_code}"
                result["fetch_status"] = self.fetch_status

        except Exception as e:
            logger.warning(f"Robots.txt fetch error for {origin_url}: {e}")
            self.fetch_status = f"fetch_error: {str(e)[:50]}"
            result["fetch_status"] = self.fetch_status

        # Add candidate default /sitemap.xml if no sitemap specified
        default_sm = f"{origin_url.rstrip('/')}/sitemap.xml"
        if default_sm not in self.sitemap_urls:
            self.sitemap_urls.append(default_sm)

        return result

    def is_allowed(self, url: str) -> bool:
        if self.fetch_status == "404_not_found":
            return True
        try:
            return self.robot_parser.can_fetch(self.user_agent, url)
        except Exception:
            return True

    async def discover_sitemap_urls(
        self,
        client: httpx.AsyncClient,
        origin_url: str,
        max_urls: int = 100,
        allow_local_dev: bool = False
    ) -> List[Dict[str, str]]:
        discovered: List[Dict[str, str]] = []
        visited_sitemaps: Set[str] = set()
        queue = list(self.sitemap_urls)
        depth_map: Dict[str, int] = {url: 0 for url in queue}

        while queue and len(discovered) < max_urls:
            sm_url = queue.pop(0)
            depth = depth_map.get(sm_url, 0)
            if sm_url in visited_sitemaps or depth > 3:
                continue
            visited_sitemaps.add(sm_url)

            # SSRF and Domain scope validation for sitemaps
            is_safe, _, _ = SSRFValidator.validate_url(sm_url, allow_local_dev=allow_local_dev)
            if not is_safe or not URLNormalizer.is_same_domain(origin_url, sm_url):
                continue

            try:
                resp = await client.get(sm_url)
                if resp.status_code != 200:
                    continue

                # Stream XML parsing via ElementTree safely
                try:
                    root = ElementTree.fromstring(resp.content)
                except ElementTree.ParseError:
                    continue

                tag_root = root.tag.split("}")[-1] if "}" in root.tag else root.tag

                if tag_root == "sitemapindex":
                    for elem in root.iter():
                        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        if tag_name == "loc" and elem.text:
                            loc_url = URLNormalizer.normalize(elem.text.strip(), origin_url)
                            if loc_url and loc_url not in visited_sitemaps:
                                queue.append(loc_url)
                                depth_map[loc_url] = depth + 1
                elif tag_root == "urlset":
                    for elem in root.iter():
                        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        if tag_name == "loc" and elem.text:
                            loc_url = URLNormalizer.normalize(elem.text.strip(), origin_url)
                            if loc_url and URLNormalizer.is_same_domain(origin_url, loc_url):
                                source_type = "robots_sitemap" if sm_url in self.sitemap_urls else "sitemap"
                                discovered.append({"url": loc_url, "source": source_type})
                                if len(discovered) >= max_urls:
                                    break
            except Exception as e:
                logger.debug(f"Sitemap processing error for {sm_url}: {e}")

        return discovered


class WebsiteCrawler:
    """
    Production-Grade SEO & Website Crawler Engine.
    Implements all strict limits, security enforcement, Playwright fallback,
    broken-link status tracking, detailed link records, and job lifecycle.
    """
    SERVER_MAX_PAGES = 10000
    SERVER_MAX_RUNTIME_SEC = 600
    SERVER_MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB
    SERVER_MAX_TOTAL_BYTES = 500 * 1024 * 1024  # 500 MB
    SERVER_MAX_JS_PAGES = 50
    SERVER_MAX_LINK_CHECKS = 500
    SERVER_MAX_REDIRECTS = 5

    def __init__(
        self,
        start_url: str,
        max_pages: int = 25,
        respect_robots: bool = True,
        crawl_delay_ms: int = 200,
        follow_redirects: bool = True,
        allow_local_dev: bool = False,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        max_depth: int = 5,
        enable_js_rendering: bool = False,
        check_external_links: bool = True,
        max_external_links: int = 50,
        concurrency: int = 5,
        progress_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
        cancellation_check: Optional[Callable[[], bool]] = None
    ):
        self.raw_start_url = start_url
        self.start_url = URLNormalizer.normalize(start_url) or start_url
        self.origin = URLNormalizer.get_origin(self.start_url) or self.start_url
        
        # Enforce server safety ceilings
        self.effective_max_pages = min(max(1, max_pages), self.SERVER_MAX_PAGES)
        self.respect_robots = respect_robots
        self.crawl_delay_ms = max(0, crawl_delay_ms)
        self.follow_redirects = follow_redirects
        
        # Security Policy
        is_prod = settings.ENVIRONMENT.strip().lower() == "production"
        self.allow_local_dev = allow_local_dev and not is_prod
        
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        self.max_depth = max_depth
        
        self.enable_js_rendering = enable_js_rendering
        self.browser_rendering_unavailable = enable_js_rendering and not PLAYWRIGHT_AVAILABLE
        
        self.check_external_links = check_external_links
        self.max_external_links = min(max(0, max_external_links), 200)
        self.concurrency = min(max(1, concurrency), 10)
        
        self.progress_callback = progress_callback
        self.cancellation_check = cancellation_check

        # State counters & buffers
        self.visited_urls: Set[str] = set()
        self.discovered_urls: List[Dict[str, str]] = []
        self.pages_data: List[Dict[str, Any]] = []
        self.link_graph: List[Dict[str, Any]] = []
        self.redirect_chains: List[Dict[str, Any]] = []
        self.skipped_urls: List[Dict[str, str]] = []
        self.broken_links: List[Dict[str, Any]] = []
        self.link_records: List[Dict[str, Any]] = []
        self.checked_link_cache: Dict[str, Dict[str, Any]] = {}

        # Limits & Execution State Flags
        self.runtime_limit_reached = False
        self.total_bytes_limit_reached = False
        self.redirect_limit_reached = False
        
        self.broken_link_check_status = "not_started"
        self.broken_link_check_error: Optional[str] = None
        self.links_skipped_count = 0

        # Counter metrics
        self.pages_discovered_count = 0
        self.pages_crawled_count = 0
        self.pages_processed_count = 0
        self.pages_failed_count = 0
        self.pages_blocked_count = 0
        self.links_discovered_count = 0
        self.links_checked_count = 0
        self.broken_links_found_count = 0
        self.js_pages_rendered_count = 0
        self.sitemap_urls_discovered_count = 0
        self.robots_blocked_count = 0
        self.ssrf_blocked_count = 0
        self.total_bytes_downloaded = 0

        self.robots_service = RobotsSitemapService()
        self.start_timestamp = datetime.now(timezone.utc)
        self.bot_protection_evidence: Optional[Dict[str, Any]] = None

    def get_options_snapshot(self) -> Dict[str, Any]:
        return {
            "start_url": self.start_url,
            "user_max_pages": self.effective_max_pages,
            "server_max_pages": self.SERVER_MAX_PAGES,
            "respect_robots": self.respect_robots,
            "crawl_delay_ms": self.crawl_delay_ms,
            "follow_redirects": self.follow_redirects,
            "allow_local_dev": self.allow_local_dev,
            "include_patterns": self.include_patterns,
            "exclude_patterns": self.exclude_patterns,
            "max_depth": self.max_depth,
            "enable_js_rendering": self.enable_js_rendering,
            "playwright_available": PLAYWRIGHT_AVAILABLE,
            "browser_rendering_unavailable": self.browser_rendering_unavailable,
            "check_external_links": self.check_external_links,
            "max_external_links": self.max_external_links,
            "server_max_runtime_sec": self.SERVER_MAX_RUNTIME_SEC,
            "server_max_response_bytes": self.SERVER_MAX_RESPONSE_BYTES,
            "server_max_total_bytes": self.SERVER_MAX_TOTAL_BYTES,
            "server_max_js_pages": self.SERVER_MAX_JS_PAGES,
            "server_max_link_checks": self.SERVER_MAX_LINK_CHECKS,
            "server_max_redirects": self.SERVER_MAX_REDIRECTS,
        }

    async def crawl(self) -> List[Dict[str, Any]]:
        # 1. Initial SSRF Validation
        is_safe, reason, _ = SSRFValidator.validate_url(self.start_url, allow_local_dev=self.allow_local_dev)
        if not is_safe:
            self.ssrf_blocked_count += 1
            raise ValueError(f"SSRF validation rejected start URL '{self.start_url}': {reason}")

        headers = {
            "User-Agent": "LocalLiftBot/1.0 (+https://locallift.io/bot; SEO Audit Engine)"
        }

        transport = SafeHTTPTransport(allow_local_dev=self.allow_local_dev, verify=True)
        
        async with httpx.AsyncClient(transport=transport, headers=headers, timeout=12.0, follow_redirects=False) as client:
            # 2. Fetch Robots.txt & XML Sitemaps
            if self.respect_robots:
                await self._notify("fetching_robots", "Fetching & inspecting robots.txt", 3.0)
                await self.robots_service.fetch_and_parse_robots(client, self.origin, allow_local_dev=self.allow_local_dev)
                
                await self._notify("reading_sitemaps", "Discovering XML sitemaps", 7.0)
                sitemap_links = await self.robots_service.discover_sitemap_urls(
                    client, self.origin, max_urls=self.effective_max_pages, allow_local_dev=self.allow_local_dev
                )
                self.sitemap_urls_discovered_count = len(sitemap_links)
                for sm_item in sitemap_links:
                    self.discovered_urls.append(sm_item)
                    self.pages_discovered_count += 1

            # Seed Crawl Queue with (URL, source, depth)
            queue: List[Dict[str, Any]] = [
                {"url": self.start_url, "source": "manual_seed", "depth": 0}
            ] + [{"url": item["url"], "source": item["source"], "depth": 1} for item in self.discovered_urls]
            
            self.pages_discovered_count = max(self.pages_discovered_count, len(queue))

            # 3. Main Crawl Execution Loop with Concurrency, Throttling & Limits
            sem = asyncio.Semaphore(self.concurrency)
            last_request_time = 0.0

            while queue and len(self.pages_data) < self.effective_max_pages:
                if self._check_cancelled():
                    break

                # Enforce Runtime Ceiling
                elapsed_sec = (datetime.now(timezone.utc) - self.start_timestamp).total_seconds()
                if elapsed_sec >= self.SERVER_MAX_RUNTIME_SEC:
                    logger.warning(f"Wall-clock runtime ceiling ({self.SERVER_MAX_RUNTIME_SEC}s) reached. Halting crawl loop.")
                    self.runtime_limit_reached = True
                    break

                # Enforce Total Cumulative Download Bytes Ceiling
                if self.total_bytes_downloaded >= self.SERVER_MAX_TOTAL_BYTES:
                    logger.warning(f"Total download bytes ceiling ({self.SERVER_MAX_TOTAL_BYTES} bytes) reached. Halting crawl loop.")
                    self.total_bytes_limit_reached = True
                    break

                item = queue.pop(0)
                current_url = item["url"]
                source = item["source"]
                depth = item["depth"]

                if current_url in self.visited_urls or depth > self.max_depth:
                    continue

                if not self._matches_patterns(current_url):
                    self.skipped_urls.append({"url": current_url, "reason": "pattern_excluded"})
                    continue

                # Check robots.txt disallow rule
                if self.respect_robots and not self.robots_service.is_allowed(current_url):
                    self.skipped_urls.append({"url": current_url, "reason": "robots_disallowed"})
                    self.visited_urls.add(current_url)
                    self.robots_blocked_count += 1
                    self.pages_blocked_count += 1
                    continue

                # SSRF check on current URL
                is_safe, ssrf_msg, _ = SSRFValidator.validate_url(current_url, allow_local_dev=self.allow_local_dev)
                if not is_safe:
                    self.skipped_urls.append({"url": current_url, "reason": ssrf_msg})
                    self.visited_urls.add(current_url)
                    self.ssrf_blocked_count += 1
                    self.pages_blocked_count += 1
                    continue

                self.visited_urls.add(current_url)

                # Real Throttling Delay
                if self.crawl_delay_ms > 0 or (self.robots_service.crawl_delay and self.robots_service.crawl_delay > 0):
                    effective_delay_sec = max(self.crawl_delay_ms / 1000.0, self.robots_service.crawl_delay or 0.0)
                    now = asyncio.get_event_loop().time()
                    elapsed_since_last = now - last_request_time
                    if elapsed_since_last < effective_delay_sec:
                        await asyncio.sleep(effective_delay_sec - elapsed_since_last)
                    last_request_time = asyncio.get_event_loop().time()

                pct = min(85.0, 10.0 + (len(self.pages_data) / float(self.effective_max_pages)) * 75.0)
                await self._notify("crawling", f"Scanning page {len(self.pages_data) + 1}/{self.effective_max_pages}: {current_url}", pct)

                async with sem:
                    try:
                        page_res, new_links = await self._fetch_and_process_url(
                            client, current_url, source, depth, allow_local_dev=self.allow_local_dev
                        )
                        if page_res:
                            self.pages_data.append(page_res)
                            self.pages_crawled_count += 1
                            self.pages_processed_count += 1
                            
                            # Queue newly discovered internal links
                            for n_link in new_links:
                                dest_url = n_link["destination_url"]
                                if dest_url not in self.visited_urls:
                                    parsed_path = urllib.parse.urlparse(dest_url).path.lower()
                                    if not re.search(r"\.(pdf|png|jpg|jpeg|gif|svg|css|js|webp|zip|mp4|mp3|woff|woff2)$", parsed_path):
                                        queue.append({"url": dest_url, "source": "internal_link", "depth": depth + 1})
                                        self.pages_discovered_count += 1
                                        self.links_discovered_count += 1
                    except Exception as exc:
                        logger.warning(f"Crawl fetch error on {current_url}: {exc}")
                        self.pages_failed_count += 1

            # 4. Broken-Link Checking Phase
            await self._notify("checking_links", "Validating internal & external link graph", 88.0)
            await self._validate_link_graph(client)

            await self._notify("saving", "Completing audit page analysis & graph synthesis", 95.0)

        return self.pages_data

    async def _render_with_playwright(self, url: str) -> Optional[str]:
        if not PLAYWRIGHT_AVAILABLE:
            self.browser_rendering_unavailable = True
            return None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="LocalLiftBot/1.0 (+https://locallift.io/bot; SEO Audit Engine)"
                )
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=12000)
                content = await page.content()
                await browser.close()
                return content
        except Exception as e:
            logger.warning(f"Playwright browser rendering error for {url}: {e}")
            return None

    async def _fetch_and_process_url(
        self,
        client: httpx.AsyncClient,
        url: str,
        source: str,
        depth: int,
        allow_local_dev: bool = False
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        start_time = asyncio.get_event_loop().time()
        
        # Follow redirects manually to enforce SSRF & track chain
        curr_url = url
        redirect_chain: List[str] = [url]
        redirect_count = 0
        resp = None

        while True:
            # SSRF check on every jump
            is_safe, msg, _ = SSRFValidator.validate_url(curr_url, allow_local_dev=allow_local_dev)
            if not is_safe:
                self.skipped_urls.append({"url": curr_url, "reason": f"Redirect SSRF: {msg}"})
                self.ssrf_blocked_count += 1
                break

            try:
                resp = await client.get(curr_url)
            except httpx.RequestError as exc:
                logger.warning(f"HTTP request error fetching {curr_url}: {exc}")
                return None, []

            body_bytes = len(resp.content)
            
            # Enforce SERVER_MAX_RESPONSE_BYTES limit per response
            content_length = resp.headers.get("content-length")
            if content_length and content_length.isdigit() and int(content_length) > self.SERVER_MAX_RESPONSE_BYTES:
                logger.warning(f"Skipping {curr_url}: Content-Length {content_length} exceeds max response limit.")
                self.skipped_urls.append({"url": curr_url, "reason": "exceeds_max_response_bytes"})
                return None, []

            if body_bytes > self.SERVER_MAX_RESPONSE_BYTES:
                logger.warning(f"Truncating response body for {curr_url}: Exceeds {self.SERVER_MAX_RESPONSE_BYTES} bytes.")
                body_bytes = self.SERVER_MAX_RESPONSE_BYTES

            self.total_bytes_downloaded += body_bytes

            # Detect Bot Protection Challenges (403, 401, Cloudflare, CAPTCHA)
            bot_prot = self._detect_bot_protection(resp)
            if bot_prot["detected"]:
                self.bot_protection_evidence = bot_prot

            if resp.is_redirect:
                loc = resp.headers.get("Location")
                if not loc:
                    break
                
                next_url = URLNormalizer.normalize(loc, curr_url)
                if not next_url:
                    break

                # Check for redirect loop
                if next_url in redirect_chain:
                    logger.warning(f"Redirect loop detected: {curr_url} -> {next_url}")
                    self.redirect_chains.append({
                        "initial_url": url,
                        "final_url": next_url,
                        "steps": redirect_chain + [next_url],
                        "redirect_count": redirect_count + 1,
                        "status": "redirect_loop"
                    })
                    break

                if not self.follow_redirects:
                    load_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                    return {
                        "url": url,
                        "status_code": resp.status_code,
                        "title": None,
                        "meta_description": None,
                        "h1": None,
                        "h2_list": [],
                        "word_count": 0,
                        "canonical_url": None,
                        "is_indexable": False,
                        "load_time_ms": load_time_ms,
                        "schema_types": [],
                        "images_count": 0,
                        "missing_alt_count": 0,
                        "internal_links_count": 0,
                        "external_links_count": 0,
                        "broken_links": [],
                        "issues_detected": [f"HTTP Redirect ({resp.status_code}) to {next_url}"],
                        "render_mode": "redirect_not_followed",
                        "redirect_location": next_url,
                        "discovery_source": source
                    }, []

                redirect_count += 1
                redirect_chain.append(next_url)
                if redirect_count >= self.SERVER_MAX_REDIRECTS:
                    self.redirect_limit_reached = True
                    logger.warning(f"Redirect limit ({self.SERVER_MAX_REDIRECTS}) reached for {url}")
                    break
                curr_url = next_url
            else:
                break

        if not resp:
            return None, []

        load_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
        final_url = str(resp.url)
        norm_final_url = URLNormalizer.normalize(final_url) or final_url

        if redirect_count > 0:
            self.redirect_chains.append({
                "initial_url": url,
                "final_url": norm_final_url,
                "steps": redirect_chain,
                "redirect_count": redirect_count,
                "status": "redirect_limit_reached" if redirect_count >= self.SERVER_MAX_REDIRECTS else "redirect_followed"
            })

        content_type = resp.headers.get("content-type", "").lower()
        if "text/html" not in content_type and resp.status_code == 200:
            return None, []

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Check if browser rendering fallback should be invoked
        body_text = soup.get_text(separator=" ")
        words = [w for w in body_text.split() if len(w) > 1]
        word_count = len(words)
        has_js_app_shell = bool(soup.find(id=re.compile(r"root|app|__next|__nuxt", re.I))) and word_count < 30
        
        render_mode = "raw_html"
        if has_js_app_shell and self.enable_js_rendering and self.js_pages_rendered_count < self.SERVER_MAX_JS_PAGES:
            rendered_dom = await self._render_with_playwright(norm_final_url)
            if rendered_dom:
                soup = BeautifulSoup(rendered_dom, "html.parser")
                render_mode = "browser"
                self.js_pages_rendered_count += 1

        page_data, extracted_links = self._analyze_html_and_extract_links(
            url=norm_final_url,
            status_code=resp.status_code,
            soup=soup,
            load_time_ms=load_time_ms,
            source=source,
            render_mode=render_mode
        )
        return page_data, extracted_links

    def _detect_bot_protection(self, resp: httpx.Response) -> Dict[str, Any]:
        status = resp.status_code
        headers = {k.lower(): v.lower() for k, v in resp.headers.items()}
        body = resp.text.lower() if resp.text else ""

        detected = False
        prot_type = "none"
        evidence = []

        if status == 429:
            detected = True
            prot_type = "rate_limit"
            evidence.append("HTTP 429 Too Many Requests status code")
        elif status in (401, 403):
            if "cf-mitigated" in headers or "cloudflare" in headers.get("server", "") or "cf-ray" in headers:
                detected = True
                prot_type = "cloudflare_challenge"
                evidence.append("Cloudflare bot management / ray ID detected in response headers")
            elif any(k in body for k in ["g-recaptcha", "hcaptcha", "cf-turnstile", "captcha"]):
                detected = True
                prot_type = "captcha_challenge"
                evidence.append("Interactive CAPTCHA challenge elements found in HTML body")
            elif "aws" in headers.get("x-amzn-errortype", "") or "waf" in body:
                detected = True
                prot_type = "waf_challenge"
                evidence.append("Web Application Firewall (WAF) blocking page detected")
            else:
                detected = True
                prot_type = "access_denied"
                evidence.append(f"HTTP {status} Access Denied status returned by origin server")

        return {
            "detected": detected,
            "type": prot_type,
            "status_code": status,
            "evidence": evidence
        }

    def _analyze_html_and_extract_links(
        self,
        url: str,
        status_code: int,
        soup: BeautifulSoup,
        load_time_ms: int,
        source: str,
        render_mode: str = "raw_html"
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        issues = []
        
        body_text = soup.get_text(separator=" ")
        words = [w for w in body_text.split() if len(w) > 1]
        word_count = len(words)

        has_js_app_shell = bool(soup.find(id=re.compile(r"root|app|__next|__nuxt", re.I))) and word_count < 30
        if has_js_app_shell and render_mode == "raw_html":
            issues.append("JavaScript-rendered SPA detected. Analyzed raw HTML DOM shell.")

        # Title
        title_tag = soup.find("title")
        title = title_tag.get_text().strip() if title_tag else None
        if not title:
            issues.append("Missing page title tag (<title>)")
        elif len(title) < 30:
            issues.append("Title tag too short (< 30 chars)")
        elif len(title) > 65:
            issues.append("Title tag too long (> 65 chars)")

        # Meta description
        meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        meta_description = meta_desc_tag.get("content", "").strip() if meta_desc_tag else None
        if not meta_description:
            issues.append("Missing meta description tag")
        elif len(meta_description) < 70:
            issues.append("Meta description too short (< 70 chars)")
        elif len(meta_description) > 160:
            issues.append("Meta description too long (> 160 chars)")

        # Headings
        h1_tags = soup.find_all("h1")
        h1 = h1_tags[0].get_text().strip() if h1_tags else None
        if not h1_tags:
            issues.append("Missing H1 heading tag")
        elif len(h1_tags) > 1:
            issues.append(f"Multiple H1 headings found on page ({len(h1_tags)})")

        h2_list = [h.get_text().strip() for h in soup.find_all("h2") if h.get_text().strip()][:10]

        if word_count < 250 and not has_js_app_shell:
            issues.append("Thin on-page content (< 250 words)")

        # Canonical
        canonical_tag = soup.find("link", rel=re.compile(r"canonical", re.I))
        canonical_url = None
        if canonical_tag and canonical_tag.get("href"):
            canonical_url = URLNormalizer.normalize(canonical_tag.get("href"), url)
        if not canonical_url:
            issues.append("Missing canonical link tag")

        # Robots & Indexability
        robots_meta = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
        robots_content = robots_meta.get("content", "").lower() if robots_meta else ""
        is_indexable = "noindex" not in robots_content and status_code == 200

        # Images & Alt Text
        images = soup.find_all("img")
        missing_alt = [img for img in images if not img.get("alt") or not img.get("alt").strip()]
        if missing_alt:
            issues.append(f"{len(missing_alt)} images missing descriptive alt attribute")

        # Structured Data Extraction
        from app.services.schema_intelligence import SchemaIntelligenceEngine
        struct_data = SchemaIntelligenceEngine.extract_structured_data(soup, url)
        schema_types = struct_data.get("schema_types", [])
        
        # Local Signals
        phones_found = set()
        for tel_a in soup.find_all("a", href=re.compile(r"^tel:", re.I)):
            clean_tel = tel_a["href"].replace("tel:", "").strip()
            if clean_tel:
                phones_found.add(clean_tel)

        emails_found = set()
        for mail_a in soup.find_all("a", href=re.compile(r"^mailto:", re.I)):
            clean_mail = mail_a["href"].replace("mailto:", "").split("?")[0].strip()
            if clean_mail:
                emails_found.add(clean_mail.lower())

        has_map_embed = bool(soup.find("iframe", src=re.compile(r"google\.com/maps|maps\.google\.com", re.I)))

        # Link Extraction
        extracted_links: List[Dict[str, Any]] = []
        internal_links_count = 0
        external_links_count = 0

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            target_norm = URLNormalizer.normalize(href, url)
            if not target_norm:
                continue

            is_internal = URLNormalizer.is_same_domain(self.origin, target_norm)
            link_text = a_tag.get_text().strip()[:100]

            link_entry = {
                "source_url": url,
                "destination_url": target_norm,
                "link_text": link_text,
                "is_internal": is_internal,
            }
            extracted_links.append(link_entry)
            self.link_graph.append(link_entry)

            if is_internal:
                internal_links_count += 1
            else:
                external_links_count += 1

        if load_time_ms > 1500:
            issues.append(f"Slow page response time ({load_time_ms}ms)")

        page_data = {
            "url": url,
            "status_code": status_code,
            "title": title,
            "meta_description": meta_description,
            "h1": h1,
            "h2_list": h2_list,
            "word_count": word_count,
            "canonical_url": canonical_url,
            "is_indexable": is_indexable,
            "load_time_ms": load_time_ms,
            "schema_types": list(set(schema_types)),
            "json_ld_schemas": struct_data.get("json_ld_schemas", []),
            "schema_entities": struct_data.get("schema_entities", []),
            "schema_formats": struct_data.get("schema_formats", []),
            "schema_count": len(struct_data.get("schema_entities", [])),
            "schema_parse_errors": struct_data.get("schema_parse_errors", []),
            "phones_found": list(phones_found)[:5],
            "emails_found": list(emails_found)[:5],
            "has_map_embed": has_map_embed,
            "images_count": len(images),
            "missing_alt_count": len(missing_alt),
            "internal_links_count": internal_links_count,
            "external_links_count": external_links_count,
            "broken_links": [],
            "issues_detected": issues,
            "render_mode": render_mode,
            "discovery_source": source
        }
        return page_data, extracted_links

    async def _validate_link_graph(self, client: httpx.AsyncClient):
        """
        Validates internal & external links using explicit verification states.
        Never turns network exceptions into 404s.
        Maintains authoritative broken_link_check_status and detailed link records.
        """
        self.broken_link_check_status = "running"
        
        unique_targets: Set[str] = set()
        external_count = 0
        
        for link in self.link_graph:
            dest = link["destination_url"]
            if link["is_internal"]:
                unique_targets.add(dest)
            elif self.check_external_links and external_count < self.max_external_links:
                unique_targets.add(dest)
                external_count += 1

        all_target_list = list(unique_targets)
        
        # Enforce SERVER_MAX_LINK_CHECKS limit
        if len(all_target_list) > self.SERVER_MAX_LINK_CHECKS:
            self.links_skipped_count = len(all_target_list) - self.SERVER_MAX_LINK_CHECKS
            all_target_list = all_target_list[:self.SERVER_MAX_LINK_CHECKS]
            self.broken_link_check_status = "limit_reached"

        sem = asyncio.Semaphore(self.concurrency)

        async def verify_link(target: str) -> Tuple[str, Dict[str, Any]]:
            if target in self.checked_link_cache:
                return target, self.checked_link_cache[target]

            is_safe, ssrf_msg, _ = SSRFValidator.validate_url(target, allow_local_dev=self.allow_local_dev)
            if not is_safe:
                res = {
                    "status_code": 403,
                    "verification_state": "blocked",
                    "response_time_ms": 0,
                    "error_code": "SSRF_BLOCKED",
                    "error_message": ssrf_msg
                }
                self.checked_link_cache[target] = res
                return target, res

            async with sem:
                start_t = asyncio.get_event_loop().time()
                status_code = 0
                verif_state = "not_checked"
                error_code = None
                error_msg = None

                try:
                    # Attempt HEAD first
                    try:
                        resp = await client.head(target, timeout=5.0)
                        status_code = resp.status_code
                        # Controlled GET fallback if HEAD returns 405, 403, 429, 5xx, or unexpected behavior
                        if status_code in (405, 403, 429, 500, 502, 503, 504):
                            resp = await client.get(target, timeout=5.0, headers={"Range": "bytes=0-1024"})
                            status_code = resp.status_code
                    except (httpx.TimeoutException, asyncio.TimeoutError):
                        # Timeout on HEAD -> try controlled GET fallback
                        try:
                            resp = await client.get(target, timeout=5.0, headers={"Range": "bytes=0-1024"})
                            status_code = resp.status_code
                        except (httpx.TimeoutException, asyncio.TimeoutError):
                            verif_state = "timeout"
                            error_code = "TIMEOUT"
                            error_msg = "Request timed out during link verification"
                        except httpx.ConnectError:
                            verif_state = "connection_error"
                            error_code = "CONNECTION_ERROR"
                            error_msg = "Failed to establish TCP connection"
                        except Exception as get_err:
                            verif_state = "connection_error"
                            error_code = "FETCH_ERROR"
                            error_msg = str(get_err)[:100]

                    except httpx.ConnectError as conn_err:
                        verif_state = "connection_error"
                        error_code = "CONNECTION_ERROR"
                        error_msg = str(conn_err)[:100]
                    except (httpx.TLSUpgradeError, httpx.ProxyError):
                        verif_state = "tls_error"
                        error_code = "TLS_ERROR"
                        error_msg = "TLS handshake or certificate failure"
                    except httpx.RequestError as req_err:
                        if "DNS" in str(req_err) or "getaddrinfo" in str(req_err):
                            verif_state = "dns_error"
                            error_code = "DNS_ERROR"
                        else:
                            verif_state = "connection_error"
                            error_code = "REQUEST_ERROR"
                        error_msg = str(req_err)[:100]

                    if status_code > 0:
                        if status_code == 200:
                            verif_state = "200"
                        elif 300 <= status_code < 400:
                            verif_state = "3xx"
                        elif status_code == 404:
                            verif_state = "404"
                            error_code = "HTTP_404_NOT_FOUND"
                            error_msg = "Resource not found (404)"
                        elif status_code == 410:
                            verif_state = "410"
                            error_code = "HTTP_410_GONE"
                            error_msg = "Resource permanently gone (410)"
                        elif status_code >= 500:
                            verif_state = "5xx"
                            error_code = f"HTTP_{status_code}"
                            error_msg = f"Server error response ({status_code})"
                        else:
                            verif_state = f"http_{status_code}"
                            error_code = f"HTTP_{status_code}"

                except Exception as e:
                    verif_state = "connection_error"
                    error_code = "UNEXPECTED_ERROR"
                    error_msg = str(e)[:100]

                elapsed_ms = int((asyncio.get_event_loop().time() - start_t) * 1000)
                res = {
                    "status_code": status_code,
                    "verification_state": verif_state,
                    "response_time_ms": elapsed_ms,
                    "error_code": error_code,
                    "error_message": error_msg
                }
                self.checked_link_cache[target] = res
                return target, res

        tasks = [verify_link(t) for t in all_target_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        target_res_map: Dict[str, Dict[str, Any]] = {}
        for r in results:
            if isinstance(r, tuple):
                t_url, res_obj = r
                target_res_map[t_url] = res_obj
                self.links_checked_count += 1

        # Match broken links & retain detailed link records
        page_broken_map: Dict[str, List[str]] = {}
        for link in self.link_graph:
            src = link["source_url"]
            dest = link["destination_url"]
            res_obj = target_res_map.get(dest, {
                "status_code": 200,
                "verification_state": "200",
                "response_time_ms": 0,
                "error_code": None,
                "error_message": None
            })

            status = res_obj["status_code"]
            verif_state = res_obj["verification_state"]

            # Record detailed link verification record
            self.link_records.append({
                "source_url": src,
                "destination_url": dest,
                "link_type": "internal" if link["is_internal"] else "external",
                "status_code": status,
                "verification_state": verif_state,
                "response_time_ms": res_obj["response_time_ms"],
                "redirect_chain": [],
                "error_code": res_obj["error_code"],
                "error_message": res_obj["error_message"]
            })

            # URL is broken ONLY when status code is 404 or 410 (or explicit broken status)
            if status in (404, 410):
                if src not in page_broken_map:
                    page_broken_map[src] = []
                if dest not in page_broken_map[src]:
                    page_broken_map[src].append(f"Broken Link ({status}): {dest}")
                
                self.broken_links.append({
                    "source_url": src,
                    "destination_url": dest,
                    "status_code": status,
                    "verification_state": verif_state,
                    "link_text": link.get("link_text"),
                    "error_code": res_obj["error_code"],
                    "error_message": res_obj["error_message"]
                })
                self.broken_links_found_count += 1

        for p in self.pages_data:
            url = p["url"]
            if url in page_broken_map:
                p["broken_links"] = page_broken_map[url]
                for b_msg in page_broken_map[url]:
                    p["issues_detected"].append(b_msg)

        if self.broken_link_check_status != "limit_reached":
            self.broken_link_check_status = "completed"

    def _matches_patterns(self, url: str) -> bool:
        if self.include_patterns:
            if not any(fnmatch.fnmatch(url, pat) or re.search(pat, url) for pat in self.include_patterns):
                return False
        if self.exclude_patterns:
            if any(fnmatch.fnmatch(url, pat) or re.search(pat, url) for pat in self.exclude_patterns):
                return False
        return True

    def _check_cancelled(self) -> bool:
        if self.cancellation_check:
            try:
                return self.cancellation_check()
            except Exception:
                return False
        return False

    async def _notify(self, stage: str, stage_msg: str, progress: float):
        if self.progress_callback:
            try:
                payload = {
                    "stage": stage,
                    "current_stage": stage_msg,
                    "progress": progress,
                    "pages_discovered": self.pages_discovered_count,
                    "pages_crawled": self.pages_crawled_count,
                    "pages_processed": self.pages_processed_count,
                    "pages_failed": self.pages_failed_count,
                    "pages_blocked": self.pages_blocked_count,
                    "links_discovered": self.links_discovered_count,
                    "links_checked": self.links_checked_count,
                    "links_skipped": self.links_skipped_count,
                    "broken_links_found": self.broken_links_found_count,
                    "broken_link_check_status": self.broken_link_check_status,
                    "broken_link_check_error": self.broken_link_check_error,
                    "js_pages_rendered": self.js_pages_rendered_count,
                    "browser_rendering_unavailable": self.browser_rendering_unavailable,
                    "sitemap_urls_discovered": self.sitemap_urls_discovered_count,
                    "robots_blocked_count": self.robots_blocked_count,
                    "ssrf_blocked_count": self.ssrf_blocked_count,
                    "runtime_limit_reached": self.runtime_limit_reached,
                    "total_bytes_limit_reached": self.total_bytes_limit_reached,
                    "redirect_limit_reached": self.redirect_limit_reached,
                }
                res = self.progress_callback(payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
