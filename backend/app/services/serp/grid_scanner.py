import asyncio
import math
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from app.services.serp.base import SERPProvider
from app.services.serp.matcher import DomainMatcher

logger = logging.getLogger("locallift.serp.grid_scanner")

class GeoGridScanner:
    # In-memory short-term cache for grid queries (TTL: 1 hour)
    # Key: (keyword, round(lat, 4), round(lng, 4)) -> (timestamp, SERPResponse)
    _CACHE: Dict[Tuple[str, float, float], Tuple[float, Any]] = {}
    CACHE_TTL_SECONDS = 3600.0

    @classmethod
    def clear_cache(cls):
        cls._CACHE.clear()

    @classmethod
    def calculate_grid_coordinates(
        cls,
        center_lat: float,
        center_lng: float,
        radius_km: float,
        grid_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generates an N x N matrix of geographic coordinates centered around (center_lat, center_lng).
        Uses spherical geodesy for accurate lat/lng displacement.
        """
        points = []
        if grid_size <= 1:
            return [{
                "row": 0,
                "col": 0,
                "lat": round(center_lat, 6),
                "lng": round(center_lng, 6)
            }]

        step_km = (radius_km * 2) / (grid_size - 1)
        half_grid = (grid_size - 1) / 2.0

        # Cosine factor for longitude displacement
        lat_rad = math.radians(center_lat)
        cos_lat = math.cos(lat_rad)
        if abs(cos_lat) < 0.001:
            cos_lat = 0.001

        for r in range(grid_size):
            for c in range(grid_size):
                offset_y_km = (half_grid - r) * step_km  # North-South
                offset_x_km = (c - half_grid) * step_km  # East-West

                # 1 deg latitude ~ 110.574 km
                lat_offset = offset_y_km / 110.574
                # 1 deg longitude ~ 111.320 km * cos(latitude)
                lng_offset = offset_x_km / (111.320 * cos_lat)

                points.append({
                    "row": r,
                    "col": c,
                    "lat": round(center_lat + lat_offset, 6),
                    "lng": round(center_lng + lng_offset, 6)
                })

        return points

    @classmethod
    async def scan_grid(
        cls,
        provider: SERPProvider,
        keyword: str,
        target_domain: str,
        center_lat: float,
        center_lng: float,
        radius_km: float = 10.0,
        grid_size: int = 5,
        concurrency_limit: int = 3
    ) -> Dict[str, Any]:
        """
        Executes a controlled concurrent 5x5 Geo-Grid scan across discrete GPS coordinates.
        Resilient against partial failures, rate limits, and network timeouts.
        """
        coordinates = cls.calculate_grid_coordinates(center_lat, center_lng, radius_km, grid_size)
        semaphore = asyncio.Semaphore(concurrency_limit)
        now_ts = asyncio.get_event_loop().time()

        async def scan_point(point: Dict[str, Any]) -> Dict[str, Any]:
            p_lat = point["lat"]
            p_lng = point["lng"]
            cache_key = (keyword.strip().lower(), round(p_lat, 4), round(p_lng, 4))

            # 1. Check in-memory cache
            if cache_key in cls._CACHE:
                cached_time, cached_resp = cls._CACHE[cache_key]
                if now_ts - cached_time < cls.CACHE_TTL_SECONDS:
                    serp_resp = cached_resp
                else:
                    serp_resp = None
            else:
                serp_resp = None

            # 2. Fetch from provider with concurrency control if not cached
            if serp_resp is None:
                async with semaphore:
                    try:
                        serp_resp = await provider.search_local_grid_point(
                            keyword=keyword,
                            lat=p_lat,
                            lng=p_lng
                        )
                        if serp_resp.success:
                            cls._CACHE[cache_key] = (now_ts, serp_resp)
                    except Exception as e:
                        logger.error(f"Geo-Grid point scan failed at ({p_lat}, {p_lng}): {e}")
                        return {
                            "row": point["row"],
                            "col": point["col"],
                            "lat": p_lat,
                            "lng": p_lng,
                            "rank": None,
                            "status": "failed",
                            "pin_status": "failed",
                            "color": "red",
                            "error": str(e)[:100],
                            "competitor_ahead": None
                        }

            # 3. Handle provider-level failure
            if not serp_resp.success:
                return {
                    "row": point["row"],
                    "col": point["col"],
                    "lat": p_lat,
                    "lng": p_lng,
                    "rank": None,
                    "status": "failed",
                    "pin_status": "failed",
                    "color": "red",
                    "error": serp_resp.error_code or serp_resp.error_message or "Query failed",
                    "competitor_ahead": None
                }

            # 4. Search for target business domain in local results
            rank, ranking_url, _ = DomainMatcher.find_rank_in_serp(
                serp_resp,
                target_domain=target_domain
            )

            # Discover top competitor if our business is not #1
            top_competitor = None
            if serp_resp.local_pack_results:
                first_item = serp_resp.local_pack_results[0]
                if not DomainMatcher.matches_target(first_item.link, target_domain):
                    top_competitor = first_item.title
            elif serp_resp.organic_results:
                first_item = serp_resp.organic_results[0]
                if not DomainMatcher.matches_target(first_item.link, target_domain):
                    top_competitor = first_item.title

            # Status and Color
            if rank is not None:
                if rank <= 3:
                    p_status = "green"
                elif rank <= 6:
                    p_status = "yellow"
                else:
                    p_status = "red"
                pin_status = "found"
            else:
                p_status = "red"
                pin_status = "not_found"

            return {
                "row": point["row"],
                "col": point["col"],
                "lat": p_lat,
                "lng": p_lng,
                "rank": rank,
                "status": p_status,  # Matches frontend pin style expectations ('green'/'yellow'/'red')
                "pin_status": pin_status,
                "ranking_url": ranking_url,
                "competitor_ahead": top_competitor if (rank is None or rank > 3) else None
            }

        # Run all points concurrently within Semaphore limits
        results = await asyncio.gather(*(scan_point(pt) for pt in coordinates))

        # Calculate summary statistics
        found_ranks = [p["rank"] for p in results if p.get("rank") is not None]
        total_points = len(results)
        successful_points = len([p for p in results if p.get("pin_status") != "failed"])
        failed_points = total_points - successful_points
        top_3_count = len([r for r in found_ranks if r <= 3])

        avg_rank = round(sum(found_ranks) / len(found_ranks), 2) if found_ranks else None
        vis_pct = round((top_3_count / total_points) * 100, 1) if total_points > 0 else 0.0

        if total_points == 0 or successful_points == 0:
            scan_status = "failed"
        elif failed_points == 0:
            scan_status = "completed"
        else:
            scan_status = "completed_with_errors"

        return {
            "center_lat": center_lat,
            "center_lng": center_lng,
            "radius_km": radius_km,
            "grid_size": grid_size,
            "average_rank": avg_rank,
            "local_visibility_pct": vis_pct,
            "total_points": total_points,
            "successful_points": successful_points,
            "failed_points": failed_points,
            "scan_status": scan_status,
            "grid_points": results,
            "scanned_at": datetime.now(timezone.utc)
        }
