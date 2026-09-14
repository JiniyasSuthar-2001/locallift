import httpx
import logging
from typing import Optional, Tuple

logger = logging.getLogger("locallift.geocoding")

class GeocodingService:
    """
    Geocoding Service for resolving real geographic coordinates (latitude, longitude)
    from business address components.
    Never returns hardcoded or arbitrary coordinates upon failure.
    """

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

        # 1. Attempt geocoding via OpenStreetMap Nominatim with retry backoff & proper User-Agent
        headers = {
            "User-Agent": "LocalLift-SEO-Engine/1.0 (https://locallift.io; geocoding@locallift.io)"
        }
        params = {
            "q": query_str,
            "format": "jsonv2",
            "limit": 1
        }

        import asyncio
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
