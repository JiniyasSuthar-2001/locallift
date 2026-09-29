import logging
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.project import Project, Location
from app.models.local_seo import BusinessProfile
from app.models.gbp import GoogleBusinessProfile
from app.models.connections import PublicBusinessListing
from app.services.geocoding import GeocodingService

logger = logging.getLogger("locallift.grid_location_resolver")


class GeoGridLocationResult:
    def __init__(
        self,
        latitude: float,
        longitude: float,
        location_precision: str,  # EXACT, ADDRESS_RESOLVED, CITY_LEVEL, UNKNOWN
        center_source: str,       # USER_PROVIDED_COORDINATES, STORED_BUSINESS_COORDINATES, GOOGLE_PLACES, PLACE_ID_RESOLVED, GEOCODED_ADDRESS, CITY_FALLBACK
        center_name: str,
        center_address: Optional[str] = None,
        location_entity: Optional[Location] = None,
        target_place_id: Optional[str] = None,
        target_url: Optional[str] = None,
        business_name: Optional[str] = None,
        phone: Optional[str] = None,
        warning_message: Optional[str] = None
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.location_precision = location_precision
        self.center_source = center_source
        self.center_name = center_name
        self.center_address = center_address
        self.location_entity = location_entity
        self.target_place_id = target_place_id
        self.target_url = target_url
        self.business_name = business_name
        self.phone = phone
        self.warning_message = warning_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "center_lat": self.latitude,
            "center_lng": self.longitude,
            "location_precision": self.location_precision,
            "center_source": self.center_source,
            "center_name": self.center_name,
            "center_address": self.center_address,
            "target_place_id": self.target_place_id,
            "target_url": self.target_url,
            "business_name": self.business_name,
            "phone": self.phone,
            "warning_message": self.warning_message
        }


