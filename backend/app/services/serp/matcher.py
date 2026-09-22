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

    @classmethod
    def get_registrable_domain(cls, url_or_domain: str) -> str:
        """
        Extracts registrable root domain (e.g. 'sub.example.com' -> 'example.com').
        """
        host = cls.normalize_host(url_or_domain)
        parts = host.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return host

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
        if not result_url or not target_domain:
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

    @staticmethod
    def _normalize_name(name: Optional[str]) -> str:
        if not name:
            return ""
        # Lowercase, strip punctuation and extra spaces
        return re.sub(r"[^\w\s]", "", name).strip().lower()

    @staticmethod
    def _normalize_phone(phone: Optional[str]) -> str:
        if not phone:
            return ""
        return re.sub(r"[^\d]", "", phone)

    @classmethod
    def find_rank_in_serp_detailed(
        cls,
        serp_response: SERPResponse,
        target_domain: Optional[str] = None,
        target_url: Optional[str] = None,
        target_place_id: Optional[str] = None,
        business_name: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Tuple[Optional[int], Optional[str], str, Optional[SERPItem]]:
        """
        Searches SERP response using the strongest available identifier:
        1. Place ID / Data CID match
        2. Normalized domain / target URL match
        3. Normalized business name + phone match
        Returns: (rank, ranking_url, serp_type, matched_item)
        """
        clean_target_place = target_place_id.strip() if target_place_id else None
        clean_target_name = cls._normalize_name(business_name)
        clean_target_phone = cls._normalize_phone(phone)

        all_results = [
            (item, "Local Pack") for item in serp_response.local_pack_results
        ] + [
            (item, "Organic") for item in serp_response.organic_results
        ]

        # 1. Strongest match: Place ID
        if clean_target_place:
            for item, s_type in all_results:
                if item.place_id and item.place_id.strip() == clean_target_place:
                    return (item.position, item.link, s_type, item)
                if item.data_cid and item.data_cid.strip() == clean_target_place:
                    return (item.position, item.link, s_type, item)

        # 2. High confidence: Normalized Domain / URL match
        if target_domain or target_url:
            for item, s_type in all_results:
                if cls.matches_target(item.link, target_domain or "", target_url):
                    return (item.position, item.link, s_type, item)

        # 3. Business Name + Phone fallback match
        if clean_target_name and len(clean_target_name) > 2:
            for item, s_type in all_results:
                item_name = cls._normalize_name(item.title)
                if clean_target_name == item_name:
                    # If phone is provided, verify phone alignment to prevent false collision
                    if clean_target_phone and item.phone:
                        if cls._normalize_phone(item.phone) == clean_target_phone:
                            return (item.position, item.link, s_type, item)
                    else:
                        return (item.position, item.link, s_type, item)

        return (None, None, "Organic", None)

    @classmethod
    def find_rank_in_serp(
        cls,
        serp_response: SERPResponse,
        target_domain: str,
        target_url: Optional[str] = None,
        target_place_id: Optional[str] = None,
        business_name: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Tuple[Optional[int], Optional[str], str]:
        """
        Searches SERP response for target domain/URL/Place ID.
        Maintains backward compatibility with 3-tuple return.
        """
        rank, r_url, s_type, _ = cls.find_rank_in_serp_detailed(
            serp_response=serp_response,
            target_domain=target_domain,
            target_url=target_url,
            target_place_id=target_place_id,
            business_name=business_name,
            phone=phone
        )
        return (rank, r_url, s_type)
