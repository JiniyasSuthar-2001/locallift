import re
import urllib.parse
from typing import Optional, Tuple, List
from app.services.serp.base import SERPItem, SERPResponse

class DomainMatcher:
    @staticmethod
    def normalize_host(url_or_domain: str) -> str:
        """
        Extracts and normalizes the canonical hostname from a URL or raw domain string.
        Examples:
          'https://www.example.com/path?q=1' -> 'example.com'
          'http://example.com:8080/' -> 'example.com'
          'sub.example.com.au' -> 'sub.example.com.au'
          'EXAMPLE.COM' -> 'example.com'
        """
        if not url_or_domain:
            return ""
        
        raw = url_or_domain.strip().lower()
        if not raw.startswith("http://") and not raw.startswith("https://"):
            raw = "https://" + raw

        try:
            parsed = urllib.parse.urlparse(raw)
            host = parsed.netloc or parsed.path
            # Strip port if present
            host = host.split(":")[0]
            # Strip leading www.
            if host.startswith("www."):
                host = host[4:]
            return host.strip("/").strip()
        except Exception:
            return ""

    @staticmethod
    def normalize_url(url: str) -> str:
        """
        Normalizes a full URL for canonical exact-page matching.
        Strips tracking query params, fragments, trailing slashes, and protocol.
        """
        if not url:
            return ""
        
        raw = url.strip().lower()
        if not raw.startswith("http://") and not raw.startswith("https://"):
            raw = "https://" + raw

        try:
            parsed = urllib.parse.urlparse(raw)
            host = parsed.netloc
            if host.startswith("www."):
                host = host[4:]
            path = parsed.path.rstrip("/")
            return f"{host}{path}"
        except Exception:
            return ""

    @classmethod
    def matches_target(cls, result_url: str, target_domain: str, target_url: Optional[str] = None) -> bool:
        """
        Checks if a result URL matches the target domain or target URL.
        Guards against suffix hijacking (e.g. target 'example.com' will NOT match 'example.com.attacker.com').
        """
        if not result_url:
            return False

        res_host = cls.normalize_host(result_url)
        tgt_host = cls.normalize_host(target_domain)

        if not res_host or not tgt_host:
            return False

        # If specific URL is tracked, check exact normalized URL match first
        if target_url:
            norm_res = cls.normalize_url(result_url)
            norm_tgt = cls.normalize_url(target_url)
            if norm_res == norm_tgt:
                return True

        # Exact hostname match
        if res_host == tgt_host:
            return True

        # Valid subdomain match: res_host ends with '.' + tgt_host (e.g. blog.example.com matches example.com)
        if res_host.endswith("." + tgt_host):
            return True

        return False

    @classmethod
    def find_rank_in_serp(
        cls,
        serp_response: SERPResponse,
        target_domain: str,
        target_url: Optional[str] = None
    ) -> Tuple[Optional[int], Optional[str], str]:
        """
        Searches SERP response for target domain/URL.
        Returns: (rank, ranking_url, serp_type)
          - rank: 1-indexed integer if found, or None if not found in top results.
          - ranking_url: Destination URL of the matched SERP item.
          - serp_type: 'Local Pack' or 'Organic'.
        """
        # 1. Check Local Pack first (high intent for local queries)
        for item in serp_response.local_pack_results:
            if cls.matches_target(item.link, target_domain, target_url):
                return (item.position, item.link, "Local Pack")

        # 2. Check Organic results
        for item in serp_response.organic_results:
            if cls.matches_target(item.link, target_domain, target_url):
                return (item.position, item.link, "Organic")

        # Not found in top checked results
        return (None, None, "Organic")
