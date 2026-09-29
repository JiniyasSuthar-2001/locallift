"""
LocalLift — Open-Web Citation Discovery, Listing Verification & NAP Extraction Engine

Strict identity-verification model:
  HIGH confidence   → VERIFIED (page fetched) / OBSERVED (SERP only with strong signal)
    Triggers: exact domain | exact name+phone | exact name+strong address | Place ID
  MEDIUM confidence → PARTIAL_MATCH (page fetched, exact name + city/partial address)
  LOW confidence    → UNABLE_TO_VERIFY (name-word overlap only)
  NOT_RELEVANT      → different business or no identity signal

NEVER accepted as citation:
  - Keyword/city/generic-word overlap alone
  - Competitor pages ranking for the same keyword
  - Pages where extracted schema name belongs to a different business
  - TIMEOUT on page fetch (→ UNABLE_TO_VERIFY, not fabricated VERIFIED)
"""

from typing import Optional, Dict, Any, List, Tuple, Set
import urllib.parse
import re
import json
import logging
import asyncio
import time
from datetime import datetime, timezone
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.local_seo import Citation

logger = logging.getLogger("locallift.local_seo.citation_service")

# ── Discovery tuning constants ─────────────────────────────────────────────
MAX_SERP_QUERIES = 8
MAX_CANDIDATES = 20                   # Cap candidate URLs before page fetching
MAX_SERP_QUERY_CONCURRENCY = 3        # Concurrent SERP queries
MAX_PAGE_FETCH_CONCURRENCY = 4        # Concurrent page fetches
GLOBAL_DISCOVERY_BUDGET_SECONDS = 90.0
PAGE_FETCH_TIMEOUT_SECONDS = 8.0


class ConfidenceLevel:
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


# Generic words that MUST NOT be used alone as identity proof
GENERIC_BUSINESS_WORDS: Set[str] = {
    "the", "and", "pty", "ltd", "inc", "llc", "co", "pvt", "corp",
    "services", "solutions", "group", "enterprise", "associates",
    "center", "centre", "clinic", "hospital", "care", "home",
    "shop", "store", "agency", "consulting", "foundation",
    "residential", "commercial", "local", "national", "global"
}

# Search engine and aggregator domains to reject as directory listings
SEARCH_ENGINE_DOMAINS: Set[str] = {
    "google.com", "google.com.au", "google.co.uk", "google.ca", "google.co.in",
    "bing.com", "duckduckgo.com", "yahoo.com", "search.yahoo.com", "baidu.com",
    "yandex.com", "ecosia.org", "ask.com", "aol.com", "startpage.com"
}

# Generic non-listing paths to reject
INVALID_PATH_PATTERNS = [
    r"^/?$",
    r"^/search",
    r"^/find",
    r"^/categories",
    r"^/category",
    r"^/browse",
    r"^/tag",
    r"^/tags",
    r"^/c/",
    r"^/topics?",
    r"^/login",
    r"^/signin",
    r"^/signup",
    r"^/register",
    r"^/claim",
    r"^/get-listed",
    r"^/add-business",
    r"^/add-listing",
    r"^/add",
    r"^/new",
    r"^/business/?$",
    r"^/biz/?$",
    r"^/sites/?$",
    r"^/places/?$",
    r"^/directory/?$",
    r"^/profile/?$",
    r"^/contact-us/?$",
    r"^/contact/?$",
    r"^/privacy-policy/?$",
    r"^/privacy/?$",
    r"^/terms-of-service/?$",
    r"^/terms/?$",
    r"^/about-us/?$",
    r"^/about/?$"
]

# Query parameters indicating search/filtering/pagination rather than a specific listing
SEARCH_QUERY_PARAMS = [
    "q", "query", "find_desc", "find_loc", "search", "where", "what", "keywords", "keyword",
    "s", "k", "searchTerm", "location", "near", "category_id", "cat", "page", "p"
]

# Tracking query parameters to strip when canonicalizing
TRACKING_PARAMS = [
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "msclkid", "ref", "source", "view", "_ga"
]


