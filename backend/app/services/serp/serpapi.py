import asyncio
import hashlib
import logging
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from app.services.serp.base import SERPProvider, SERPResponse, SERPItem, SERPCapabilities
from app.services.serp.matcher import DomainMatcher
from app.services.serp.normalizer import SERPNormalizer

from app.services.serp.location_canonicalizer import LocationCanonicalizer

logger = logging.getLogger("locallift.serp.serpapi")

class SerpApiProvider(SERPProvider):
    BASE_URL = "https://serpapi.com/search.json"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or "").strip().strip("'\"").strip()

    @property
    def capabilities(self) -> SERPCapabilities:
        if not self.is_configured:
            return SERPCapabilities()
        return SERPCapabilities(
            organic_search=True,
            local_search=True,
            maps_search=True,
            coordinate_search=True,
            geo_grid=True,
            maps_reviews=True
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5 and not any(c in self.api_key for c in ("•", "*")))

    @staticmethod
    def _normalize_country(country: Optional[str]) -> str:
        if not country:
            return "us"
        c = str(country).strip().lower()
        country_map = {
            "united states": "us", "united states of america": "us", "usa": "us", "u.s.": "us", "u.s.a.": "us", "us": "us",
            "australia": "au", "australian": "au", "aus": "au", "au": "au",
            "united kingdom": "gb", "great britain": "gb", "uk": "gb", "gb": "gb", "england": "gb",
            "canada": "ca", "can": "ca", "ca": "ca",
            "india": "in", "ind": "in", "in": "in",
            "germany": "de", "deutschland": "de", "de": "de",
            "france": "fr", "fr": "fr",
            "new zealand": "nz", "nz": "nz",
            "ireland": "ie", "ie": "ie",
            "spain": "es", "es": "es",
            "italy": "it", "it": "it",
            "brazil": "br", "br": "br",
            "mexico": "mx", "mx": "mx",
            "south africa": "za", "za": "za",
        }
        return country_map.get(c, c[:2] if len(c) >= 2 else "us")

    @staticmethod
    def _sanitize_location(location: Optional[str]) -> Optional[str]:
        if not location:
            return None
        loc = str(location).strip()
        invalid_placeholders = {
            "metro area", "default", "local", "local area", "national",
            "global", "n/a", "na", "none", "null", "undefined", "all", "target location"
        }
        if loc.lower() in invalid_placeholders or len(loc) < 2:
            return None
        return loc

    async def search_keyword(
        self,
        keyword: str,
        location: Optional[str] = None,
        country: Optional[str] = "us",
        language: Optional[str] = "en",
        device: str = "desktop",
        num_results: int = 100
    ) -> SERPResponse:
        """Executes a real Google Search query via SerpApi."""
        if not self.is_configured:
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=location,
                success=False,
                error_code="SERP_PROVIDER_NOT_CONFIGURED",
                error_message="SerpApi key is not configured. Connect your SerpApi account in Settings to enable keyword tracking and Geo-Grid."
            )

        clean_country = self._normalize_country(country)
        sanitized_loc = self._sanitize_location(location)
        clean_location = LocationCanonicalizer.canonicalize(sanitized_loc, clean_country) or sanitized_loc
        clean_lang = (language or "en").strip().lower()[:2] if language else "en"

        params: Dict[str, Any] = {
            "api_key": self.api_key,
            "engine": "google",
            "q": keyword,
            "gl": clean_country,
            "hl": clean_lang,
            "device": device,
            "num": min(num_results, 100),
            "output": "json"
        }
        if clean_location:
            params["location"] = clean_location

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                logger.info(f"Executing SERP lookup for keyword='{keyword}' location='{clean_location}' gl='{clean_country}'")
                response = await client.get(self.BASE_URL, params=params, headers=headers)

                raw_json = {}
                try:
                    raw_json = response.json()
                except Exception:
                    pass

                api_err = raw_json.get("error") if isinstance(raw_json, dict) else None

                # If SerpApi returned 400 with a location error, report honest location error without silent global fallback
                if response.status_code == 400 and "location" in params:
                    err_msg = str(api_err) if api_err else "Unsupported or unresolvable location specified."
                    logger.error(f"SerpApi HTTP 400 for keyword='{keyword}' with location='{params['location']}': {err_msg}")
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=clean_location,
                        success=False,
                        error_code="SERP_LOCATION_UNSUPPORTED",
                        error_message=f"Location '{clean_location}' is not supported by SerpApi or invalid: {err_msg}"
                    )

                if response.status_code in (401, 403):
                    err_detail = str(api_err) if api_err else "SerpApi authentication error."
                    logger.error(f"SerpApi authentication error: {err_detail}")
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=clean_location,
                        success=False,
                        error_code="SERP_PROVIDER_AUTH_ERROR",
                        error_message=f"SerpApi rejected the API key: {err_detail}"
                    )

                if response.status_code == 429:
                    logger.warning("SerpApi rate limit reached.")
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=clean_location,
                        success=False,
                        error_code="SERP_PROVIDER_RATE_LIMIT",
                        error_message="SerpApi rate limit reached. Please wait and try again."
                    )

                if response.status_code >= 500:
                    logger.error(f"SerpApi returned server status {response.status_code}")
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=clean_location,
                        success=False,
                        error_code="SERP_PROVIDER_ERROR",
                        error_message="SerpApi is temporarily unavailable. Please try again shortly."
                    )

                if response.status_code != 200:
                    err_msg = api_err or (response.text[:200] if response.text else "")
                    logger.error(f"SerpApi returned status {response.status_code}: {err_msg}")
                    return SERPResponse(
                        provider="serpapi",
                        keyword=keyword,
                        location=clean_location,
                        success=False,
                        error_code="SERP_PROVIDER_ERROR",
                        error_message=f"SerpApi error: HTTP {response.status_code} - {err_msg}" if err_msg else f"SerpApi error: HTTP {response.status_code}"
                    )

                data = response.json()
                return self._parse_google_serp_response(data, keyword, clean_location)

        except httpx.TimeoutException:
            logger.error("SerpApi request timed out.")
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=clean_location,
                success=False,
                error_code="SERP_PROVIDER_TIMEOUT",
                error_message="SerpApi did not respond in time. Please try again."
            )
        except Exception as e:
            logger.error(f"SerpApi request failed: {str(e)}")
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=clean_location,
                success=False,
                error_code="SERP_PROVIDER_EXCEPTION",
                error_message=f"SERP lookup failed: {str(e)[:150]}"
            )

    async def search_local_grid_point(
        self,
        keyword: str,
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        zoom: int = 14
    ) -> SERPResponse:
        """Executes a Google Maps / Local search for a discrete geo-grid coordinate."""
        if not self.is_configured:
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=f"@{lat},{lng}",
                success=False,
                error_code="SERP_PROVIDER_NOT_CONFIGURED",
                error_message="SerpApi key is not configured. Connect your SerpApi account in Settings to enable keyword tracking and Geo-Grid."
            )

        params: Dict[str, Any] = {
            "api_key": self.api_key,
            "engine": "google_maps",
            "q": keyword,
            "ll": f"@{lat},{lng},{zoom}z",
            "type": "search",
            "output": "json"
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        max_retries = 3
        backoff_sec = 1.5

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    logger.info(f"Executing Geo-Grid point search keyword='{keyword}' coords=({lat}, {lng}) (attempt {attempt + 1})")
                    response = await client.get(self.BASE_URL, params=params, headers=headers)

                    raw_json = {}
                    try:
                        raw_json = response.json()
                    except Exception:
                        pass

                    api_err = raw_json.get("error") if isinstance(raw_json, dict) else None

                    if response.status_code in (401, 403):
                        err_detail = str(api_err) if api_err else "SerpApi authentication error."
                        return SERPResponse(
                            provider="serpapi",
                            keyword=keyword,
                            location=f"@{lat},{lng}",
                            success=False,
                            error_code="SERP_PROVIDER_AUTH_ERROR",
                            error_message=f"SerpApi rejected the API key: {err_detail}"
                        )

                    if response.status_code == 429:
                        if attempt < max_retries - 1:
                            logger.warning(f"SerpApi 429 rate limit at ({lat}, {lng}). Retrying in {backoff_sec}s...")
                            await asyncio.sleep(backoff_sec)
                            backoff_sec *= 2.0
                            continue
                        return SERPResponse(
                            provider="serpapi",
                            keyword=keyword,
                            location=f"@{lat},{lng}",
                            success=False,
                            error_code="SERP_PROVIDER_RATE_LIMIT",
                            error_message="SerpApi rate limit reached. Please wait and try again."
                        )

                    if response.status_code >= 500:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(backoff_sec)
                            backoff_sec *= 2.0
                            continue
                        return SERPResponse(
                            provider="serpapi",
                            keyword=keyword,
                            location=f"@{lat},{lng}",
                            success=False,
                            error_code="SERP_PROVIDER_ERROR",
                            error_message="SerpApi is temporarily unavailable. Please try again shortly."
                        )

                    if response.status_code != 200:
                        err_msg = api_err or (response.text[:200] if response.text else "")
                        logger.error(f"SerpApi Google Maps returned status {response.status_code}: {err_msg}")
                        return SERPResponse(
                            provider="serpapi",
                            keyword=keyword,
                            location=f"@{lat},{lng}",
                            success=False,
                            error_code="SERP_PROVIDER_ERROR",
                            error_message=f"SerpApi error: HTTP {response.status_code} - {err_msg}" if err_msg else f"SerpApi error: HTTP {response.status_code}"
                        )

                    data = response.json()
                    return self._parse_google_maps_response(data, keyword, f"@{lat},{lng}")

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    await asyncio.sleep(backoff_sec)
                    continue
                logger.error("SerpApi request timed out.")
                return SERPResponse(
                    provider="serpapi",
                    keyword=keyword,
                    location=f"@{lat},{lng}",
                    success=False,
                    error_code="SERP_PROVIDER_TIMEOUT",
                    error_message="SerpApi did not respond in time. Please try again."
                )
            except Exception as e:
                logger.error(f"SerpApi request failed: {str(e)}")
                return SERPResponse(
                    provider="serpapi",
                    keyword=keyword,
                    location=f"@{lat},{lng}",
                    success=False,
                    error_code="SERP_PROVIDER_EXCEPTION",
                    error_message=f"SERP lookup failed: {str(e)[:150]}"
                )

        return SERPResponse(
            provider="serpapi",
            keyword=keyword,
            location=f"@{lat},{lng}",
            success=False,
            error_code="SERP_PROVIDER_TIMEOUT",
            error_message="Geo-Grid request timed out."
        )

    def _parse_google_serp_response(self, data: Dict[str, Any], keyword: str, location: Optional[str]) -> SERPResponse:
        organic_items: List[SERPItem] = []
        local_items: List[SERPItem] = []

        if not isinstance(data, dict):
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=location,
                success=True,
                raw_data=data if isinstance(data, dict) else {}
            )

        # 1. Parse Organic results
        raw_organic = data.get("organic_results", [])
        if isinstance(raw_organic, list):
            for pos, item in enumerate(raw_organic, 1):
                if not isinstance(item, dict):
                    continue
                link = str(item.get("link") or "").strip()
                title = str(item.get("title") or "").strip()
                snippet = str(item.get("snippet") or "") if item.get("snippet") is not None else None
                domain = DomainMatcher.normalize_host(link)

                organic_items.append(
                    SERPItem(
                        position=item.get("position") or pos,
                        title=title,
                        link=link,
                        domain=domain,
                        snippet=snippet,
                        item_type="organic"
                    )
                )

        # 2. Parse Local Pack results if present
        raw_local_val = data.get("local_results")
        raw_local = []
        if isinstance(raw_local_val, dict):
            raw_local = raw_local_val.get("places", [])
        elif isinstance(raw_local_val, list):
            raw_local = raw_local_val

        if isinstance(raw_local, list):
            for pos, place in enumerate(raw_local, 1):
                if not isinstance(place, dict):
                    continue
                link = ""
                if isinstance(place.get("links"), dict):
                    link = place["links"].get("website") or ""
                if not link:
                    link = place.get("website") or place.get("link") or ""
                link = str(link or "").strip()
                title = str(place.get("title") or "").strip()
                address = str(place.get("address") or "").strip() if place.get("address") else None
                phone = str(place.get("phone") or "").strip() if place.get("phone") else None
                rating = place.get("rating")
                reviews = place.get("reviews")
                place_id = place.get("place_id") or place.get("data_id")
                data_cid = place.get("data_cid") or (str(place.get("cid", "")) if place.get("cid") else None)
                domain = DomainMatcher.normalize_host(link)

                local_items.append(
                    SERPItem(
                        position=place.get("position") or pos,
                        title=title,
                        link=link,
                        domain=domain,
                        item_type="local_pack",
                        rating=float(rating) if rating is not None else None,
                        reviews_count=int(reviews) if reviews is not None else None,
                        phone=phone,
                        address=address,
                        place_id=str(place_id) if place_id else None,
                        data_cid=str(data_cid) if data_cid else None
                    )
                )

        return SERPResponse(
            provider="serpapi",
            keyword=keyword,
            location=location,
            organic_results=organic_items,
            local_pack_results=local_items,
            total_results_count=len(organic_items) + len(local_items),
            search_timestamp=datetime.now(timezone.utc),
            success=True,
            raw_data=data
        )

    def _parse_google_maps_response(self, data: Dict[str, Any], keyword: str, location: Optional[str]) -> SERPResponse:
        local_items: List[SERPItem] = []
        if not isinstance(data, dict):
            return SERPResponse(
                provider="serpapi",
                keyword=keyword,
                location=location,
                success=True,
                raw_data=data if isinstance(data, dict) else {}
            )

        raw_places = data.get("local_results", [])
        if isinstance(raw_places, list):
            for pos, place in enumerate(raw_places, 1):
                if not isinstance(place, dict):
                    continue
                link = str(place.get("website") or place.get("link") or "").strip()
                title = str(place.get("title") or "").strip()
                address = str(place.get("address") or "").strip() if place.get("address") else None
                phone = str(place.get("phone") or "").strip() if place.get("phone") else None
                rating = place.get("rating")
                reviews = place.get("reviews")
                place_id = place.get("place_id") or place.get("data_id")
                data_cid = place.get("data_cid") or (str(place.get("cid", "")) if place.get("cid") else None)
                domain = DomainMatcher.normalize_host(link)

                local_items.append(
                    SERPItem(
                        position=place.get("position") or pos,
                        title=title,
                        link=link,
                        domain=domain,
                        item_type="local_pack",
                        rating=float(rating) if rating is not None else None,
                        reviews_count=int(reviews) if reviews is not None else None,
                        category=str(place.get("type") or place.get("category") or "") or None,
                        phone=phone,
                        address=address,
                        place_id=str(place_id) if place_id else None,
                        data_cid=str(data_cid) if data_cid else None
                    )
                )

        return SERPResponse(
            provider="serpapi",
            keyword=keyword,
            location=location,
            organic_results=[],
            local_pack_results=local_items,
            total_results_count=len(local_items),
            search_timestamp=datetime.now(timezone.utc),
            success=True,
            raw_data=data
        )

    async def get_google_maps_reviews(
        self,
        place_id: Optional[str] = None,
        data_id: Optional[str] = None,
        max_pages: int = 5,
        sort_by: str = "qualityScore",
        hl: str = "en"
    ) -> Dict[str, Any]:
        """
        Retrieves public Google Maps reviews using SerpApi engine=google_maps_reviews with pagination.
        Supports Place ID and Data ID identifiers.
        """
        now_dt = datetime.now(timezone.utc)
        clean_place_id = str(place_id).strip() if place_id else None
        clean_data_id = str(data_id).strip() if data_id else None

        if not clean_place_id and not clean_data_id:
            return {
                "provider": "SERPAPI_GOOGLE_MAPS_REVIEWS",
                "place_id": None,
                "data_id": None,
                "success": False,
                "collection_status": "ERROR",
                "error_code": "MISSING_IDENTIFIER",
                "error": "Either place_id or data_id is required to fetch Google Maps reviews.",
                "reviews": [],
                "reviews_returned": 0,
                "total_reviews_on_listing": None,
                "pages_fetched": 0,
                "fetched_at": now_dt.isoformat()
            }

        if not self.is_configured:
            return {
                "provider": "SERPAPI_GOOGLE_MAPS_REVIEWS",
                "place_id": clean_place_id,
                "data_id": clean_data_id,
                "success": False,
                "collection_status": "NOT_CONFIGURED",
                "error_code": "SERP_PROVIDER_NOT_CONFIGURED",
                "error": "SerpApi key is not configured for this organization.",
                "reviews": [],
                "reviews_returned": 0,
                "total_reviews_on_listing": None,
                "pages_fetched": 0,
                "fetched_at": now_dt.isoformat()
            }

        all_reviews: List[Dict[str, Any]] = []
        next_page_token: Optional[str] = None
        pages_fetched = 0
        total_listing_reviews: Optional[int] = None
        avg_rating: Optional[float] = None
        place_title: Optional[str] = None
        collection_error: Optional[str] = None
        collection_error_code: Optional[str] = None
        is_quota_exceeded = False
        is_auth_error = False

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        while pages_fetched < max(1, max_pages):
            params: Dict[str, Any] = {
                "api_key": self.api_key,
                "engine": "google_maps_reviews",
                "hl": (hl or "en").strip().lower()[:2],
                "sort_by": sort_by or "qualityScore",
                "output": "json"
            }
            if clean_place_id:
                params["place_id"] = clean_place_id
            elif clean_data_id:
                params["data_id"] = clean_data_id

            if next_page_token:
                params["next_page_token"] = next_page_token

            max_retries = 3
            backoff_sec = 1.5
            page_data = None

            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        logger.info(
                            f"Fetching SerpApi Google Maps reviews place_id='{clean_place_id}' "
                            f"data_id='{clean_data_id}' page={pages_fetched + 1} (attempt {attempt + 1})"
                        )
                        response = await client.get(self.BASE_URL, params=params, headers=headers)

                        raw_json = {}
                        try:
                            raw_json = response.json()
                        except Exception:
                            pass

                        api_err = raw_json.get("error") if isinstance(raw_json, dict) else None

                        if response.status_code in (401, 403):
                            is_auth_error = True
                            collection_error_code = "SERP_PROVIDER_AUTH_ERROR"
                            collection_error = str(api_err) if api_err else f"SerpApi authentication error (HTTP {response.status_code})"
                            break

                        if response.status_code == 429:
                            err_str = str(api_err or response.text).lower()
                            if "out of searches" in err_str or "quota" in err_str or "limit" in err_str:
                                is_quota_exceeded = True
                                collection_error_code = "SERP_QUOTA_EXCEEDED"
                                collection_error = "SerpApi account has reached its search limit."
                                break
                            if attempt < max_retries - 1:
                                await asyncio.sleep(backoff_sec)
                                backoff_sec *= 2.0
                                continue
                            is_quota_exceeded = True
                            collection_error_code = "SERP_QUOTA_EXCEEDED"
                            collection_error = "SerpApi rate limit reached."
                            break

                        if response.status_code >= 500:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(backoff_sec)
                                backoff_sec *= 2.0
                                continue
                            collection_error_code = "SERP_PROVIDER_ERROR"
                            collection_error = f"SerpApi returned server error HTTP {response.status_code}"
                            break

                        if response.status_code != 200:
                            collection_error_code = "SERP_PROVIDER_ERROR"
                            collection_error = str(api_err) if api_err else f"SerpApi returned HTTP {response.status_code}"
                            break

                        page_data = raw_json
                        break

                except httpx.TimeoutException:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(backoff_sec)
                        continue
                    collection_error_code = "SERP_PROVIDER_TIMEOUT"
                    collection_error = "SerpApi review request timed out."
                    break
                except Exception as e:
                    collection_error_code = "SERP_PROVIDER_EXCEPTION"
                    collection_error = str(e)[:150]
                    break

            if is_auth_error or is_quota_exceeded or not page_data or collection_error:
                break

            pages_fetched += 1

            # Extract place info
            place_info = page_data.get("place_info", {})
            if isinstance(place_info, dict):
                if place_info.get("reviews") is not None:
                    try:
                        total_listing_reviews = int(place_info.get("reviews"))
                    except (ValueError, TypeError):
                        pass
                if place_info.get("rating") is not None:
                    try:
                        avg_rating = float(place_info.get("rating"))
                    except (ValueError, TypeError):
                        pass
                if place_info.get("title"):
                    place_title = str(place_info.get("title")).strip()

            raw_revs = page_data.get("reviews", [])
            if not isinstance(raw_revs, list) or len(raw_revs) == 0:
                break

            for r in raw_revs:
                if not isinstance(r, dict):
                    continue
                user = r.get("user", {}) if isinstance(r.get("user"), dict) else {}
                response_obj = r.get("response", {}) if isinstance(r.get("response"), dict) else {}
                
                author_name = str(user.get("name") or "").strip() or "Google User"
                author_photo = user.get("thumbnail")
                author_uri = user.get("link")
                
                rating_val = r.get("rating")
                try:
                    rating_val = int(round(float(rating_val))) if rating_val is not None else None
                except (ValueError, TypeError):
                    rating_val = None

                snippet = r.get("snippet") or r.get("text") or ""
                if isinstance(r.get("extracted_snippet"), dict):
                    snippet = r.get("extracted_snippet", {}).get("original") or snippet

                r_id = str(r.get("review_id") or r.get("id") or "").strip()
                if not r_id and snippet:
                    r_id = hashlib.sha256(f"{author_name}|{rating_val}|{snippet[:80]}".encode()).hexdigest()[:24]

                all_reviews.append({
                    "external_review_id": r_id or None,
                    "author_name": author_name,
                    "author_photo_url": author_photo,
                    "author_uri": author_uri,
                    "rating": rating_val,
                    "review_text": snippet,
                    "review_date_raw": r.get("date"),
                    "provider_url": r.get("link"),
                    "response_text": response_obj.get("snippet") or response_obj.get("text"),
                    "response_date_raw": response_obj.get("date"),
                    "source": "Google",
                    "provider": "SERPAPI_GOOGLE_MAPS_REVIEWS",
                    "access_mode": "PUBLIC",
                    "verification_status": "OBSERVED",
                    "raw_data": r
                })

            pagination = page_data.get("serpapi_pagination", {})
            next_page_token = pagination.get("next_page_token") if isinstance(pagination, dict) else None
            if not next_page_token:
                break

        # Determine collection status
        if is_quota_exceeded:
            status = "QUOTA_EXCEEDED"
        elif is_auth_error:
            status = "ERROR"
        elif collection_error and len(all_reviews) == 0:
            status = "ERROR"
        elif total_listing_reviews is not None and len(all_reviews) < total_listing_reviews:
            status = "PARTIAL"
        elif next_page_token is None and not collection_error:
            status = "COMPLETE"
        elif len(all_reviews) > 0:
            status = "PARTIAL"
        else:
            status = "NOT_AVAILABLE"

        return {
            "provider": "SERPAPI_GOOGLE_MAPS_REVIEWS",
            "place_id": clean_place_id,
            "data_id": clean_data_id,
            "success": bool(len(all_reviews) > 0 or (status == "COMPLETE" and total_listing_reviews == 0)),
            "collection_status": status,
            "reviews": all_reviews,
            "reviews_returned": len(all_reviews),
            "total_reviews_on_listing": total_listing_reviews,
            "pages_fetched": pages_fetched,
            "average_rating": avg_rating,
            "place_title": place_title,
            "error": collection_error,
            "error_code": collection_error_code,
            "fetched_at": now_dt.isoformat()
        }

