import asyncio
import math
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from app.services.serp.base import SERPProvider
from app.services.serp.matcher import DomainMatcher
from app.services.geocoding import GeocodingService

logger = logging.getLogger("locallift.serp.grid_scanner")

class GeoGridScanner:
    _CACHE: Dict[str, Any] = {}

    @classmethod
    def clear_cache(cls):
        cls._CACHE.clear()

    @staticmethod
    def calculate_distance_and_direction(
        center_lat: float,
        center_lng: float,
        target_lat: float,
        target_lng: float
    ) -> Tuple[float, str]:
        """
        Computes accurate Haversine distance in km and 8-cardinal compass direction from center to target.
        """
        dlat = math.radians(target_lat - center_lat)
        dlng = math.radians(target_lng - center_lng)
        lat1_rad = math.radians(center_lat)
        lat2_rad = math.radians(target_lat)

        a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        distance_km = round(6371.0 * c, 2)

        if distance_km < 0.05:
            return 0.0, "Center"

        y = math.sin(dlng) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlng)
        bearing = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0

        directions = ["North", "North-East", "East", "South-East", "South", "South-West", "West", "North-West"]
        idx = int((bearing + 22.5) / 45.0) % 8
        return distance_km, directions[idx]

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
        Calculates step distance such that every point (including corner nodes) satisfies distance <= radius_km.
        Uses spherical geodesy for accurate lat/lng displacement.
        """
        points = []
        if grid_size <= 1:
            return [{
                "point_number": 1,
                "row": 0,
                "col": 0,
                "lat": round(center_lat, 6),
                "lng": round(center_lng, 6),
                "distance_km": 0.0,
                "direction": "Center",
                "is_center": True
            }]

        step_km = (radius_km * math.sqrt(2)) / (grid_size - 1)
        half_grid = (grid_size - 1) / 2.0

        # Cosine factor for longitude displacement
        lat_rad = math.radians(center_lat)
        cos_lat = math.cos(lat_rad)
        if abs(cos_lat) < 0.001:
            cos_lat = 0.001

        pt_num = 1
        for r in range(grid_size):
            for c in range(grid_size):
                offset_y_km = (half_grid - r) * step_km  # North-South
                offset_x_km = (c - half_grid) * step_km  # East-West

                # Exact spherical earth radius (6371.0 km) matching calculate_distance_and_direction
                km_per_deg_lat = (math.pi * 6371.0) / 180.0
                km_per_deg_lng = km_per_deg_lat * cos_lat

                lat_offset = offset_y_km / km_per_deg_lat
                lng_offset = offset_x_km / km_per_deg_lng

                p_lat = round(center_lat + lat_offset, 6)
                p_lng = round(center_lng + lng_offset, 6)
                dist_km, direction = cls.calculate_distance_and_direction(center_lat, center_lng, p_lat, p_lng)

                points.append({
                    "point_number": pt_num,
                    "row": r,
                    "col": c,
                    "lat": p_lat,
                    "lng": p_lng,
                    "distance_km": dist_km,
                    "direction": direction,
                    "is_center": (dist_km == 0.0 or direction == "Center")
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
        target_url: Optional[str] = None,
        is_cancelled_fn: Optional[Any] = None,
        on_point_completed: Optional[Any] = None
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
                    "distance_km": pt.get("distance_km", 0.0),
                    "direction": pt.get("direction", "Center"),
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
                    "competitors": [],
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
                "completed_points": total_pts,
                "ranking_found_points": 0,
                "not_found_points": 0,
                "provider_error_points": total_pts,
                "timeout_points": 0,
                "successful_points": 0,
                "failed_points": total_pts,
                "scan_status": "failed",
                "status_message": "SERP provider not configured. Connect your SerpApi account in Settings to enable Geo-Grid.",
                "grid_points": unconfigured_points,
                "scanned_at": datetime.now(timezone.utc)
            }

        caps = getattr(provider, "capabilities", None)
        has_geo_grid = True
        if caps:
            if isinstance(caps, dict):
                has_geo_grid = caps.get("geo_grid", caps.get("local_grid", True))
            else:
                has_geo_grid = getattr(caps, "geo_grid", getattr(caps, "local_grid", True))

        if not has_geo_grid:
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
            p_dist = point.get("distance_km", 0.0)
            p_dir = point.get("direction", "Center")

            # Reverse geocode coordinate to human-readable area / locality
            try:
                area_name = await GeocodingService.reverse_geocode(p_lat, p_lng) or "Area name unavailable"
            except Exception:
                area_name = "Area name unavailable"

            async with semaphore:
                try:
                    # IMPORTANT: provider httpx timeout is 30s; outer wait_for must be > 30s
                    # so the provider's own timeout fires first and returns a structured error,
                    # rather than us getting a raw asyncio.TimeoutError mid-network.
                    serp_resp = await asyncio.wait_for(
                        provider.search_local_grid_point(
                            keyword=keyword,
                            lat=p_lat,
                            lng=p_lng
                        ),
                        timeout=35.0
                    )
                except (asyncio.TimeoutError, TimeoutError):
                    return {
                        "point_number": pt_num,
                        "row": point["row"],
                        "col": point["col"],
                        "lat": p_lat,
                        "lng": p_lng,
                        "area_name": area_name,
                        "distance_km": p_dist,
                        "direction": p_dir,
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
                        "competitor_ahead": None,
                        "competitors": []
                    }
                except Exception as e:
                    logger.error(f"Geo-Grid point scan failed at ({p_lat}, {p_lng}): {e}")
                    return {
                        "point_number": pt_num,
                        "row": point["row"],
                        "col": point["col"],
                        "lat": p_lat,
                        "lng": p_lng,
                        "area_name": area_name,
                        "distance_km": p_dist,
                        "direction": p_dir,
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
                        "competitor_ahead": None,
                        "competitors": []
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
                    "area_name": area_name,
                    "distance_km": p_dist,
                    "direction": p_dir,
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
                    "competitor_ahead": None,
                    "competitors": []
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

            # Discover all competitors and top competitor
            raw_items = serp_resp.local_pack_results or serp_resp.organic_results or []
            competitors_list: List[Dict[str, Any]] = []
            for item in raw_items:
                is_target = bool(
                    matched_item and (
                        (matched_item.place_id and item.place_id and item.place_id == matched_item.place_id) or
                        (matched_item.title and item.title and item.title.strip().lower() == matched_item.title.strip().lower()) or
                        (matched_item.domain and item.domain and item.domain.strip().lower() == matched_item.domain.strip().lower()) or
                        (item.position == rank)
                    )
                )
                competitors_list.append({
                    "position": item.position,
                    "title": item.title,
                    "link": item.link or "",
                    "domain": item.domain or "",
                    "rating": item.rating,
                    "reviews_count": item.reviews_count,
                    "category": getattr(item, "category", None) or getattr(item, "item_type", "Local Business"),
                    "address": item.address,
                    "phone": item.phone,
                    "place_id": item.place_id,
                    "snippet": item.snippet,
                    "is_target": is_target
                })

            top_competitor = None
            if competitors_list:
                for c_entry in competitors_list:
                    if not c_entry["is_target"]:
                        top_competitor = c_entry["title"]
                        break

            if rank is not None:
                point_status = "SUCCESS"
                pin_status = "found"
                if rank <= 3:
                    color = "green"
                elif rank <= 7:
                    color = "blue"
                elif rank <= 15:
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
                "area_name": area_name,
                "distance_km": p_dist,
                "direction": p_dir,
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
                "matched_by": getattr(matched_item, "matched_by", None) if matched_item else None,
                "competitor_ahead": top_competitor if (rank is None or rank > 3) else None,
                "competitors": competitors_list,
                "error": None
            }

        # Run points in controlled batches with active cooperative cancellation check
        results: List[Dict[str, Any]] = []
        is_cancelled = False

        batch_size = max(1, concurrency_limit)
        for i in range(0, len(coordinates), batch_size):
            if is_cancelled_fn:
                try:
                    c_res = is_cancelled_fn()
                    if asyncio.iscoroutine(c_res):
                        is_cancelled = await c_res
                    else:
                        is_cancelled = bool(c_res)
                except Exception as ce:
                    logger.warning(f"Error checking cancellation: {ce}")

            if is_cancelled:
                logger.info(f"Geo-Grid scan cancelled. Stopped before point batch starting at index {i}.")
                break

            batch = coordinates[i:i + batch_size]
            batch_results = await asyncio.gather(*(scan_point(pt) for pt in batch))

            for pt_res in batch_results:
                results.append(pt_res)
                if on_point_completed:
                    try:
                        cb_res = on_point_completed(pt_res)
                        if asyncio.iscoroutine(cb_res):
                            await cb_res
                    except Exception as cbe:
                        logger.warning(f"Error in on_point_completed callback: {cbe}")

        # Metrics calculation
        total_points = len(coordinates)
        completed_results_count = len(results)
        found_points = [p for p in results if p.get("rank") is not None]
        not_found_points = [p for p in results if p.get("status") == "NOT_FOUND"]
        timeout_points = [p for p in results if p.get("error_type") == "TIMEOUT" or p.get("status") == "TIMEOUT"]
        provider_error_points = [p for p in results if (
            p.get("error_type") == "PROVIDER_ERROR"
            or p.get("status") == "PROVIDER_ERROR"
            or (p.get("status") == "failed" and p.get("error_type") != "TIMEOUT")
        )]

        ranking_found_count = len(found_points)
        not_found_count = len(not_found_points)
        timeout_count = len(timeout_points)
        provider_error_count = len(provider_error_points)

        # Clear invariant: completed_points = successful_points + failed_points
        successful_points = ranking_found_count + not_found_count
        failed_points = provider_error_count + timeout_count
        completed_points = successful_points + failed_points

        # Average rank: Strictly on points where the business was found. Never treat missing as 0 or default!
        found_ranks = [p["rank"] for p in found_points]
        avg_rank = round(sum(found_ranks) / len(found_ranks), 2) if found_ranks else None

        # Visibility: Top 3 points divided by successful evaluated points
        top_3_count = len([r for r in found_ranks if r <= 3])
        vis_pct = round((top_3_count / successful_points) * 100, 1) if successful_points > 0 else 0.0

        if is_cancelled:
            scan_status = "cancelled"
            status_message = f"Geo-Grid scan cancelled by user. {completed_points} of {total_points} points evaluated."
        elif total_points == 0 or completed_points == 0:
            scan_status = "failed"
            status_message = "No grid points could be successfully evaluated."
        elif failed_points == 0 and successful_points == total_points:
            scan_status = "completed"
            status_message = f"Geo-Grid scan completed across all {total_points} points."
        elif successful_points == 0:
            scan_status = "failed"
            status_message = f"Geo-Grid scan failed across all {total_points} points."
        else:
            scan_status = "completed_with_errors"
            status_message = f"Geo-Grid scan completed with {failed_points} point errors."

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
            "status_message": status_message,
            "is_cancelled": is_cancelled,
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

            ref_pt = p_b or p_a
            pt_lat = getattr(ref_pt, "latitude", None) or getattr(ref_pt, "lat", 0.0)
            pt_lng = getattr(ref_pt, "longitude", None) or getattr(ref_pt, "lng", 0.0)

            point_comparisons.append({
                "point_number": pt_num,
                "lat": pt_lat,
                "lng": pt_lng,
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