class CitationService:
    """
    Validates, verifies, discovers, and extracts NAP data from open-web citation sources.
    """

    @staticmethod
    def canonicalize_url(url: Optional[str]) -> Optional[str]:
        """
        Normalizes a URL to a stable canonical form for deduplication.
        Strips tracking parameters, lowercases domain, removes trailing slashes and hashes.
        """
        if not url or not str(url).strip():
            return None

        u_str = str(url).strip()
        has_scheme = u_str.lower().startswith(("http://", "https://"))
        if not has_scheme:
            u_str = "https://" + u_str

        try:
            parsed = urllib.parse.urlparse(u_str)
            scheme = parsed.scheme.lower() if parsed.scheme else "https"
            netloc = parsed.netloc.lower().replace("www.", "")
            path = parsed.path.rstrip("/")
            if not path:
                path = ""

            # Filter tracking query parameters
            query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
            filtered_query = [
                (k, v) for k, v in query_items
                if k.lower() not in TRACKING_PARAMS
            ]
            clean_query = urllib.parse.urlencode(filtered_query)

            canonical = f"{scheme}://{netloc}{path}"
            if clean_query:
                canonical = f"{canonical}?{clean_query}"
            return canonical
        except Exception:
            return u_str.rstrip("/")

    @staticmethod
    def extract_domain_from_url(url: Optional[str]) -> str:
        """Extracts clean root/registerable domain from URL."""
        if not url:
            return ""
        try:
            parsed = urllib.parse.urlparse(url if url.lower().startswith(("http://", "https://")) else f"https://{url}")
            netloc = parsed.netloc.lower().replace("www.", "")
            return netloc
        except Exception:
            return ""

    @classmethod
    def build_open_web_discovery_queries(cls, canonical_identity: Dict[str, Any], max_queries: int = 8) -> List[str]:
        """
        Builds dynamic multi-query search strings based on canonical business identity.
        """
        b_name = (canonical_identity.get("business_name") or "").strip()
        b_city = (canonical_identity.get("city") or "").strip()
        b_state = (canonical_identity.get("state") or "").strip()
        b_phone = (canonical_identity.get("phone") or "").strip()
        b_address = (canonical_identity.get("address") or "").strip()
        b_website = (canonical_identity.get("website") or "").strip()
        business_domain = cls.extract_domain_from_url(b_website)

        queries: List[str] = []
        if b_name and b_city and b_phone:
            queries.append(f'"{b_name}" "{b_city}" "{b_phone}"')
        if b_name and b_address:
            queries.append(f'"{b_name}" "{b_address}"')
        if b_name and b_city:
            queries.append(f'"{b_name}" "{b_city}"')
        if b_name and b_phone and f'"{b_name}" "{b_phone}"' not in queries:
            queries.append(f'"{b_name}" "{b_phone}"')
        if b_name and business_domain:
            queries.append(f'"{b_name}" "{business_domain}"')
        if b_name and b_city:
            queries.append(f'"{b_name}" "{b_city}" directory')
            queries.append(f'"{b_name}" "{b_city}" reviews')
        if b_name and b_state:
            queries.append(f'"{b_name}" "{b_state}"')

        queries = queries[:max_queries]
        if not queries and b_name:
            queries.append(f'"{b_name}"')
        return queries

    @classmethod
    def is_valid_business_listing_url(
        cls,
        url: str,
        expected_domain: Optional[str] = None,
        business_domain: Optional[str] = None,
        project_domain: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Generic listing URL validator that works across arbitrary domains without requiring a hardcoded catalog.
        Rejects homepages, search engines, query pages, category listings, auth, and business's own domain.
        """
        if not url or not str(url).strip():
            return False, "URL is empty"

        target_project_domain = business_domain or project_domain

        u_str = str(url).strip()
        if not u_str.lower().startswith(("http://", "https://")):
            u_str = "https://" + u_str

        try:
            parsed = urllib.parse.urlparse(u_str)
        except Exception:
            return False, "URL could not be parsed"

        netloc = parsed.netloc.lower().replace("www.", "")
        if not netloc:
            return False, "Invalid URL host"

        # 1. Reject search engines
        if netloc in SEARCH_ENGINE_DOMAINS or any(netloc.endswith(f".{se}") for se in SEARCH_ENGINE_DOMAINS):
            return False, f"URL belongs to a search engine ({netloc}), not a directory listing"

        # 2. Reject business's own website/domain
        if target_project_domain:
            b_dom = target_project_domain.lower().replace("www.", "").strip()
            if b_dom and (netloc == b_dom or netloc.endswith(f".{b_dom}") or b_dom.endswith(f".{netloc}")):
                return False, "URL is the project's own website, not an external citation listing"

        # 3. If expected_domain is explicitly provided, verify domain match
        if expected_domain:
            exp_dom = expected_domain.lower().replace("www.", "").strip()
            if exp_dom and exp_dom not in netloc and netloc not in exp_dom:
                return False, f"URL domain '{netloc}' does not match expected directory domain '{exp_dom}'"

        # 4. Check for root / homepage (must not be root)
        path = parsed.path.rstrip("/")
        if not path or path == "":
            return False, "URL points to directory homepage, not a specific business listing"

        # 5. Check for invalid path patterns (search / categories / auth / generic)
        for pattern in INVALID_PATH_PATTERNS:
            if re.match(pattern, path, re.IGNORECASE):
                return False, f"URL path '{path}' is a search/category/generic directory landing path"

        # 6. Check for search query parameters
        if parsed.query:
            query_dict = urllib.parse.parse_qs(parsed.query)
            for param in SEARCH_QUERY_PARAMS:
                if param in query_dict:
                    return False, f"URL contains search/filter query parameter '{param}'"

        # 7. Path depth check: Must have meaningful slug or identifier
        segments = [s for s in path.split("/") if s]
        if len(segments) == 1 and segments[0].lower() in ["search", "find", "categories", "category", "biz", "sites", "profile", "explore", "listing", "business", "company", "tags", "tag", "login", "claim", "claim-business", "get-listed"]:
            return False, "URL lacks specific business profile identifier slug"

        return True, "Valid business listing URL structure"

    @classmethod
    async def fetch_and_extract_page(
        cls,
        url: str,
        client: Optional[httpx.AsyncClient] = None
    ) -> Dict[str, Any]:
        """
        Safely attempts to fetch the HTML of an external citation page and extracts
        JSON-LD Schema markup, title, meta description, and visible contact signals.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }

        should_close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers)
            should_close_client = True

        res_data: Dict[str, Any] = {
            "fetch_success": False,
            "fetch_status": "error",
            "http_status": None,
            "resolved_url": url,
            "title": "",
            "meta_description": "",
            "body_text": "",
            "schema_entities": [],
            "extracted_phones": [],
            "extracted_addresses": [],
            "extracted_names": [],
            "extracted_websites": [],
            "found_name": None,
            "found_phone": None,
            "found_address": None,
            "found_website": None,
            "error_type": None,
            "error_message": None
        }

        try:
            resp = await client.get(url)
            res_data["http_status"] = resp.status_code
            res_data["resolved_url"] = str(resp.url)

            if resp.status_code != 200:
                res_data["error_type"] = f"HTTP_{resp.status_code}"
                res_data["error_message"] = f"Listing page returned HTTP {resp.status_code}"
                res_data["fetch_status"] = "error"
                return res_data

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                res_data["error_type"] = "NON_HTML_CONTENT"
                res_data["error_message"] = f"Non-HTML content type: {content_type}"
                res_data["fetch_status"] = "error"
                return res_data

            html = resp.text[:500000]  # Limit to 500KB
            res_data["fetch_success"] = True
            res_data["fetch_status"] = "success"

            # 1. Extract <title>
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            if title_match:
                res_data["title"] = re.sub(r"\s+", " ", title_match.group(1)).strip()

            # 2. Extract <meta name="description">
            meta_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.IGNORECASE)
            if not meta_match:
                meta_match = re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']', html, re.IGNORECASE)
            if meta_match:
                res_data["meta_description"] = re.sub(r"\s+", " ", meta_match.group(1)).strip()

            # 3. Parse JSON-LD scripts
            json_ld_matches = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.IGNORECASE | re.DOTALL)
            for raw_json in json_ld_matches:
                try:
                    data = json.loads(raw_json.strip())
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if isinstance(item, dict):
                            # Flatten @graph if present
                            if "@graph" in item and isinstance(item["@graph"], list):
                                for g_item in item["@graph"]:
                                    if isinstance(g_item, dict):
                                        res_data["schema_entities"].append(g_item)
                            else:
                                res_data["schema_entities"].append(item)
                except Exception:
                    pass

            # Extract schema signals
            for entity in res_data["schema_entities"]:
                stype = str(entity.get("@type", "")).lower()
                if any(t in stype for t in ["localbusiness", "organization", "restaurant", "store", "dentist", "medical", "professional", "place"]):
                    if entity.get("name"):
                        res_data["extracted_names"].append(str(entity["name"]))
                    if entity.get("telephone"):
                        res_data["extracted_phones"].append(str(entity["telephone"]))
                    if entity.get("url"):
                        res_data["extracted_websites"].append(str(entity["url"]))

                    addr = entity.get("address")
                    if isinstance(addr, dict):
                        parts = [addr.get("streetAddress"), addr.get("addressLocality"), addr.get("addressRegion"), addr.get("postalCode")]
                        full_addr = ", ".join([str(p).strip() for p in parts if p and str(p).strip()])
                        if full_addr:
                            res_data["extracted_addresses"].append(full_addr)
                    elif isinstance(addr, str) and addr.strip():
                        res_data["extracted_addresses"].append(addr.strip())

            # 4. Extract visible body text (clean HTML tags)
            clean_text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r"<style[^>]*>.*?</style>", " ", clean_text, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r"<[^>]+>", " ", clean_text)
            clean_text = re.sub(r"\s+", " ", clean_text).strip()
            res_data["body_text"] = clean_text[:50000]

            # 5. Extract tel: links and phone patterns
            tel_links = re.findall(r'href=["\']tel:([^"\']+)["\']', html, re.IGNORECASE)
            for t in tel_links:
                clean_tel = re.sub(r"[^\d\+]", "", t)
                if len(clean_tel) >= 8:
                    res_data["extracted_phones"].append(t.strip())

            # Populate top found fields
            if res_data["extracted_names"]:
                res_data["found_name"] = res_data["extracted_names"][0]
            if res_data["extracted_phones"]:
                res_data["found_phone"] = res_data["extracted_phones"][0]
            if res_data["extracted_addresses"]:
                res_data["found_address"] = res_data["extracted_addresses"][0]
            if res_data["extracted_websites"]:
                res_data["found_website"] = res_data["extracted_websites"][0]

        except httpx.TimeoutException:
            res_data["error_type"] = "TIMEOUT"
            res_data["error_message"] = "Page fetch timed out after 8 seconds"
            res_data["fetch_status"] = "error"
        except httpx.HTTPStatusError as hse:
            res_data["error_type"] = f"HTTP_{hse.response.status_code}"
            res_data["error_message"] = str(hse)
            res_data["fetch_status"] = "error"
        except Exception as e:
            res_data["error_type"] = "NETWORK_ERROR"
            res_data["error_message"] = str(e)
            res_data["fetch_status"] = "error"
        finally:
            if should_close_client:
                await client.aclose()

        return res_data

    @classmethod
    def match_identity(
        cls,
        canonical_identity: Dict[str, Any],
        extracted_data: Dict[str, Any],
        serp_item: Optional[Dict[str, Any]] = None,
        listing_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        STRICT evidence-based identity verification.

        HIGH confidence (-> VERIFIED if page fetched, OBSERVED if domain/place-ID only in SERP):
          - Exact canonical website/domain match
          - Exact business name + exact phone
          - Exact business name + strong address (>=70% token overlap)
          - Place ID match

        MEDIUM confidence (-> PARTIAL_MATCH, only if page was fetched):
          - Exact business name in fetched page + city observed in page body
          - Exact business name in schema + no phone/address confirmation

        LOW confidence (-> UNABLE_TO_VERIFY, never VERIFIED):
          - SERP title/snippet contains full business name, but page not fetched
          - Name-word overlap (partial match)

        NOT_RELEVANT:
          - Schema name on page clearly belongs to a DIFFERENT business
          - No name signal at all

        NEVER: keyword overlap alone, city alone, generic-word overlap alone
        NEVER: fabricate found_name, found_phone, found_address, found_website
        """
        b_name = (canonical_identity.get("business_name") or "").strip()
        b_phone = (canonical_identity.get("phone") or "").strip()
        b_address = (canonical_identity.get("address") or "").strip()
        b_city = (canonical_identity.get("city") or "").strip()
        b_state = (canonical_identity.get("state") or "").strip()
        b_website = (canonical_identity.get("website") or "").strip()

        # Schema-extracted signals from page
        ext_names = list(extracted_data.get("extracted_names") or [])
        ext_phones = list(extracted_data.get("extracted_phones") or [])
        ext_addresses = list(extracted_data.get("extracted_addresses") or [])
        ext_websites = list(extracted_data.get("extracted_websites") or [])
        page_title = (extracted_data.get("title") or "")
        page_desc = (extracted_data.get("meta_description") or "")
        body_text = (extracted_data.get("body_text") or "")

        # SERP signals (SERP title alone is NOT identity — it's often a category page or competitor title)
        serp_title = ((serp_item.get("title") if serp_item else "") or "")
        serp_snippet = ((serp_item.get("snippet") if serp_item else "") or "")
        serp_place_id = ((serp_item.get("place_id") if serp_item else "") or "")

        fetch_success = extracted_data.get("fetch_success", False)
        fetch_error = extracted_data.get("error_type")

        evidence_signals: List[str] = []
        rejection_reasons: List[str] = []

        # ── Signal 1: Place ID ──────────────────────────────────────────────
        b_place_id = (canonical_identity.get("place_id") or "").strip()
        place_id_match = bool(
            b_place_id and serp_place_id
            and b_place_id.strip() == serp_place_id.strip()
        )
        if place_id_match:
            evidence_signals.append(f"PLACE_ID_MATCH ({b_place_id})")

        # ── Signal 2: Website / Domain ─────────────────────────────────────
        domain_match = False
        b_domain = cls.extract_domain_from_url(b_website)
        if b_domain:
            for ew in ext_websites:
                ew_domain = cls.extract_domain_from_url(ew)
                if ew_domain and b_domain == ew_domain:
                    domain_match = True
                    evidence_signals.append(f"EXACT_DOMAIN_IN_SCHEMA ({ew_domain})")
                    break
            if not domain_match:
                # Check if domain referenced in page body/title (not SERP snippet)
                page_full = (page_title + " " + page_desc + " " + body_text).lower()
                if b_domain in page_full:
                    domain_match = True
                    evidence_signals.append(f"DOMAIN_REFERENCED_IN_PAGE ({b_domain})")

        # ── Signal 3: Business Name ────────────────────────────────────────
        b_name_lower = b_name.lower()
        b_name_norm = re.sub(r"[^\w\s]", "", b_name_lower).strip()
        b_distinctive_tokens = [
            w for w in b_name_norm.split()
            if w not in GENERIC_BUSINESS_WORDS and len(w) >= 3
        ]

        # EXACT name match = the full business name string appears verbatim in the fetched page or schema
        # We do NOT check against SERP snippet/title for HIGH/MEDIUM confidence — those are competitor-polluted
        exact_name_in_schema = any(
            b_name_lower in n.lower() or n.lower() in b_name_lower
            for n in ext_names if n and len(n.strip()) >= 3
        )
        exact_name_in_page_title = fetch_success and b_name_lower in page_title.lower()
        exact_name_in_body = fetch_success and bool(body_text) and b_name_lower in body_text.lower()

        strong_name_match = exact_name_in_schema or exact_name_in_page_title or exact_name_in_body

        # SERP-only name presence (only for LOW tier — page not fetched)
        serp_name_present = b_name_lower in (serp_title + " " + serp_snippet).lower()

        if exact_name_in_schema:
            evidence_signals.append("EXACT_NAME_IN_SCHEMA")
        elif exact_name_in_page_title:
            evidence_signals.append("EXACT_NAME_IN_PAGE_TITLE")
        elif exact_name_in_body:
            evidence_signals.append("EXACT_NAME_IN_BODY_TEXT")
        elif serp_name_present and not fetch_success:
            evidence_signals.append("EXACT_NAME_IN_SERP_ONLY (LOW confidence)")

        # Detect if page clearly belongs to a DIFFERENT business
        different_business_detected = False
        page_schema_name = extracted_data.get("found_name")  # Schema-extracted only
        if page_schema_name and b_name:
            fn_lower = page_schema_name.lower()
            fn_tokens = set(re.sub(r"[^\w\s]", "", fn_lower).split()) - GENERIC_BUSINESS_WORDS
            b_tokens_set = set(b_distinctive_tokens)
            if fn_tokens and b_tokens_set:
                overlap = len(fn_tokens & b_tokens_set) / max(len(b_tokens_set), 1)
                if overlap < 0.3:
                    different_business_detected = True
                    rejection_reasons.append(
                        f"DIFFERENT_BUSINESS: schema name '{page_schema_name}' has <30% token overlap with target '{b_name}'"
                    )

        # ── Signal 4: Phone ────────────────────────────────────────────────
        phone_match = False
        matched_phone: Optional[str] = None
        if b_phone:
            b_phone_digits = re.sub(r"\D", "", b_phone)
            b_phone_last10 = b_phone_digits[-10:] if len(b_phone_digits) >= 10 else b_phone_digits
            for ep in ext_phones:
                ep_digits = re.sub(r"\D", "", str(ep))
                ep_last10 = ep_digits[-10:] if len(ep_digits) >= 10 else ep_digits
                if b_phone_last10 and ep_last10 and len(b_phone_last10) >= 8 and b_phone_last10 == ep_last10:
                    phone_match = True
                    matched_phone = ep
                    evidence_signals.append(f"EXACT_PHONE_IN_SCHEMA ({ep})")
                    break
            if not phone_match and b_phone_last10 and len(b_phone_last10) >= 8 and fetch_success and body_text:
                body_digits = re.sub(r"\D", "", body_text)
                if b_phone_last10 in body_digits:
                    phone_match = True
                    matched_phone = b_phone
                    evidence_signals.append(f"PHONE_FOUND_IN_BODY ({b_phone})")

        phone_status = "match" if phone_match else ("mismatch" if (ext_phones and not phone_match) else "missing")

        # ── Signal 5: Address ──────────────────────────────────────────────
        address_match = False
        address_partial = False
        matched_address: Optional[str] = None

        def _norm_addr(raw: str) -> str:
            a = raw.lower()
            for pat, rep in [
                (r"\bstreet\b", "st"), (r"\broad\b", "rd"), (r"\bavenue\b", "ave"),
                (r"\bboulevard\b", "blvd"), (r"\bdrive\b", "dr"), (r"\bcourt\b", "ct"),
                (r"\bplace\b", "pl"), (r"\bsuite\b", "ste"), (r"\bapartment\b", "apt")
            ]:
                a = re.sub(pat, rep, a)
            return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", a)).strip()

        if b_address and ext_addresses:
            norm_b = _norm_addr(b_address)
            for ea in ext_addresses:
                norm_ea = _norm_addr(ea)
                b_tok = set(norm_b.split()) - GENERIC_BUSINESS_WORDS
                ea_tok = set(norm_ea.split()) - GENERIC_BUSINESS_WORDS
                if b_tok and ea_tok:
                    overlap = len(b_tok & ea_tok) / max(len(b_tok), 1)
                    if norm_b in norm_ea or norm_ea in norm_b or overlap >= 0.7:
                        address_match = True
                        matched_address = ea
                        evidence_signals.append(f"STRONG_ADDRESS_MATCH (overlap={overlap:.2f})")
                        break
                    elif overlap >= 0.4:
                        address_partial = True
                        matched_address = ea

        # City in PAGE body (not SERP snippet — SERP snippet always contains city for local queries)
        b_city_lower = b_city.lower() if b_city else ""
        city_in_page = (
            fetch_success
            and bool(b_city_lower)
            and b_city_lower in (page_title + " " + body_text).lower()
        )
        address_status = "match" if address_match else ("partial_match" if (address_partial or city_in_page) else "missing")

        # ── Confidence Tier Logic ──────────────────────────────────────────
        confidence_level = ConfidenceLevel.NONE

        if different_business_detected:
            confidence_level = ConfidenceLevel.NONE
        elif place_id_match:
            confidence_level = ConfidenceLevel.HIGH
            evidence_signals.append("TIER: HIGH (Place ID)")
        elif domain_match:
            confidence_level = ConfidenceLevel.HIGH
            evidence_signals.append("TIER: HIGH (Exact Domain)")
        elif strong_name_match and phone_match:
            confidence_level = ConfidenceLevel.HIGH
            evidence_signals.append("TIER: HIGH (Exact Name + Phone)")
        elif strong_name_match and address_match:
            confidence_level = ConfidenceLevel.HIGH
            evidence_signals.append("TIER: HIGH (Exact Name + Strong Address)")
        elif strong_name_match and (address_partial or city_in_page) and fetch_success:
            confidence_level = ConfidenceLevel.MEDIUM
            evidence_signals.append("TIER: MEDIUM (Exact Name + City in Page)")
        elif strong_name_match and fetch_success:
            confidence_level = ConfidenceLevel.MEDIUM
            evidence_signals.append("TIER: MEDIUM (Exact Name in Page, no address/phone)")
        elif serp_name_present and not fetch_success:
            confidence_level = ConfidenceLevel.LOW
            evidence_signals.append("TIER: LOW (Name in SERP only, page not fetched)")
        else:
            confidence_level = ConfidenceLevel.NONE
            if not strong_name_match and not serp_name_present:
                rejection_reasons.append("NO_NAME_SIGNAL: Target business name not found in page content or SERP result")
            else:
                rejection_reasons.append("INSUFFICIENT_EVIDENCE: Only keyword/generic/city word overlap detected — insufficient for identity")

        # ── Confidence Score ───────────────────────────────────────────────
        base_scores = {
            ConfidenceLevel.HIGH: 0.85,
            ConfidenceLevel.MEDIUM: 0.50,
            ConfidenceLevel.LOW: 0.20,
            ConfidenceLevel.NONE: 0.00
        }
        confidence_score = base_scores[confidence_level]
        if phone_match:
            confidence_score = min(0.99, confidence_score + 0.05)
        if address_match:
            confidence_score = min(0.99, confidence_score + 0.05)
        if domain_match:
            confidence_score = min(0.99, confidence_score + 0.05)

        # ── Determine Verification/Status ──────────────────────────────────
        # found_name comes ONLY from schema — never from SERP title or page title
        final_found_name = extracted_data.get("found_name")  # Schema-extracted only; None if not found
        final_found_phone = matched_phone if phone_match else None
        final_found_address = matched_address if (address_match or address_partial) else None
        final_found_website: Optional[str] = None
        if domain_match and ext_websites:
            final_found_website = ext_websites[0]

        if confidence_level == ConfidenceLevel.HIGH:
            if fetch_success:
                verification_status = "VERIFIED"
                status = "listed"
                nap_status = "mismatch" if (phone_status == "mismatch" or address_status == "mismatch") else "consistent"
            elif place_id_match or domain_match:
                # Strong SERP-only signal (domain or place ID) — OBSERVED, not VERIFIED
                verification_status = "OBSERVED"
                status = "listed"
                nap_status = "not_checked"
            else:
                # name+phone/address but page fetch failed — cannot confirm without page
                verification_status = "UNABLE_TO_VERIFY"
                status = "unable_to_verify"
                nap_status = "not_checked"
        elif confidence_level == ConfidenceLevel.MEDIUM:
            if fetch_success:
                verification_status = "PARTIAL_MATCH"
                status = "listed"
                nap_status = "not_checked"
            else:
                verification_status = "UNABLE_TO_VERIFY"
                status = "unable_to_verify"
                nap_status = "not_checked"
        elif confidence_level == ConfidenceLevel.LOW:
            verification_status = "UNABLE_TO_VERIFY"
            status = "unable_to_verify"
            nap_status = "not_checked"
            rejection_reasons.append("LOW_CONFIDENCE: SERP-only name signal, not sufficient for listing")
        else:  # NONE
            if different_business_detected:
                verification_status = "NOT_RELEVANT"
            else:
                verification_status = "NOT_RELEVANT"
            status = "not_relevant"
            nap_status = "not_checked"

        field_matches = {
            "business_name": "MATCH" if strong_name_match else ("SERP_ONLY" if serp_name_present else "NOT_FOUND"),
            "name": "MATCH" if strong_name_match else ("SERP_ONLY" if serp_name_present else "NOT_FOUND"),
            "phone": phone_status.upper(),
            "address": address_status.upper(),
            "website": "MATCH" if domain_match else "MISSING"
        }

        return {
            "verified": verification_status in ("VERIFIED", "OBSERVED"),
            "status": status,
            "verification_status": verification_status,
            "confidence_level": confidence_level,
            "nap_status": nap_status,
            "confidence": round(confidence_score, 2),
            "found_name": final_found_name,     # Schema-only; never fabricated
            "found_phone": final_found_phone,
            "found_address": final_found_address,
            "found_website": final_found_website,
            "listing_url": listing_url,
            "field_matches": field_matches,
            "evidence": {
                "confidence_level": confidence_level,
                "evidence_signals": evidence_signals,
                "rejection_reasons": rejection_reasons,
                "field_matches": field_matches,
                "identity_score": round(confidence_score, 2),
                "page_fetch_status": "success" if fetch_success else (fetch_error or "error"),
                "page_http_status": extracted_data.get("http_status"),
                "fetch_error": fetch_error,
                "schema_detected": len(extracted_data.get("schema_entities", [])) > 0,
                "schema_name_extracted": bool(extracted_data.get("found_name")),
                "different_business_detected": different_business_detected,
                "verified_at": datetime.now(timezone.utc).isoformat()
            }
        }

    @classmethod
    def verify_citation_from_serp_item(
        cls,
        serp_item: Any,
        expected_domain: Optional[str],
        canonical_identity: Dict[str, Any],
        search_query: str
    ) -> Dict[str, Any]:
        """
        Evaluates a SERP result item against canonical business identity.
        Preserves backward compatibility while enforcing strict listing URL validation.
        """
        item_link = getattr(serp_item, "link", None) or (serp_item.get("link") if isinstance(serp_item, dict) else None)
        item_title = getattr(serp_item, "title", None) or (serp_item.get("title") if isinstance(serp_item, dict) else "")
        item_snippet = getattr(serp_item, "snippet", None) or (serp_item.get("snippet") if isinstance(serp_item, dict) else "")

        if not item_link:
            return {
                "verified": False,
                "listing_url": None,
                "status": "missing",
                "nap_status": "not_checked",
                "verification_status": "NOT_VERIFIED",
                "confidence": None,
                "evidence": {"search_query": search_query, "reason": "No listing URL returned in search results"}
            }

        # Validate URL structure
        business_dom = cls.extract_domain_from_url(canonical_identity.get("website"))
        is_valid_url, url_reason = cls.is_valid_business_listing_url(item_link, expected_domain=expected_domain, business_domain=business_dom)
        if not is_valid_url:
            return {
                "verified": False,
                "listing_url": None,
                "status": "missing",
                "nap_status": "not_checked",
                "verification_status": "NOT_VERIFIED",
                "confidence": None,
                "evidence": {
                    "search_query": search_query,
                    "rejected_url": item_link,
                    "rejection_reason": url_reason
                }
            }

        extracted_mock = {
            "fetch_success": False,
            "error_type": "SERP_ONLY",
            "title": item_title,
            "meta_description": item_snippet,
            "body_text": "",
            "schema_entities": [],
            "extracted_phones": [],
            "extracted_addresses": [],
            "extracted_names": [],
            "extracted_websites": []
        }

        serp_dict = {"title": item_title, "snippet": item_snippet, "link": item_link}
        res = cls.match_identity(
            canonical_identity=canonical_identity,
            extracted_data=extracted_mock,
            serp_item=serp_dict,
            listing_url=item_link
        )
        res["evidence"]["search_query"] = search_query
        return res

    @classmethod
    async def discover_open_web_citations(
        cls,
        project_id: int,
        canonical_identity: Dict[str, Any],
        serp_provider: Any,
        db: AsyncSession,
        max_queries: int = 8
    ) -> Dict[str, Any]:
        """
        Executes open-web citation discovery across multiple dynamic queries.
        Collects organic results, deduplicates by canonicalized URL, fetches and extracts page NAP,
        and persists verified citations into the database.
        """
        b_name = (canonical_identity.get("business_name") or "").strip()
        b_city = (canonical_identity.get("city") or "").strip()
        b_state = (canonical_identity.get("state") or "").strip()
        b_phone = (canonical_identity.get("phone") or "").strip()
        b_address = (canonical_identity.get("address") or "").strip()
        b_website = (canonical_identity.get("website") or "").strip()
        b_country = (canonical_identity.get("country") or "").strip()

        business_domain = cls.extract_domain_from_url(b_website)

        # 1. Build open-web query candidates
        queries: List[str] = []
        if b_name and b_city and b_phone:
            queries.append(f'"{b_name}" "{b_city}" "{b_phone}"')
        if b_name and b_address:
            queries.append(f'"{b_name}" "{b_address}"')
        if b_name and b_city:
            queries.append(f'"{b_name}" "{b_city}"')
        if b_name and b_phone and f'"{b_name}" "{b_phone}"' not in queries:
            queries.append(f'"{b_name}" "{b_phone}"')
        if b_name and business_domain:
            queries.append(f'"{b_name}" "{business_domain}"')
        if b_name and b_city:
            queries.append(f'"{b_name}" "{b_city}" directory')
            queries.append(f'"{b_name}" "{b_city}" reviews')
        if b_name and b_state:
            queries.append(f'"{b_name}" "{b_state}"')

        # Limit queries
        queries = queries[:max_queries]
        if not queries and b_name:
            queries.append(f'"{b_name}"')

        logger.info(
            f"[CITATION_DISCOVERY] Project #{project_id} | Business: '{b_name}' | "
            f"Queries: {len(queries)}"
        )
        discovery_start = time.monotonic()
        scan_errors: List[str] = []

        # 2. Run SERP queries concurrently (max 3 at a time)
        serp_semaphore = asyncio.Semaphore(MAX_SERP_QUERY_CONCURRENCY)
        discovered_urls_map: Dict[str, Dict[str, Any]] = {}

        async def _run_serp(query: str) -> None:
            if time.monotonic() - discovery_start > GLOBAL_DISCOVERY_BUDGET_SECONDS * 0.5:
                return
            async with serp_semaphore:
                try:
                    serp_res = await serp_provider.search_keyword(
                        keyword=query,
                        location=f"{b_city}, {b_state}".strip(", ") if (b_city or b_state) else None,
                        country=b_country,
                        num_results=10
                    )
                    if serp_res and serp_res.success:
                        items = (serp_res.organic_results or []) + (serp_res.local_pack_results or [])
                        for pos, item in enumerate(items, 1):
                            raw_link = getattr(item, "link", None) or (item.get("link") if isinstance(item, dict) else None)
                            if not raw_link:
                                continue
                            canon_url = cls.canonicalize_url(raw_link)
                            if not canon_url or canon_url in discovered_urls_map:
                                continue
                            if len(discovered_urls_map) >= MAX_CANDIDATES:
                                break
                            is_valid, _r = cls.is_valid_business_listing_url(canon_url, business_domain=business_domain)
                            if not is_valid:
                                continue
                            title = getattr(item, "title", None) or (item.get("title") if isinstance(item, dict) else "")
                            snippet = getattr(item, "snippet", None) or (item.get("snippet") if isinstance(item, dict) else "")
                            place_id = getattr(item, "place_id", None) or (item.get("place_id") if isinstance(item, dict) else None)
                            discovered_urls_map[canon_url] = {
                                "url": raw_link, "canonical_url": canon_url,
                                "title": title, "snippet": snippet,
                                "position": pos, "query": query, "place_id": place_id
                            }
                    elif serp_res and not serp_res.success:
                        scan_errors.append(f"SERP '{query}': {getattr(serp_res, 'error_message', '')}")
                except Exception as exc:
                    scan_errors.append(f"SERP '{query}' error: {str(exc)[:80]}")

        if serp_provider and getattr(serp_provider, "is_configured", True):
            await asyncio.gather(*(_run_serp(q) for q in queries))
        else:
            scan_errors.append("SERP provider not configured")

        logger.info(
            f"[CITATION_DISCOVERY] {len(discovered_urls_map)} candidates "
            f"(elapsed: {time.monotonic() - discovery_start:.1f}s)"
        )

        # 3. Fetch and verify pages concurrently (max 4 at a time)
        now = datetime.now(timezone.utc)
        verified_citations: List[Dict[str, Any]] = []
        rejected_candidates: List[Dict[str, Any]] = []
        fetch_semaphore = asyncio.Semaphore(MAX_PAGE_FETCH_CONCURRENCY)
        http_hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "text/html,*/*;q=0.8"}

        async def _fetch_verify(item_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            elapsed = time.monotonic() - discovery_start
            dom = cls.extract_domain_from_url(item_info["url"])
            src_name = dom.split(".")[0].capitalize() if dom else "Directory Listing"
            _base = {"source_name": src_name, "domain": dom, "listing_url": item_info["url"],
                     "citation_type": "OPEN_WEB_DISCOVERED", "source_type": "open_web_search",
                     "found_name": None, "found_phone": None, "found_address": None, "found_website": None}
            if elapsed > GLOBAL_DISCOVERY_BUDGET_SECONDS * 0.9:
                return {**_base, "status": "unable_to_verify", "nap_status": "not_checked",
                        "verification_status": "UNABLE_TO_VERIFY", "confidence_level": ConfidenceLevel.NONE,
                        "confidence": 0.0, "evidence": {"rejection_reasons": ["BUDGET_EXCEEDED"],
                        "matched_query": item_info["query"], "serp_position": item_info["position"]},
                        "_accepted": False, "_rejection_reason": "BUDGET_EXCEEDED"}
            async with fetch_semaphore:
                async with httpx.AsyncClient(timeout=PAGE_FETCH_TIMEOUT_SECONDS, follow_redirects=True, headers=http_hdrs) as hc:
                    extracted = await cls.fetch_and_extract_page(item_info["url"], client=hc)
            match_res = cls.match_identity(
                canonical_identity=canonical_identity,
                extracted_data=extracted,
                serp_item={"title": item_info.get("title", ""), "snippet": item_info.get("snippet", ""), "place_id": item_info.get("place_id")},
                listing_url=item_info["url"]
            )
            match_res["evidence"].update({
                "matched_query": item_info["query"], "serp_position": item_info["position"],
                "discovered_url": item_info["url"], "serp_title": item_info.get("title", ""),
                "serp_snippet": item_info.get("snippet", "")
            })
            return {**_base, "status": match_res["status"], "nap_status": match_res["nap_status"],
                    "verification_status": match_res["verification_status"],
                    "confidence_level": match_res.get("confidence_level", ConfidenceLevel.NONE),
                    "confidence": match_res["confidence"], "evidence": match_res["evidence"],
                    "found_name": match_res.get("found_name"), "found_phone": match_res.get("found_phone"),
                    "found_address": match_res.get("found_address"), "found_website": match_res.get("found_website"),
                    "_accepted": match_res["status"] not in ("not_relevant",),
                    "_rejection_reason": "; ".join(match_res["evidence"].get("rejection_reasons", []))}

        if discovered_urls_map:
            fr_list = await asyncio.gather(*(_fetch_verify(i) for i in discovered_urls_map.values()), return_exceptions=True)
            for fr in fr_list:
                if isinstance(fr, Exception):
                    scan_errors.append(f"Fetch error: {str(fr)[:80]}")
                elif fr is not None:
                    if fr.get("_accepted"):
                        verified_citations.append(fr)
                    else:
                        rejected_candidates.append(fr)
                        logger.info(f"[CITATION_DISCOVERY] REJECTED {fr.get('listing_url','')} | {fr.get('_rejection_reason','')}")

        # 4. Upsert with project_id-scoped keys to prevent cross-project collisions
        existing_res = await db.execute(select(Citation).where(Citation.project_id == project_id))
        existing_list = existing_res.scalars().all()
        existing_by_url = {cls.canonicalize_url(c.listing_url): c for c in existing_list if c.listing_url}
        # project_id prefix prevents cross-project domain collisions
        existing_by_dom = {f"{project_id}:{c.domain.lower()}": c for c in existing_list if c.domain}

        new_count = 0
        updated_count = 0

        for vc in verified_citations:
            c_url = cls.canonicalize_url(vc["listing_url"])
            dom_key = f"{project_id}:{vc['domain'].lower()}"
            existing = existing_by_url.get(c_url) or existing_by_dom.get(dom_key)

            if existing:
                if existing.source_type != "manual" or not existing.listing_url:
                    existing.listing_url = vc["listing_url"]
                    existing.status = vc["status"]
                    existing.nap_status = vc["nap_status"]
                    existing.verification_status = vc["verification_status"]
                    existing.confidence = vc["confidence"]
                    existing.evidence = vc["evidence"]
                    existing.found_name = vc["found_name"]
                    existing.found_phone = vc["found_phone"]
                    existing.found_address = vc["found_address"]
                    existing.found_website = vc["found_website"]
                    existing.last_checked_at = now
                    updated_count += 1
            else:
                db.add(Citation(
                    project_id=project_id,
                    source_name=vc["source_name"],
                    domain=vc["domain"],
                    listing_url=vc["listing_url"],
                    domain_authority=None,
                    category="General Directory",
                    status=vc["status"],
                    nap_status=vc["nap_status"],
                    citation_type=vc["citation_type"],
                    verification_status=vc["verification_status"],
                    confidence=vc["confidence"],
                    evidence=vc["evidence"],
                    found_name=vc["found_name"],
                    found_phone=vc["found_phone"],
                    found_address=vc["found_address"],
                    found_website=vc["found_website"],
                    source_type=vc["source_type"],
                    last_checked_at=now
                ))
                new_count += 1

        await db.commit()
        elapsed = time.monotonic() - discovery_start
        scan_status = "completed"
        if scan_errors:
            scan_status = "completed_with_errors" if verified_citations else "failed"

        logger.info(
            f"[CITATION_DISCOVERY] Done | Project #{project_id} | "
            f"Elapsed={elapsed:.1f}s | Queries={len(queries)} | "
            f"Candidates={len(discovered_urls_map)} | Accepted={len(verified_citations)} | "
            f"Rejected={len(rejected_candidates)} | New={new_count} | Updated={updated_count}"
        )

        return {
            "project_id": project_id,
            "queries_executed": len(queries),
            "candidates_found": len(discovered_urls_map),
            "verified_citations": len(verified_citations),
            "rejected_candidates": len(rejected_candidates),
            "new_citations_added": new_count,
            "existing_citations_updated": updated_count,
            "elapsed_seconds": round(elapsed, 1),
            "scan_status": scan_status,
            "scan_errors": scan_errors[:10],
            "rejection_summary": [
                {
                    "url": r.get("listing_url", ""),
                    "reason": r.get("_rejection_reason", ""),
                    "verification_status": r.get("verification_status", "")
                }
                for r in rejected_candidates[:20]
            ]
        }