class GeoGridLocationResolver:
    """
    Authoritative service to resolve the most accurate business center coordinates
    for Geo-Grid scans based on strict multi-level precision hierarchy:

    Priority 1: Explicit User-Provided Coordinates
    Priority 2: Stored Verified Coordinates in LocalLift (Location / GBP / BusinessProfile)
    Priority 3: Google Places / Place ID Resolved Coordinates
    Priority 4: Full Street Address Geocoding (with landmark stripping fallback)
    Priority 5: Structured Suburb / Postal Code Geocoding
    Priority 6: City / State Fallback (marked explicitly as CITY_LEVEL precision)
    """

    @classmethod
    async def resolve_business_center(
        cls,
        db: AsyncSession,
        project_id: int,
        location_id: Optional[int] = None,
        explicit_lat: Optional[float] = None,
        explicit_lng: Optional[float] = None,
        explicit_center_name: Optional[str] = None
    ) -> GeoGridLocationResult:
        # 1. Fetch Project with relations
        proj_res = await db.execute(
            select(Project)
            .options(selectinload(Project.locations))
            .where(Project.id == project_id)
        )
        project = proj_res.scalars().first()
        if not project:
            raise ValueError(f"Project with ID {project_id} not found.")

        # 2. Fetch associated business records
        loc_res = None
        target_loc: Optional[Location] = None
        if location_id is not None:
            l_stmt = select(Location).where(Location.id == location_id, Location.project_id == project_id)
            l_exec = await db.execute(l_stmt)
            target_loc = l_exec.scalars().first()
        elif project.locations:
            target_loc = project.locations[0]

        bp_res = await db.execute(select(BusinessProfile).where(BusinessProfile.project_id == project_id))
        bp: Optional[BusinessProfile] = bp_res.scalars().first()

        gbp_res = await db.execute(select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id))
        gbp: Optional[GoogleBusinessProfile] = gbp_res.scalars().first()

        pbl_res = await db.execute(select(PublicBusinessListing).where(PublicBusinessListing.project_id == project_id))
        pbl: Optional[PublicBusinessListing] = pbl_res.scalars().first()

        # Resolve Business Identity
        resolved_business_name = (
            (gbp.business_name if gbp and gbp.business_name else None)
            or (bp.business_name if bp and bp.business_name else None)
            or project.name
        )

        target_place_id = (
            (target_loc.place_id if target_loc and target_loc.place_id else None)
            or (gbp.place_id if gbp and gbp.place_id else None)
            or (bp.place_id if bp and bp.place_id else None)
            or (pbl.place_id if pbl and pbl.place_id else None)
        )

        target_url = (
            (gbp.website_url if gbp and gbp.website_url else None)
            or (bp.website if bp and bp.website else None)
            or (f"https://{project.domain}" if project.domain else None)
        )

        resolved_phone = (
            (target_loc.phone if target_loc and target_loc.phone else None)
            or (gbp.phone if gbp and gbp.phone else None)
            or (bp.primary_phone if bp and bp.primary_phone else None)
        )

        # Full address candidate
        full_address = (
            (target_loc.address if target_loc and target_loc.address else None)
            or (bp.primary_address if bp and bp.primary_address else None)
            or (gbp.address if gbp and gbp.address else None)
            or (pbl.formatted_address if pbl and pbl.formatted_address else None)
        )

        city = (
            (target_loc.city if target_loc and target_loc.city else None)
            or (bp.city if bp and bp.city else None)
            or (gbp.city if gbp and gbp.city else None)
        )

        state = (
            (target_loc.state if target_loc and target_loc.state else None)
            or (bp.state if bp and bp.state else None)
            or (gbp.state if gbp and gbp.state else None)
        )

        postal_code = (
            (target_loc.postal_code if target_loc and target_loc.postal_code else None)
            or (bp.postal_code if bp and bp.postal_code else None)
            or (gbp.postal_code if gbp and gbp.postal_code else None)
        )

        country = (
            (target_loc.country if target_loc and target_loc.country else None)
            or (bp.country if bp and bp.country else None)
            or (gbp.country if gbp and gbp.country else None)
            or project.country
            or "us"
        )

        center_name = (
            explicit_center_name
            or (target_loc.name if target_loc and target_loc.name else None)
            or resolved_business_name
            or "Business Location"
        )

        # ── Priority 1: Explicit User-Provided Coordinates ──
        if explicit_lat is not None and explicit_lng is not None:
            if (-90.0 <= explicit_lat <= 90.0) and (-180.0 <= explicit_lng <= 180.0) and (explicit_lat != 0.0 or explicit_lng != 0.0):
                return GeoGridLocationResult(
                    latitude=explicit_lat,
                    longitude=explicit_lng,
                    location_precision="EXACT",
                    center_source="USER_PROVIDED_COORDINATES",
                    center_name=center_name,
                    center_address=full_address,
                    location_entity=target_loc,
                    target_place_id=target_place_id,
                    target_url=target_url,
                    business_name=resolved_business_name,
                    phone=resolved_phone
                )

        # ── Priority 2: Stored Verified Coordinates ──
        stored_coords = None
        stored_source = None

        if target_loc and target_loc.latitude is not None and target_loc.longitude is not None:
            if (-90.0 <= target_loc.latitude <= 90.0) and (-180.0 <= target_loc.longitude <= 180.0) and (target_loc.latitude != 0.0 or target_loc.longitude != 0.0):
                stored_coords = (target_loc.latitude, target_loc.longitude)
                stored_source = "STORED_BUSINESS_COORDINATES"

        if not stored_coords and gbp and gbp.latitude is not None and gbp.longitude is not None:
            if (-90.0 <= gbp.latitude <= 90.0) and (-180.0 <= gbp.longitude <= 180.0) and (gbp.latitude != 0.0 or gbp.longitude != 0.0):
                stored_coords = (gbp.latitude, gbp.longitude)
                stored_source = "GOOGLE_PLACES"

        if not stored_coords and bp and bp.latitude is not None and bp.longitude is not None:
            if (-90.0 <= bp.latitude <= 90.0) and (-180.0 <= bp.longitude <= 180.0) and (bp.latitude != 0.0 or bp.longitude != 0.0):
                stored_coords = (bp.latitude, bp.longitude)
                stored_source = "STORED_BUSINESS_COORDINATES"

        if not stored_coords and pbl and pbl.latitude is not None and pbl.longitude is not None:
            if (-90.0 <= pbl.latitude <= 90.0) and (-180.0 <= pbl.longitude <= 180.0) and (pbl.latitude != 0.0 or pbl.longitude != 0.0):
                stored_coords = (pbl.latitude, pbl.longitude)
                stored_source = "GOOGLE_PLACES"

        if stored_coords:
            return GeoGridLocationResult(
                latitude=stored_coords[0],
                longitude=stored_coords[1],
                location_precision="EXACT",
                center_source=stored_source or "STORED_BUSINESS_COORDINATES",
                center_name=center_name,
                center_address=full_address,
                location_entity=target_loc,
                target_place_id=target_place_id,
                target_url=target_url,
                business_name=resolved_business_name,
                phone=resolved_phone
            )

        # ── Priority 3: Place ID Resolution ──
        if target_place_id:
            try:
                # 1. Check if public business listing has coordinates for this place ID
                if pbl and pbl.place_id == target_place_id and pbl.latitude and pbl.longitude:
                    return GeoGridLocationResult(
                        latitude=pbl.latitude,
                        longitude=pbl.longitude,
                        location_precision="EXACT",
                        center_source="PLACE_ID_RESOLVED",
                        center_name=center_name,
                        center_address=pbl.address or full_address,
                        location_entity=target_loc,
                        target_place_id=target_place_id,
                        target_url=target_url,
                        business_name=resolved_business_name,
                        phone=resolved_phone
                    )

                # 2. Check if Google Places API Key is configured
                from app.config import settings
                import httpx
                if settings.GOOGLE_PLACES_API_KEY:
                    places_url = f"https://places.googleapis.com/v1/places/{target_place_id}"
                    headers = {
                        "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
                        "X-Goog-FieldMask": "location,formattedAddress,displayName"
                    }
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.get(places_url, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            loc_data = data.get("location", {})
                            p_lat = loc_data.get("latitude")
                            p_lng = loc_data.get("longitude")
                            p_addr = data.get("formattedAddress")

                            if p_lat is not None and p_lng is not None:
                                if target_loc:
                                    target_loc.latitude = p_lat
                                    target_loc.longitude = p_lng
                                    if not target_loc.address and p_addr:
                                        target_loc.address = p_addr
                                    await db.commit()
                                elif bp:
                                    bp.latitude = p_lat
                                    bp.longitude = p_lng
                                    await db.commit()

                                return GeoGridLocationResult(
                                    latitude=p_lat,
                                    longitude=p_lng,
                                    location_precision="EXACT",
                                    center_source="PLACE_ID_RESOLVED",
                                    center_name=center_name,
                                    center_address=p_addr or full_address,
                                    location_entity=target_loc,
                                    target_place_id=target_place_id,
                                    target_url=target_url,
                                    business_name=resolved_business_name,
                                    phone=resolved_phone
                                )
            except Exception as pe:
                logger.debug(f"Place ID coordinate lookup skipped/failed: {pe}")

        # ── Priority 4: Full Street Address Geocoding ──
        if full_address:
            geo_coords = await GeocodingService.geocode_full_address(
                full_address=full_address,
                city=city,
                state=state,
                postal_code=postal_code,
                country=country
            )
            if geo_coords:
                lat, lng = geo_coords
                # Save to location for future fast lookups
                if target_loc:
                    target_loc.latitude = lat
                    target_loc.longitude = lng
                    await db.commit()
                elif bp:
                    bp.latitude = lat
                    bp.longitude = lng
                    await db.commit()

                return GeoGridLocationResult(
                    latitude=lat,
                    longitude=lng,
                    location_precision="ADDRESS_RESOLVED",
                    center_source="GEOCODED_ADDRESS",
                    center_name=center_name,
                    center_address=full_address,
                    location_entity=target_loc,
                    target_place_id=target_place_id,
                    target_url=target_url,
                    business_name=resolved_business_name,
                    phone=resolved_phone
                )

        # ── Priority 5: Structured Suburb / Postal Code Geocoding ──
        if city or postal_code or state:
            geo_coords = await GeocodingService.geocode_address(
                city=city,
                state=state,
                postal_code=postal_code,
                country=country
            )
            if geo_coords:
                lat, lng = geo_coords
                prec = "ADDRESS_RESOLVED" if postal_code else "CITY_LEVEL"
                src = "GEOCODED_ADDRESS" if postal_code else "CITY_FALLBACK"

                warning = None
                if prec == "CITY_LEVEL":
                    warning = "Exact business coordinates were not available. This Geo-Grid is using city-level location and may be less precise."

                return GeoGridLocationResult(
                    latitude=lat,
                    longitude=lng,
                    location_precision=prec,
                    center_source=src,
                    center_name=center_name,
                    center_address=f"{city or ''}, {state or ''} {postal_code or ''}".strip(),
                    location_entity=target_loc,
                    target_place_id=target_place_id,
                    target_url=target_url,
                    business_name=resolved_business_name,
                    phone=resolved_phone,
                    warning_message=warning
                )

        # ── Priority 6: Explicit Center Name fallback ──
        if explicit_center_name:
            geo_coords = await GeocodingService.geocode_address(city=explicit_center_name, country=country)
            if geo_coords:
                lat, lng = geo_coords
                return GeoGridLocationResult(
                    latitude=lat,
                    longitude=lng,
                    location_precision="CITY_LEVEL",
                    center_source="CITY_FALLBACK",
                    center_name=explicit_center_name,
                    center_address=explicit_center_name,
                    location_entity=target_loc,
                    target_place_id=target_place_id,
                    target_url=target_url,
                    business_name=resolved_business_name,
                    phone=resolved_phone,
                    warning_message="Exact business coordinates were not available. This Geo-Grid is using city-level location and may be less precise."
                )

        return GeoGridLocationResult(
            latitude=0.0,
            longitude=0.0,
            location_precision="UNKNOWN",
            center_source="CITY_FALLBACK",
            center_name=center_name,
            center_address=None,
            location_entity=target_loc,
            target_place_id=target_place_id,
            target_url=target_url,
            business_name=resolved_business_name,
            phone=resolved_phone,
            warning_message="Exact business coordinates were not available. This Geo-Grid is using city-level location and may be less precise."
        )
