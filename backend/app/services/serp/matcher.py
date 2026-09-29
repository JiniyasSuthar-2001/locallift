import re
import urllib.parse
from typing import Optional, Tuple, List, Set, Any
from app.services.serp.base import SERPItem, SERPResponse

class DomainMatcher:
    GENERIC_TERMS: Set[str] = {
        "plumber", "plumbing", "dental", "dentist", "electrician", "electrical",
        "lawyer", "attorney", "seo", "marketing", "agency", "services",
        "center", "centre", "clinic", "solutions", "group", "inc", "llc",
        "ltd", "pvt", "rehab", "care", "home", "hospital", "store", "shop",
        "consulting", "consultant", "foundation", "enterprise", "associates"
    }

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

    @classmethod
    def get_brand_from_domain(cls, domain: Optional[str]) -> str:
        """
        Extracts distinct brand identifier from a domain string.
        Example: 'ihriday.com' -> 'ihriday', 'www.ihriday.com' -> 'ihriday'
        """
        if not domain:
            return ""
        host = cls.normalize_host(domain)
        parts = host.split(".")
        if len(parts) >= 2:
            sld = parts[-2].lower().strip()
            if sld not in cls.GENERIC_TERMS and len(sld) >= 3:
                return sld
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

    @classmethod
    def extract_brand_name(cls, name: Optional[str]) -> str:
        """
        Extracts primary brand name by removing subtitle keywords separated by dashes, colons, or pipes.
        Example: 'iHriday - Occupational therapy in Vadodara...' -> 'ihriday'
        """
        if not name:
            return ""
        chunks = re.split(r"[\-\|\:—,]", name)
        first_chunk = chunks[0].strip()
        clean = cls._normalize_name(first_chunk)
        tokens = [t for t in clean.split() if t not in cls.GENERIC_TERMS]
        if tokens:
            return " ".join(tokens)
        return clean

    @staticmethod
    def _normalize_phone(phone: Optional[str]) -> str:
        if not phone:
            return ""
        return re.sub(r"[^\d]", "", phone)

    @staticmethod
    def _cids_match(cid_a: Optional[str], cid_b: Optional[str]) -> bool:
        """Compares two Google CIDs handling string, decimal, or hex formats."""
        if not cid_a or not cid_b:
            return False
        clean_a = str(cid_a).strip().lower()
        clean_b = str(cid_b).strip().lower()
        if clean_a == clean_b:
            return True
        try:
            # Try parsing hex (e.g. 0xd2cc781ac573e09) to decimal string
            val_a = int(clean_a, 16) if clean_a.startswith("0x") else int(clean_a)
            val_b = int(clean_b, 16) if clean_b.startswith("0x") else int(clean_b)
            return val_a == val_b
        except (ValueError, TypeError):
            return False

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
        Searches SERP response using the evidence-based matching priority:
        1. Exact Google Place ID / Stable Google Business ID (or CID)
        2. Normalized website / target URL match
        3. Distinct Brand Domain match (e.g. ihridayresidentialcare.com vs ihriday.com)
        4. Normalized business name + phone match
        5. Distinct Brand Name prefix match (e.g. 'iHriday Residentialcare' vs 'iHriday')
        Returns: (rank, ranking_url, serp_type, matched_item)
        """
        clean_target_place = target_place_id.strip() if target_place_id else None
        clean_target_name = cls._normalize_name(business_name)
        brand_target_name = cls.extract_brand_name(business_name)
        brand_target_domain = cls.get_brand_from_domain(target_domain)
        clean_target_phone = cls._normalize_phone(phone)

        all_results: List[Tuple[SERPItem, str]] = [
            (item, "Local Pack") for item in (serp_response.local_pack_results or [])
        ] + [
            (item, "Organic") for item in (serp_response.organic_results or [])
        ]

        # 1. Priority 1 (Strongest): Exact Place ID / Data CID match
        if clean_target_place:
            for item, s_type in all_results:
                if item.place_id and item.place_id.strip() == clean_target_place:
                    setattr(item, "matched_by", "place_id")
                    return (item.position, item.link, s_type, item)
                if item.data_cid and cls._cids_match(item.data_cid, clean_target_place):
                    setattr(item, "matched_by", "place_id")
                    return (item.position, item.link, s_type, item)
                if getattr(item, "data_id", None) and str(item.data_id).strip() == clean_target_place:
                    setattr(item, "matched_by", "place_id")
                    return (item.position, item.link, s_type, item)

        # 2. Priority 2: High confidence exact normalized Domain / Target URL match
        if target_domain or target_url:
            for item, s_type in all_results:
                if item.link and cls.matches_target(item.link, target_domain or "", target_url):
                    setattr(item, "matched_by", "domain")
                    return (item.position, item.link, s_type, item)

        # 3. Priority 3: Distinct Brand Domain match
        # If target domain has a distinctive SLD (e.g. 'ihriday' from 'ihriday.com'),
        # and result domain also starts with that brand (e.g. 'ihridayresidentialcare.com'),
        # AND title also contains the brand.
        if brand_target_domain and len(brand_target_domain) >= 3:
            for item, s_type in all_results:
                item_host = cls.normalize_host(item.link or item.domain or "")
                item_title_clean = cls._normalize_name(item.title)
                if item_host and item_host.startswith(brand_target_domain):
                    if brand_target_domain in item_title_clean:
                        setattr(item, "matched_by", "brand_domain")
                        return (item.position, item.link, s_type, item)

        # 4. Priority 4: Business Name + Phone match
        if clean_target_name and clean_target_phone and len(clean_target_phone) >= 6:
            for item, s_type in all_results:
                item_name = cls._normalize_name(item.title)
                item_phone = cls._normalize_phone(item.phone)
                if item_phone and item_phone == clean_target_phone:
                    if clean_target_name == item_name or (brand_target_name and brand_target_name in item_name):
                        setattr(item, "matched_by", "name_phone")
                        return (item.position, item.link, s_type, item)

        # 5. Priority 5: Distinct Brand / Business Name match
        # Exact full name match
        if clean_target_name and len(clean_target_name) >= 3:
            for item, s_type in all_results:
                item_name = cls._normalize_name(item.title)
                if clean_target_name == item_name:
                    setattr(item, "matched_by", "business_name")
                    return (item.position, item.link, s_type, item)

        # Distinct brand prefix match (e.g. 'iHriday' matches 'iHriday Residentialcare')
        if brand_target_name and len(brand_target_name) >= 3 and brand_target_name not in cls.GENERIC_TERMS:
            for item, s_type in all_results:
                item_name = cls._normalize_name(item.title)
                if item_name.startswith(brand_target_name) or brand_target_name.startswith(item_name):
                    setattr(item, "matched_by", "brand_name")
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

    @classmethod
    def find_domain_rank(cls, items_or_serp_response, target_domain: str) -> Optional[int]:
        """
        Finds domain rank position from SERPResponse or items list.
        """
        if not target_domain:
            return None
        if isinstance(items_or_serp_response, SERPResponse):
            rank, _, _ = cls.find_rank_in_serp(items_or_serp_response, target_domain=target_domain)
            return rank
        if isinstance(items_or_serp_response, (list, tuple)):
            for idx, it in enumerate(items_or_serp_response):
                link = getattr(it, "link", None) or (it.get("link") if isinstance(it, dict) else None)
                if link and cls.matches_target(link, target_domain):
                    pos = getattr(it, "position", None) or (it.get("position") if isinstance(it, dict) else None)
                    return pos if pos is not None else (idx + 1)
        return None
