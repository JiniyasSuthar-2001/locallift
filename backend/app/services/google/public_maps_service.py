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

        # 1. Resolve short links by following HTTP redirects
        resolved_url = await cls.resolve_url(maps_url)

        # 2. Extract verified business data from the resolved URL
        parsed_data = cls.parse_maps_url(resolved_url)

        # 3. Determine business name
        biz_name = (business_name or "").strip() or parsed_data.get("name")
        if not biz_name:
            raise ValueError(
                "Unable to resolve this Google Maps short link or extract business details. "
                "Please provide a full Google Maps place link or enter the business name."
            )

        cat = CategoryTaxonomy.normalize_category_name(target_category) if target_category else "Local Business"

        # 4. Check for existing import (deduplicate by organization_id and name or place_id)
        conditions = [
            PublicBusinessListing.organization_id == organization_id,
            PublicBusinessListing.name == biz_name
        ]
        if parsed_data.get("place_id"):
            conditions = [
                PublicBusinessListing.organization_id == organization_id,
                (PublicBusinessListing.name == biz_name) | (PublicBusinessListing.place_id == parsed_data["place_id"])
            ]

        existing_res = await db.execute(select(PublicBusinessListing).where(*conditions))
        existing = existing_res.scalars().first()

        if existing:
            existing.maps_url = resolved_url or maps_url
            if parsed_data.get("latitude") is not None:
                existing.latitude = parsed_data.get("latitude")
            if parsed_data.get("longitude") is not None:
                existing.longitude = parsed_data.get("longitude")
            if parsed_data.get("place_id"):
                existing.place_id = parsed_data.get("place_id")
            existing.rating = parsed_data.get("rating")
            existing.review_count = parsed_data.get("review_count")
            existing.last_checked_at = datetime.now(timezone.utc)
            await db.commit()
            return existing

        # 5. Create clean public listing with honest/verified data only
        listing = PublicBusinessListing(
            organization_id=organization_id,
            project_id=project_id,
            place_id=parsed_data.get("place_id"),
            name=biz_name,
            formatted_address=parsed_data.get("formatted_address"),
            primary_category=cat,
            rating=None,        # Honest None: do NOT fabricate rating
            review_count=None,  # Honest None: do NOT fabricate review count
            maps_url=resolved_url or maps_url,
            latitude=parsed_data.get("latitude"),
            longitude=parsed_data.get("longitude"),
            is_managed=False,   # Public non-owned monitoring
            monitoring_status="active",
            last_checked_at=datetime.now(timezone.utc)
        )
        db.add(listing)
        await db.commit()
        await db.refresh(listing)
        return listing
