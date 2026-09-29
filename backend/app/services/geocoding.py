import asyncio
import httpx
import logging
from typing import Optional, Tuple, Dict, List, Any
from app.config import settings

logger = logging.getLogger("locallift.geocoding")

class GeocodingService:
    """
    Geocoding & Reverse-Geocoding Service for resolving real geographic coordinates (latitude, longitude)
    and human-readable area / locality / suburb names.
    Never returns hardcoded or arbitrary area names upon failure.
    """

    # In-memory cache keyed by rounded (lat, lon) coordinates (~100m radius precision)
    _REVERSE_CACHE: Dict[Tuple[float, float], str] = {}

    @classmethod
    def clear_cache(cls):
        cls._REVERSE_CACHE.clear()

    @classmethod
    async def geocode_address(
        cls,
        address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        postal_code: Optional[str] = None,
        country: Optional[str] = None
    ) -> Optional[Tuple[float, float]]:
        """
        Attempts to resolve physical address components to (latitude, longitude).
        Returns None if resolution fails, times out, or parameters are insufficient.
        """
        parts = [p.strip() for p in [address, city, state, postal_code, country] if p and p.strip()]
        if not parts:
            return None

        query_str = ", ".join(parts)

        headers = {
            "User-Agent": "LocalLift-SEO-Engine/1.0 (https://locallift.io; geocoding@locallift.io)"
        }
        params = {
            "q": query_str,
            "format": "jsonv2",
            "limit": 1
        }

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                    resp = await client.get("https://nominatim.openstreetmap.org/search", params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            first_match = data[0]
                            lat = float(first_match.get("lat"))
                            lon = float(first_match.get("lon"))
                            logger.info(f"Geocoded '{query_str}' -> ({lat}, {lon})")
                            return (lat, lon)
                    elif resp.status_code == 429:
                        logger.warning(f"Geocoding rate limited (429) for '{query_str}', attempt {attempt}/{max_attempts}")
                        if attempt < max_attempts:
                            await asyncio.sleep(1.5)
                            continue
                    else:
                        logger.warning(f"Geocoding returned status {resp.status_code} for '{query_str}'")
            except (httpx.TimeoutException, httpx.RequestError) as e:
                logger.warning(f"Geocoding network error for '{query_str}' attempt {attempt}/{max_attempts}: {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(1.0)
                    continue
            except Exception as e:
                logger.warning(f"Geocoding lookup failed for '{query_str}': {e}")
                break

        return None

    @classmethod
    async def geocode_full_address(
        cls,
        full_address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        postal_code: Optional[str] = None,
        country: Optional[str] = None
    ) -> Optional[Tuple[float, float]]:
        """
        Robust multi-step address geocoding with landmark stripping fallback.
        Preserves full original address details while cleanly resolving complex real-world addresses.
        """
        if not full_address:
            return await cls.geocode_address(city=city, state=state, postal_code=postal_code, country=country)

        # 1. Attempt exact complete address string
        coords = await cls.geocode_address(address=full_address, city=city, state=state, postal_code=postal_code, country=country)
        if coords:
            return coords

        # 2. If address contains multiple comma-separated tokens, try cleaning relative landmark phrases
        # e.g. "Plot 5, Vasna Rd, behind Yogeshwar Apartment, opposite Raneshwar Hospital, Ashwamegh Nagar, Vasna, Vadodara, Gujarat 390015"
        raw_tokens = [t.strip() for t in full_address.split(",") if t.strip()]
        if len(raw_tokens) > 2:
            landmark_triggers = ("behind", "opp", "opposite", "near", "beside", "above", "below", "next to", "in front of", "plot", "shop no", "flat no")
            clean_tokens = [
                t for t in raw_tokens
                if not any(t.lower().startswith(trig) or f" {trig} " in t.lower() for trig in landmark_triggers)
            ]
            if clean_tokens and len(clean_tokens) != len(raw_tokens):
                cleaned_addr = ", ".join(clean_tokens)
                coords = await cls.geocode_address(address=cleaned_addr, city=city, state=state, postal_code=postal_code, country=country)
                if coords:
                    return coords

            # 3. Try street/road + suburb + postal code + city
            road_or_area_tokens = [t for t in raw_tokens if any(kw in t.lower() for kw in ("road", "rd", "street", "st", "nagar", "vasna", "avenue", "ave", "lane", "suburb"))]
            if road_or_area_tokens:
                sub_addr = ", ".join(road_or_area_tokens)
                coords = await cls.geocode_address(address=sub_addr, city=city, state=state, postal_code=postal_code, country=country)
                if coords:
                    return coords

        # 4. Fallback to structured suburb / city / state / postal code
        return await cls.geocode_address(city=city, state=state, postal_code=postal_code, country=country)

    @classmethod
    async def reverse_geocode(
        cls,
        latitude: Optional[float],
        longitude: Optional[float]
    ) -> Optional[str]:
        """
        Resolves a human-readable area, suburb, neighborhood, or locality name for a GPS point.
        Uses in-memory caching to prevent duplicate API requests for identical or nearby coordinates.
        Never fabricates an area name upon failure.
        """
        if latitude is None or longitude is None:
            return None

        # Round to 3 decimal places (~110m grid cell) for fast caching
        cache_key = (round(float(latitude), 3), round(float(longitude), 3))
        if cache_key in cls._REVERSE_CACHE:
            return cls._REVERSE_CACHE[cache_key]

        # 1. Attempt Google Geocoding API if key configured
        google_name = await cls._google_reverse(latitude, longitude)
        if google_name:
            cls._REVERSE_CACHE[cache_key] = google_name
            return google_name

        # 2. Fallback to OpenStreetMap Nominatim reverse geocoding
        nom_name = await cls._nominatim_reverse(latitude, longitude)
        if nom_name:
            cls._REVERSE_CACHE[cache_key] = nom_name
            return nom_name

        return None

    @classmethod
    async def _google_reverse(cls, latitude: float, longitude: float) -> Optional[str]:
        google_api_key = (getattr(settings, "GOOGLE_MAPS_API_KEY", None) or getattr(settings, "GOOGLE_PLACES_API_KEY", None) or "").strip()
        if not google_api_key:
            return None

        try:
            g_params = {
                "latlng": f"{latitude},{longitude}",
                "key": google_api_key,
                "result_type": "sublocality|locality|neighborhood|administrative_area_level_2"
            }
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get("https://maps.googleapis.com/maps/api/geocode/json", params=g_params)
                if resp.status_code == 200:
                    g_data = resp.json()
                    results = g_data.get("results", [])
                    if results:
                        for comp in results[0].get("address_components", []):
                            types = comp.get("types", [])
                            if any(t in types for t in ["sublocality", "sublocality_level_1", "neighborhood", "locality", "administrative_area_level_2"]):
                                name = comp.get("long_name")
                                if name:
                                    return name.strip()
        except Exception as ge:
            logger.debug(f"Google Maps reverse geocoding notice: {ge}")
        return None

    @classmethod
    async def _nominatim_reverse(cls, latitude: float, longitude: float) -> Optional[str]:
        headers = {
            "User-Agent": "LocalLift-SEO-Engine/1.0 (https://locallift.io; geocoding@locallift.io)"
        }
        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "jsonv2",
            "zoom": 14
        }
        try:
            async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
                resp = await client.get("https://nominatim.openstreetmap.org/reverse", params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    addr = data.get("address", {}) if isinstance(data, dict) else {}

                    # Hierarchy of most specific and useful area designations
                    area_name = (
                        addr.get("suburb")
                        or addr.get("neighbourhood")
                        or addr.get("quarter")
                        or addr.get("residential")
                        or addr.get("city_district")
                        or addr.get("locality")
                        or addr.get("town")
                        or addr.get("village")
                        or addr.get("municipality")
                        or addr.get("city")
                        or addr.get("county")
                    )
                    if area_name:
                        return area_name.strip()
        except Exception as e:
            logger.debug(f"Nominatim reverse geocoding notice: {e}")
        return None

    @classmethod
    async def reverse_geocode_points_batch(
        cls,
        points: Any
    ) -> Any:
        """
        Enriches a list of grid points or coordinate tuples with resolved area names concurrently.
        Supports:
        - List of (lat, lng) tuples -> returns Dict[Tuple[float, float], str]
        - List of dicts/objects -> enriches with area_name and returns updated list
        """
        if not points:
            return {} if isinstance(points, list) and len(points) == 0 else points

        # If points is a list of tuples (lat, lng)
        if isinstance(points[0], (tuple, list)):
            async def _resolve_coord(coord: Tuple[float, float]) -> Tuple[Tuple[float, float], Optional[str]]:
                lat, lng = coord[0], coord[1]
                name = await cls.reverse_geocode(lat, lng)
                return ((round(lat, 3), round(lng, 3)), name)

            tasks = [_resolve_coord(c) for c in points]
            results = await asyncio.gather(*tasks)
            return {k: v for k, v in results if v is not None}

        # If points is a list of dicts
        async def _enrich_point(pt: Any) -> Any:
            if isinstance(pt, dict):
                lat = pt.get("lat") or pt.get("latitude")
                lng = pt.get("lng") or pt.get("longitude")
                if not pt.get("area_name") and lat is not None and lng is not None:
                    pt["area_name"] = await cls.reverse_geocode(lat, lng) or "Area name unavailable"
            elif hasattr(pt, "latitude") and hasattr(pt, "longitude"):
                lat = getattr(pt, "latitude", None) or getattr(pt, "lat", None)
                lng = getattr(pt, "longitude", None) or getattr(pt, "lng", None)
                if not getattr(pt, "area_name", None) and lat is not None and lng is not None:
                    pt.area_name = await cls.reverse_geocode(lat, lng) or "Area name unavailable"
            return pt

        tasks = [_enrich_point(pt) for pt in points]
        return await asyncio.gather(*tasks)

