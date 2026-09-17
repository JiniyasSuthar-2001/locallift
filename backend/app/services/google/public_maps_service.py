import re
import urllib.parse
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.connections import PublicBusinessListing
from app.models.project import Project, Location
from app.services.category_taxonomy import CategoryTaxonomy

logger = logging.getLogger("locallift.google.public_maps")

# Common keywords in URL paths that are not business names
GENERIC_MAPS_PATH_SEGMENTS = {
    "maps", "place", "search", "data", "preview", "dir", "viewer", "embed",
    "timeline", "contrib", "reviews", "photos", "u", "0", "1", "2"
}

# Domains that represent short URLs requiring redirect resolution
SHORT_URL_DOMAINS = {
    "goo.gl", "maps.app.goo.gl", "g.page", "g.co", "bit.ly", "tinyurl.com", "t.co", "ow.ly"
}

class PublicGoogleMapsService:
    @classmethod
    async def resolve_url(cls, url: str) -> str:
        """
        Resolves short Google Maps URLs (e.g. maps.app.goo.gl/..., goo.gl/maps/...)
        by following HTTP redirects using httpx.
        """
        if not url or not url.strip():
            return ""

        clean_url = url.strip()
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = f"https://{clean_url}"

        parsed = urllib.parse.urlparse(clean_url)
        domain = (parsed.netloc or "").lower().replace("www.", "")

        # Check if URL is a known short domain or short-link format
        is_short_domain = any(domain == d or domain.endswith(f".{d}") for d in SHORT_URL_DOMAINS)
        is_short_path = "goo.gl" in clean_url or "maps.app" in clean_url

        if is_short_domain or is_short_path:
            try:
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
                async with httpx.AsyncClient(follow_redirects=True, timeout=10.0, headers=headers) as client:
                    resp = await client.get(clean_url)
                    resolved_str = str(resp.url)
                    if resolved_str and resolved_str != clean_url:
                        return resolved_str
            except Exception as e:
                logger.warning(f"Failed to follow redirects for short URL '{clean_url}': {e}")

        return clean_url

    @classmethod
    def parse_maps_url(cls, url: str) -> Dict[str, Any]:
        """
        Extracts business query, place coordinates, or Place ID from a resolved/full Google Maps link.
        Supports:
        - https://www.google.com/maps/place/Business+Name/@lat,lng,zoom/...
        - https://maps.google.com/?q=Business+Name
        - https://www.google.com/maps/search/Business+Name/@lat,lng,...
        - https://www.google.com/maps/search/?api=1&query=Business+Name

        Does NOT fabricate business names from short-code path fragments, ratings, or review counts.
        """
        if not url or not url.strip():
            raise ValueError("Google Maps URL cannot be empty.")

        clean_url = url.strip()
        parsed = urllib.parse.urlparse(clean_url)
        domain = (parsed.netloc or "").lower()
        
        extracted_name = None
        extracted_lat = None
        extracted_lng = None
        extracted_place_id = None
        extracted_address = None

        # 1. Check for /maps/place/Business+Name/@lat,lng or /maps/place/Business+Name/data=...
        place_match = re.search(r'/maps/place/([^/@?#]+)', clean_url)
        if place_match:
            raw_title = place_match.group(1)
            decoded = urllib.parse.unquote_plus(raw_title).replace('+', ' ').strip()
            if decoded.lower() not in GENERIC_MAPS_PATH_SEGMENTS:
                extracted_name = decoded

        # 2. Check for /maps/search/Business+Name/@lat,lng
        if not extracted_name:
            search_match = re.search(r'/maps/search/([^/@?#]+)', clean_url)
            if search_match:
                raw_search = search_match.group(1)
                decoded_search = urllib.parse.unquote_plus(raw_search).replace('+', ' ').strip()
                if decoded_search.lower() not in GENERIC_MAPS_PATH_SEGMENTS:
                    extracted_name = decoded_search

        # 3. Check query parameters ?q=... or ?query=...
        query_params = urllib.parse.parse_qs(parsed.query)
        for q_key in ('q', 'query'):
            if q_key in query_params and not extracted_name:
                q_val = query_params[q_key][0]
                decoded_q = urllib.parse.unquote_plus(q_val).replace('+', ' ').strip()
                if decoded_q.lower() not in GENERIC_MAPS_PATH_SEGMENTS and not decoded_q.startswith("@"):
                    extracted_name = decoded_q

        # 4. Extract coordinates (@lat,lng or !3dlat!4dlng or ll=lat,lng)
        coords_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', clean_url)
        if coords_match:
            try:
                extracted_lat = float(coords_match.group(1))
                extracted_lng = float(coords_match.group(2))
            except ValueError:
                pass
        else:
            data_coords = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', clean_url)
            if data_coords:
                try:
                    extracted_lat = float(data_coords.group(1))
                    extracted_lng = float(data_coords.group(2))
                except ValueError:
                    pass
            elif 'll' in query_params:
                try:
                    ll_parts = query_params['ll'][0].split(',')
                    extracted_lat = float(ll_parts[0])
                    extracted_lng = float(ll_parts[1])
                except Exception:
                    pass

        # 5. Extract Place ID (!1s0x...:0x... or !1sChIJ... or ftid=... or place_id=...)
        place_id_match = re.search(r'!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+|ChIJ[a-zA-Z0-9_-]+)', clean_url)
        if place_id_match:
            extracted_place_id = place_id_match.group(1)
        elif 'ftid' in query_params:
            extracted_place_id = query_params['ftid'][0]
        elif 'place_id' in query_params:
            extracted_place_id = query_params['place_id'][0]
        elif 'cid' in query_params:
            extracted_place_id = query_params['cid'][0]

        # 6. Reject unresolved short-code URLs being used as business names
        # (e.g. if domain is still maps.app.goo.gl or goo.gl, path segment is an opaque short ID)
        if extracted_name:
            # Check if extracted name looks like an opaque short link hash (e.g. "AbCd1234XyZ")
            if any(domain == d or domain.endswith(f".{d}") for d in SHORT_URL_DOMAINS):
                # An unresolved short link must not have its hash treated as a name
                extracted_name = None

        return {
            "name": extracted_name,
            "latitude": extracted_lat,
            "longitude": extracted_lng,
            "place_id": extracted_place_id,
            "formatted_address": extracted_address,
            "rating": None,       # Unknown data MUST remain None
            "review_count": None, # Unknown data MUST remain None
            "original_url": clean_url
        }

    @classmethod
    async def lookup_public_place(
        cls,
        organization_id: int,
        project_id: Optional[int],
        db: AsyncSession,
        business_name: Optional[str] = None,
        location_str: Optional[str] = None,
        maps_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes Google Places API (System A) lookup without requiring user GBP OAuth.
        Returns normalized Place observation and persists to PublicBusinessListing.
        """
        from app.config import settings

        api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", "").strip()
        env = getattr(settings, "ENVIRONMENT", "production").lower()

        # 1. Resolve Maps URL if provided
        resolved_url = None
        extracted_info = {}
        if maps_url and maps_url.strip():
            resolved_url = await cls.resolve_url(maps_url)
            if not resolved_url:
                return {
                    "lookup_status": "invalid_url",
                    "lookup_error": "Unable to resolve the provided Google Maps URL.",
                    "listing": None
                }
            try:
                extracted_info = cls.parse_maps_url(resolved_url)
            except ValueError as ve:
                return {
                    "lookup_status": "invalid_url",
                    "lookup_error": str(ve),
                    "listing": None
                }

        search_query = (business_name or "").strip()
        if location_str and location_str.strip():
            search_query = f"{search_query} in {location_str.strip()}".strip()
        elif extracted_info.get("name"):
            search_query = extracted_info["name"]

        if not search_query and not extracted_info.get("place_id"):
            return {
                "lookup_status": "invalid_url",
                "lookup_error": "Please enter a business name, location, or valid Google Maps URL.",
                "listing": None
            }

        # Check API key configuration (allow mock fixture in testing)
        if not api_key and env != "testing":
            return {
                "lookup_status": "not_configured",
                "lookup_error": "Google Places API key is not configured. Add GOOGLE_PLACES_API_KEY in .env.",
                "listing": None
            }

        # 2. Perform Place Search / Place Details via Google Places API (or testing fallback)
        if env == "testing" and not api_key:
            # Deterministic testing response
            if "not_found" in search_query.lower():
                return {"lookup_status": "not_found", "lookup_error": "No matching Google Place found.", "listing": None}
            elif "ambiguous" in search_query.lower():
                return {"lookup_status": "ambiguous", "lookup_error": "Multiple plausible places found. Please refine location.", "listing": None}
            elif "quota" in search_query.lower():
                return {"lookup_status": "quota_exceeded", "lookup_error": "Google Places API quota exceeded.", "listing": None}

            place_data = {
                "place_id": extracted_info.get("place_id") or f"ChIJ_test_{hash(search_query) % 100000}",
                "name": business_name or extracted_info.get("name") or "Sample Public Business",
                "formatted_address": location_str or "123 Commercial Rd, Sydney NSW 2000",
                "address_components": [{"long_name": "Sydney", "types": ["locality"]}],
                "phone": "+61 2 9876 5432",
                "website_url": "https://example-business.com.au",
                "category": "Local Business",
                "primary_category": "Local Business",
                "business_status": "OPERATIONAL",
                "rating": 4.8,
                "review_count": 42,
                "opening_hours": {"weekday_text": ["Monday: 9:00 AM - 5:00 PM"]},
                "latitude": extracted_info.get("latitude") or -33.8688,
                "longitude": extracted_info.get("longitude") or 151.2093,
                "maps_url": resolved_url or maps_url or "https://maps.google.com/?cid=12345",
                "source": "google_places_api",
                "source_checked_at": datetime.now(timezone.utc),
                "lookup_status": "found",
                "lookup_error": None
            }
        else:
            # Real Google Places HTTP Request
            try:
                headers = {
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.googleMapsUri,places.location,places.businessStatus,places.primaryType"
                }
                body = {"textQuery": search_query}
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post("https://places.googleapis.com/v1/places:searchText", json=body, headers=headers)
                    if resp.status_code in (401, 403):
                        return {"lookup_status": "invalid_credentials", "lookup_error": "Google Places API key is invalid or rejected.", "listing": None}
                    if resp.status_code == 429:
                        return {"lookup_status": "quota_exceeded", "lookup_error": "Google Places API request limit exceeded.", "listing": None}
                    if resp.status_code >= 500:
                        return {"lookup_status": "provider_error", "lookup_error": f"Google Places API server error (HTTP {resp.status_code}).", "listing": None}
                    if resp.status_code != 200:
                        return {"lookup_status": "provider_error", "lookup_error": f"Google Places API error (HTTP {resp.status_code}).", "listing": None}

                    res_json = resp.json()
                    places = res_json.get("places", [])
                    if not places:
                        return {"lookup_status": "not_found", "lookup_error": "No matching Google Place found for query.", "listing": None}
                    if len(places) > 3 and not (business_name and location_str):
                        return {"lookup_status": "ambiguous", "lookup_error": "Multiple plausible places match this query. Please provide location details.", "listing": None}

                    top_place = places[0]
                    displayName = top_place.get("displayName", {}).get("text") or search_query
                    loc = top_place.get("location", {})

                    place_data = {
                        "place_id": top_place.get("id"),
                        "name": displayName,
                        "formatted_address": top_place.get("formattedAddress"),
                        "address_components": None,
                        "phone": top_place.get("nationalPhoneNumber"),
                        "website_url": top_place.get("websiteUri"),
                        "category": top_place.get("primaryType") or "Local Business",
                        "primary_category": top_place.get("primaryType") or "Local Business",
                        "business_status": top_place.get("businessStatus", "OPERATIONAL"),
                        "rating": float(top_place["rating"]) if top_place.get("rating") is not None else None,
                        "review_count": int(top_place["userRatingCount"]) if top_place.get("userRatingCount") is not None else None,
                        "opening_hours": None,
                        "latitude": float(loc.get("latitude")) if loc.get("latitude") is not None else None,
                        "longitude": float(loc.get("longitude")) if loc.get("longitude") is not None else None,
                        "maps_url": top_place.get("googleMapsUri") or resolved_url or maps_url,
                        "source": "google_places_api",
                        "source_checked_at": datetime.now(timezone.utc),
                        "lookup_status": "found",
                        "lookup_error": None
                    }

            except httpx.TimeoutException:
                return {"lookup_status": "timeout", "lookup_error": "Google Places API request timed out.", "listing": None}
            except Exception as e:
                logger.error(f"Google Places API lookup failed: {e}")
                return {"lookup_status": "provider_error", "lookup_error": f"Lookup failed: {str(e)[:150]}", "listing": None}

        # 3. Persist / Update PublicBusinessListing in DB
        conditions = [PublicBusinessListing.organization_id == organization_id]
        if project_id:
            conditions.append(PublicBusinessListing.project_id == project_id)
        if place_data.get("place_id"):
            conditions.append(PublicBusinessListing.place_id == place_data["place_id"])

        stmt = select(PublicBusinessListing).where(*conditions)
        res = await db.execute(stmt)
        listing = res.scalars().first()

        if not listing:
            listing = PublicBusinessListing(
                organization_id=organization_id,
                project_id=project_id,
                place_id=place_data.get("place_id"),
                name=place_data["name"],
                formatted_address=place_data.get("formatted_address"),
                address_components=place_data.get("address_components"),
                phone=place_data.get("phone"),
                website_url=place_data.get("website_url"),
                category=place_data.get("category"),
                primary_category=place_data.get("primary_category"),
                business_status=place_data.get("business_status"),
                rating=place_data.get("rating"),
                review_count=place_data.get("review_count"),
                opening_hours=place_data.get("opening_hours"),
                maps_url=place_data.get("maps_url"),
                latitude=place_data.get("latitude"),
                longitude=place_data.get("longitude"),
                source=place_data.get("source", "google_places_api"),
                source_checked_at=place_data.get("source_checked_at"),
                lookup_status="found",
                lookup_error=None,
                is_managed=False,
                monitoring_status="active",
                last_checked_at=datetime.now(timezone.utc)
            )
            db.add(listing)
        else:
            listing.place_id = place_data.get("place_id") or listing.place_id
            listing.name = place_data["name"]
            listing.formatted_address = place_data.get("formatted_address") or listing.formatted_address
            listing.phone = place_data.get("phone") or listing.phone
            listing.website_url = place_data.get("website_url") or listing.website_url
            listing.category = place_data.get("category") or listing.category
            listing.business_status = place_data.get("business_status") or listing.business_status
            listing.rating = place_data.get("rating") if place_data.get("rating") is not None else listing.rating
            listing.review_count = place_data.get("review_count") if place_data.get("review_count") is not None else listing.review_count
            listing.maps_url = place_data.get("maps_url") or listing.maps_url
            listing.latitude = place_data.get("latitude") if place_data.get("latitude") is not None else listing.latitude
            listing.longitude = place_data.get("longitude") if place_data.get("longitude") is not None else listing.longitude
            listing.source = place_data.get("source", "google_places_api")
            listing.source_checked_at = place_data.get("source_checked_at")
            listing.lookup_status = "found"
            listing.lookup_error = None
            listing.last_checked_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(listing)

        return {
            "lookup_status": "found",
            "lookup_error": None,
            "listing": listing
        }

    @classmethod
    async def import_public_business(
        cls,
        organization_id: int,
        maps_url: str,
        db: AsyncSession,
        project_id: Optional[int] = None,
        target_category: Optional[str] = None,
        business_name: Optional[str] = None
    ) -> PublicBusinessListing:
        """
        Resolves short URLs, parses verified Google Maps business metadata,
        and registers the listing for Public Monitoring without fabricating data.
        """
        if not maps_url or not maps_url.strip():
            raise ValueError("Google Maps URL is required.")

        res = await cls.lookup_public_place(
            organization_id=organization_id,
            project_id=project_id,
            db=db,
            business_name=business_name,
            maps_url=maps_url
        )
        if res.get("listing"):
            return res["listing"]

        resolved_url = await cls.resolve_url(maps_url)
        parsed_data = cls.parse_maps_url(resolved_url)
        biz_name = (business_name or "").strip() or parsed_data.get("name") or "Public Business Listing"

        cat = CategoryTaxonomy.normalize_category_name(target_category) if target_category else "Local Business"

        listing = PublicBusinessListing(
            organization_id=organization_id,
            project_id=project_id,
            place_id=parsed_data.get("place_id"),
            name=biz_name,
            formatted_address=parsed_data.get("formatted_address"),
            primary_category=cat,
            rating=None,
            review_count=None,
            maps_url=resolved_url or maps_url,
            latitude=parsed_data.get("latitude"),
            longitude=parsed_data.get("longitude"),
            lookup_status=res.get("lookup_status", "found"),
            lookup_error=res.get("lookup_error"),
            is_managed=False,
            monitoring_status="active",
            last_checked_at=datetime.now(timezone.utc)
        )
        db.add(listing)
        await db.commit()
        await db.refresh(listing)
        return listing

