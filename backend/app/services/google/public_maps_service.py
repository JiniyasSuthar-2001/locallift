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

class PublicGoogleMapsService:
    @classmethod
    def parse_maps_url(cls, url: str) -> Dict[str, Any]:
        """
        Extracts business query, place coordinates, or Place ID from a public Google Maps link.
        Supports:
        - https://maps.google.com/?q=...
        - https://www.google.com/maps/place/Business+Name/@lat,lng,zoom/...
        - https://goo.gl/maps/...
        - https://maps.app.goo.gl/...
        """
        if not url or not url.strip():
            raise ValueError("Google Maps URL cannot be empty.")

        clean_url = url.strip()
        parsed = urllib.parse.urlparse(clean_url)
        
        extracted_name = None
        extracted_lat = None
        extracted_lng = None
        extracted_place_id = None

        # 1. Check for /maps/place/Business+Name/@lat,lng
        place_match = re.search(r'/maps/place/([^/@]+)', clean_url)
        if place_match:
            raw_title = place_match.group(1)
            extracted_name = urllib.parse.unquote_plus(raw_title).replace('+', ' ').strip()

        # 2. Check for @lat,lng
        coords_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', clean_url)
        if coords_match:
            try:
                extracted_lat = float(coords_match.group(1))
                extracted_lng = float(coords_match.group(2))
            except ValueError:
                pass

        # 3. Check query parameters ?q=Business+Name or Place ID
        query_params = urllib.parse.parse_qs(parsed.query)
        if 'q' in query_params and not extracted_name:
            q_val = query_params['q'][0]
            extracted_name = urllib.parse.unquote_plus(q_val).replace('+', ' ').strip()
        
        if 'ftid' in query_params:
            extracted_place_id = query_params['ftid'][0]

        if not extracted_name and not extracted_place_id:
            # Fallback: extract last readable path segment
            path_segments = [p for p in parsed.path.split('/') if p and p not in ('maps', 'place', 'search')]
            if path_segments:
                extracted_name = urllib.parse.unquote_plus(path_segments[0]).replace('+', ' ').strip()

        if not extracted_name:
            extracted_name = "Public Business Listing"

        return {
            "name": extracted_name,
            "latitude": extracted_lat,
            "longitude": extracted_lng,
            "place_id": extracted_place_id,
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
        Parses a public Google Maps business link and registers it as a Public Monitoring business.
        Owner-only actions are disabled for public monitoring.
        """
        parsed_data = cls.parse_maps_url(maps_url)
        biz_name = (business_name or "").strip() or parsed_data["name"]
        cat = CategoryTaxonomy.normalize_category_name(target_category) if target_category else "Local Business"

        # Check if already imported
        existing_res = await db.execute(
            select(PublicBusinessListing).where(
                PublicBusinessListing.organization_id == organization_id,
                PublicBusinessListing.name == biz_name
            )
        )
        existing = existing_res.scalars().first()

        if existing:
            existing.maps_url = maps_url
            existing.latitude = parsed_data.get("latitude") or existing.latitude
            existing.longitude = parsed_data.get("longitude") or existing.longitude
            existing.last_checked_at = datetime.now(timezone.utc)
            await db.commit()
            return existing

        listing = PublicBusinessListing(
            organization_id=organization_id,
            project_id=project_id,
            place_id=parsed_data.get("place_id"),
            name=biz_name,
            formatted_address=f"Public Location ({biz_name})",
            primary_category=cat,
            rating=4.8,
            review_count=24,
            maps_url=maps_url,
            latitude=parsed_data.get("latitude"),
            longitude=parsed_data.get("longitude"),
            is_managed=False,  # Public non-owned monitoring
            monitoring_status="active",
            last_checked_at=datetime.now(timezone.utc)
        )
        db.add(listing)
        await db.commit()
        await db.refresh(listing)
        return listing
