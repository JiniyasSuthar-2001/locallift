import asyncio
import math
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from app.services.serp.base import SERPProvider
from app.services.serp.matcher import DomainMatcher

logger = logging.getLogger("locallift.serp.grid_scanner")

class GeoGridScanner:
    _CACHE: Dict[str, Any] = {}

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
                "point_number": 0,
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

        pt_num = 0
        for r in range(grid_size):
            for c in range(grid_size):
                offset_y_km = (half_grid - r) * step_km  # North-South
                offset_x_km = (c - half_grid) * step_km  # East-West

                # 1 deg latitude ~ 110.574 km
                lat_offset = offset_y_km / 110.574
                # 1 deg longitude ~ 111.320 km * cos(latitude)
                lng_offset = offset_x_km / (111.320 * cos_lat)

                points.append({
                    "point_number": pt_num,
                    "row": r,
                    "col": c,
                    "lat": round(center_lat + lat_offset, 6),
                    "lng": round(center_lng + lng_offset, 6)
                })
                pt_num += 1

        return points

    @classmethod
    async def scan_grid(
        cls,
        provider: SERPProvider,
        keyword: str,
        target_domain: Optional[str] = None,
        center_lat: float = 0.0,
        center_lng: float = 0.0,
        radius_km: float = 10.0,
        grid_size: int = 5,
        concurrency_limit: int = 3,
        target_place_id: Optional[str] = None,
        business_name: Optional[str] = None,
        phone: Optional[str] = None,
        target_url: Optional[str] = None
    ) -> Dict[str, Any]:
        # 0. Check provider configuration and capabilities first
        if not getattr(provider, "is_configured", True):
            logger.warning(f"Geo-Grid scan requested for unconfigured provider '{provider.__class__.__name__}'.")
            coordinates = cls.calculate_grid_coordinates(center_lat, center_lng, radius_km, grid_size)
            total_pts = len(coordinates)
            unconfigured_points = [
                {
                    "point_number": pt["point_number"],
                    "row": pt["row"],
                    "col": pt["col"],
                    "lat": pt["lat"],
                    "lng": pt["lng"],
                    "keyword": keyword,
                    "provider": getattr(provider, "provider_name", type(provider).__name__),
                    "rank": None,
                    "status": "failed",
                    "pin_status": "failed",
                    "color": "red",
                    "ranking_url": None,
                    "matched_business": None,
                    "matched_place_id": None,
                    "matched_domain": None,
                    "competitor_ahead": None,
                    "error": "SERP provider not configured."
                }
                for pt in coordinates
            ]
            return {
                "center_lat": center_lat,
                "center_lng": center_lng,
                "radius_km": radius_km,
                "grid_size": grid_size,
                "average_rank": None,
                "local_visibility_pct": 0.0,
                "total_points": total_pts,
                "completed_points": 0,
                "ranking_found_points": 0,
                "not_found_points": 0,
                "provider_error_points": total_pts,
                "timeout_points": 0,
                "successful_points": 0,
                "failed_points": total_pts,
                "scan_status": "failed",
                "status_message": "SERP provider not configured. Add your SerpApi key in Settings to enable 5x5 Geo-Grid searches.",
                "grid_points": unconfigured_points,
                "scanned_at": datetime.now(timezone.utc)
            }

        caps = getattr(provider, "capabilities", None)
        if caps and not caps.geo_grid:
            logger.warning(f"Geo-Grid scan requested for provider '{provider.__class__.__name__}' which does not support coordinate search.")
            return {
                "center_lat": center_lat,
                "center_lng": center_lng,
                "radius_km": radius_km,
                "grid_size": grid_size,
                "average_rank": None,
                "local_visibility_pct": 0.0,
                "total_points": 0,
                "completed_points": 0,
                "ranking_found_points": 0,
                "not_found_points": 0,
                "provider_error_points": 0,
                "timeout_points": 0,
                "successful_points": 0,
                "failed_points": 0,
                "scan_status": "unsupported",
                "status_message": f"Geo-Grid coordinate scanning is unsupported by {provider.__class__.__name__}. Configure SerpApi to enable 5x5 Geo-Grid searches.",
                "grid_points": [],
                "scanned_at": datetime.now(timezone.utc)
            }

        coordinates = cls.calculate_grid_coordinates(center_lat, center_lng, radius_km, grid_size)
        semaphore = asyncio.Semaphore(concurrency_limit)
        provider_name = getattr(provider, "provider_name", type(provider).__name__)

        async def scan_point(point: Dict[str, Any]) -> Dict[str, Any]:
            p_lat = point["lat"]
            p_lng = point["lng"]
            pt_num = point.get("point_number", 0)

            async with semaphore:
                try:
                    serp_resp = await asyncio.wait_for(
                        provider.search_local_grid_point(
                            keyword=keyword,
                            lat=p_lat,
                            lng=p_lng
                        ),
                        timeout=15.0
                    )
                except (asyncio.TimeoutError, TimeoutError):
                    return {
                        "point_number": pt_num,
                        "row": point["row"],
                        "col": point["col"],
                        "lat": p_lat,
                        "lng": p_lng,
                        "keyword": keyword,
                        "provider": provider_name,
                        "rank": None,
                        "status": "failed",
                        "error_type": "TIMEOUT",
                        "pin_status": "failed",
                        "color": "red",
                        "error": "Provider request timed out at grid point",
                        "matched_business": None,
                        "matched_place_id": None,
                        "matched_domain": None,
                        "ranking_url": None,
                        "competitor_ahead": None
                    }
                except Exception as e:
                    logger.error(f"Geo-Grid point scan failed at ({p_lat}, {p_lng}): {e}")
                    return {
                        "point_number": pt_num,
                        "row": point["row"],
                        "col": point["col"],
                        "lat": p_lat,
                        "lng": p_lng,
                        "keyword": keyword,
                        "provider": provider_name,
                        "rank": None,
                        "status": "failed",
                        "error_type": "PROVIDER_ERROR",
                        "pin_status": "failed",
                        "color": "red",
                        "error": str(e)[:100],
                        "matched_business": None,
                        "matched_place_id": None,
                        "matched_domain": None,
                        "ranking_url": None,
                        "competitor_ahead": None
                    }

            # Handle provider-level error
            if not serp_resp.success:
                err_code = serp_resp.error_code or "PROVIDER_ERROR"
                is_timeout = "timeout" in err_code.lower() or "timeout" in str(serp_resp.error_message).lower()
                status_val = "TIMEOUT" if is_timeout else "PROVIDER_ERROR"
                return {
                    "point_number": pt_num,
                    "row": point["row"],
                    "col": point["col"],
                    "lat": p_lat,
                    "lng": p_lng,
                    "keyword": keyword,
                    "provider": serp_resp.provider or provider_name,
                    "rank": None,
                    "status": "failed",
                    "error_type": status_val,
                    "pin_status": "failed",
                    "color": "red",
                    "error": serp_resp.error_message or err_code,
                    "matched_business": None,
                    "matched_place_id": None,
                    "matched_domain": None,
                    "ranking_url": None,
                    "competitor_ahead": None
                }

            # Match target business in provider results
            rank, ranking_url, serp_type, matched_item = DomainMatcher.find_rank_in_serp_detailed(
                serp_response=serp_resp,
                target_domain=target_domain,
                target_url=target_url,
                target_place_id=target_place_id,
                business_name=business_name,
                phone=phone
            )

            # Discover top competitor if our business is not #1
            top_competitor = None
            if serp_resp.local_pack_results:
                first_item = serp_resp.local_pack_results[0]
                if matched_item is None or first_item.position != 1:
                    top_competitor = first_item.title
            elif serp_resp.organic_results:
                first_item = serp_resp.organic_results[0]
                if matched_item is None or first_item.position != 1:
                    top_competitor = first_item.title

            if rank is not None:
                point_status = "SUCCESS"
                pin_status = "found"
                if rank <= 3:
                    color = "green"
                elif rank <= 6:
                    color = "yellow"
                else:
                    color = "red"
            else:
                point_status = "NOT_FOUND"
                pin_status = "not_found"
                color = "red"

            return {
                "point_number": pt_num,
                "row": point["row"],
                "col": point["col"],
                "lat": p_lat,
                "lng": p_lng,
                "keyword": keyword,
                "provider": serp_resp.provider or provider_name,
                "rank": rank,
                "status": point_status,
                "pin_status": pin_status,
                "color": color,
                "ranking_url": ranking_url,
                "matched_business": matched_item.title if matched_item else None,
                "matched_place_id": matched_item.place_id if matched_item else None,
                "matched_domain": matched_item.domain if matched_item else None,
                "competitor_ahead": top_competitor if (rank is None or rank > 3) else None,
                "error": None
            }

        # Run all points concurrently within Semaphore limits
        results = await asyncio.gather(*(scan_point(pt) for pt in coordinates))

        # Metrics calculation
        total_points = len(results)
        found_points = [p for p in results if p.get("rank") is not None]
        not_found_points = [p for p in results if p.get("status") == "NOT_FOUND"]
        timeout_points = [p for p in results if p.get("error_type") == "TIMEOUT" or p.get("status") == "TIMEOUT"]
        provider_error_points = [p for p in results if p.get("error_type") == "PROVIDER_ERROR" or p.get("status") == "PROVIDER_ERROR"]

        ranking_found_count = len(found_points)
        not_found_count = len(not_found_points)
        timeout_count = len(timeout_points)
        provider_error_count = len(provider_error_points)

        # Completed points: requests where provider successfully returned a result set (found + not_found)
        completed_points = ranking_found_count + not_found_count
        failed_points = len([p for p in results if p.get("status") == "failed"]) or (timeout_count + provider_error_count)
        successful_points = completed_points  # Backwards compatibility

        # Average rank: Strictly on points where the business was found. Never treat missing as 0 or default!
        found_ranks = [p["rank"] for p in found_points]
        avg_rank = round(sum(found_ranks) / len(found_ranks), 2) if found_ranks else None

        # Visibility: Top 3 points divided by completed points (excluding failed provider queries from denominator)
        top_3_count = len([r for r in found_ranks if r <= 3])
        vis_pct = round((top_3_count / completed_points) * 100, 1) if completed_points > 0 else 0.0

        if total_points == 0 or completed_points == 0:
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
            "completed_points": completed_points,
            "ranking_found_points": ranking_found_count,
            "not_found_points": not_found_count,
            "provider_error_points": provider_error_count,
            "timeout_points": timeout_count,
            "successful_points": successful_points,
            "failed_points": failed_points,
            "scan_status": scan_status,
            "grid_points": results,
            "scanned_at": datetime.now(timezone.utc)
        }

    @staticmethod
    def calculate_local_visibility(points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Centralized local visibility computation across ranking observations.
        Excludes provider errors and timeouts from ranking averages.
        """
        valid_points = [p for p in points if p.get("rank") is not None]
        completed = [p for p in points if p.get("status") in ["SUCCESS", "NOT_FOUND"] or p.get("rank") is not None]
        completed_count = len(completed)

        ranks = [p["rank"] for p in valid_points]
        avg_rank = round(sum(ranks) / len(ranks), 2) if ranks else None
        top_3_count = len([r for r in ranks if r <= 3])
        top_10_count = len([r for r in ranks if r <= 10])

        top_3_pct = round((top_3_count / completed_count) * 100, 1) if completed_count > 0 else 0.0
        top_10_pct = round((top_10_count / completed_count) * 100, 1) if completed_count > 0 else 0.0

        return {
            "average_rank": avg_rank,
            "top_3_visibility_pct": top_3_pct,
            "top_10_visibility_pct": top_10_pct,
            "ranking_found_points": len(valid_points),
            "completed_points": completed_count,
            "total_points": len(points)
        }

    @staticmethod
    def compare_scans(scan_a: Any, scan_b: Any) -> Dict[str, Any]:
        """
        Compares two historical scans (Scan A earlier vs Scan B later).
        Calculates metric deltas and point-by-point rank movements.
        """
        avg_a = getattr(scan_a, "average_rank", None)
        avg_b = getattr(scan_b, "average_rank", None)
        vis_a = getattr(scan_a, "local_visibility_pct", 0.0) or 0.0
        vis_b = getattr(scan_b, "local_visibility_pct", 0.0) or 0.0

        delta_avg_rank = round(avg_b - avg_a, 2) if (avg_a is not None and avg_b is not None) else None
        delta_vis_pct = round(vis_b - vis_a, 1)

        # Build point lookup
        pts_a = {p.point_number: p for p in getattr(scan_a, "point_results", [])}
        pts_b = {p.point_number: p for p in getattr(scan_b, "point_results", [])}

        point_comparisons = []
        improved_count = 0
        dropped_count = 0
        unchanged_count = 0

        for pt_num in sorted(set(list(pts_a.keys()) + list(pts_b.keys()))):
            p_a = pts_a.get(pt_num)
            p_b = pts_b.get(pt_num)

            rank_a = p_a.rank if p_a else None
            rank_b = p_b.rank if p_b else None

            delta = None
            movement = "unchanged"
            if rank_a is not None and rank_b is not None:
                delta = rank_a - rank_b  # Positive means rank improved (e.g. 5 to 2 = +3)
                if delta > 0:
                    movement = "improved"
                    improved_count += 1
                elif delta < 0:
                    movement = "dropped"
                    dropped_count += 1
                else:
                    unchanged_count += 1
            elif rank_a is None and rank_b is not None:
                movement = "newly_ranked"
                improved_count += 1
            elif rank_a is not None and rank_b is None:
                movement = "lost_rank"
                dropped_count += 1

            point_comparisons.append({
                "point_number": pt_num,
                "lat": (p_b or p_a).latitude,
                "lng": (p_b or p_a).longitude,
                "rank_a": rank_a,
                "rank_b": rank_b,
                "rank_delta": delta,
                "delta": delta,
                "movement": movement,
                "improved": movement in ["improved", "newly_ranked"],
                "declined": movement in ["dropped", "lost_rank"],
                "unchanged": movement == "unchanged"
            })

        return {
            "scan_a_id": getattr(scan_a, "id", None),
            "scan_b_id": getattr(scan_b, "id", None),
            "scan_a_date": getattr(scan_a, "scanned_at", None),
            "scan_b_date": getattr(scan_b, "scanned_at", None),
            "average_rank_a": avg_a,
            "average_rank_b": avg_b,
            "visibility_pct_a": vis_a,
            "visibility_pct_b": vis_b,
            "delta_average_rank": delta_avg_rank,
            "delta_visibility_pct": delta_vis_pct,
            "visibility_delta": delta_vis_pct,
            "rank_delta": delta_avg_rank,
            "improved_points_count": improved_count,
            "dropped_points_count": dropped_count,
            "unchanged_points_count": unchanged_count,
            "point_comparisons": point_comparisons
        }

