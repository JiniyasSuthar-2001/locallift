import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.models.local_seo import Competitor
from app.models.project import Project
from app.services.serp.matcher import DomainMatcher

logger = logging.getLogger("locallift.competitor_geogrid")

class CompetitorGeoGridService:
    """
    Authoritative service to extract, normalize, deduplicate, and persist competitors
    discovered during completed Geo-Grid scans.
    """

    @classmethod
    async def ingest_scan_competitors(
        cls,
        db: AsyncSession,
        project_id: int,
        scan_id: Optional[int],
        grid_points: List[Dict[str, Any]],
        keyword: Optional[str] = None,
        scan_time: Optional[datetime] = None
    ) -> List[Competitor]:
        """
        Processes grid_points from a completed Geo-Grid scan and reconciles them with
        the project's tracked competitors.
        """
        if not grid_points:
            return []

        # 1. Fetch project for target exclusion
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalars().first()
        target_domain = DomainMatcher.normalize_host(project.domain) if project and project.domain else ""
        target_name = project.name.strip().lower() if project and project.name else ""

        # 2. Aggregate competitor items across all points in this scan
        # Keyed by best identifier to prevent duplicate rows per scan
        scan_candidates: Dict[str, Dict[str, Any]] = {}

        for pt in grid_points:
            pt_competitors = pt.get("competitors") or []
            pt_num = pt.get("point_number")

            for comp in pt_competitors:
                # Exclude target business itself
                if comp.get("is_target"):
                    continue

                raw_title = (comp.get("title") or "").strip()
                if not raw_title:
                    continue

                raw_domain = DomainMatcher.normalize_host(comp.get("domain") or "")
                place_id = (comp.get("place_id") or "").strip()
                pos = comp.get("position")

                # Filter out target project by name or domain
                if target_domain and raw_domain == target_domain:
                    continue
                if target_name and raw_title.lower() == target_name:
                    continue

                # Ignore major non-business global directories / search engines if misclassified
                if raw_domain in ("google.com", "maps.google.com", "facebook.com", "instagram.com", "wikipedia.org"):
                    continue

                # Generate deduplication key for this candidate within the scan
                if place_id:
                    cand_key = f"place:{place_id}"
                elif raw_domain:
                    cand_key = f"domain:{raw_domain}"
                else:
                    cand_key = f"name:{raw_title.lower()}"

                if cand_key not in scan_candidates:
                    scan_candidates[cand_key] = {
                        "title": raw_title,
                        "domain": raw_domain or (f"{raw_title.lower().replace(' ', '')}.com" if not raw_domain else ""),
                        "place_id": place_id or None,
                        "rating": comp.get("rating"),
                        "reviews": comp.get("reviews"),
                        "address": comp.get("address"),
                        "phone": comp.get("phone"),
                        "ranks": [pos] if pos is not None else [],
                        "points_seen": {pt_num} if pt_num is not None else set()
                    }
                else:
                    entry = scan_candidates[cand_key]
                    if pos is not None:
                        entry["ranks"].append(pos)
                    if pt_num is not None:
                        entry["points_seen"].add(pt_num)
                    # Supplement missing metadata
                    if not entry["place_id"] and place_id:
                        entry["place_id"] = place_id
                    if not entry["domain"] and raw_domain:
                        entry["domain"] = raw_domain
                    if entry["rating"] is None and comp.get("rating") is not None:
                        entry["rating"] = comp.get("rating")
                    if (entry["reviews"] is None or entry["reviews"] == 0) and comp.get("reviews"):
                        entry["reviews"] = comp.get("reviews")
                    if not entry["address"] and comp.get("address"):
                        entry["address"] = comp.get("address")
                    if not entry["phone"] and comp.get("phone"):
                        entry["phone"] = comp.get("phone")

        if not scan_candidates:
            return []

        # 3. Fetch existing competitors for this project
        existing_res = await db.execute(select(Competitor).where(Competitor.project_id == project_id))
        existing_comps = existing_res.scalars().all()

        existing_by_place_id: Dict[str, Competitor] = {
            c.place_id.strip(): c for c in existing_comps if c.place_id and c.place_id.strip()
        }
        existing_by_domain: Dict[str, Competitor] = {
            DomainMatcher.normalize_host(c.domain): c for c in existing_comps if c.domain
        }
        existing_by_name: Dict[str, Competitor] = {
            c.name.strip().lower(): c for c in existing_comps if c.name
        }

        now_utc = datetime.now(timezone.utc)
        effective_time = scan_time or now_utc
        affected_competitors: List[Competitor] = []

        # 4. Reconcile candidates with database records
        for cand_key, cand in scan_candidates.items():
            cand_title = cand["title"]
            cand_domain = cand["domain"]
            cand_place_id = cand["place_id"]
            cand_ranks = cand["ranks"]
            cand_appearances = len(cand["points_seen"]) if cand["points_seen"] else len(cand_ranks)
            min_rank = min(cand_ranks) if cand_ranks else None
            max_rank = max(cand_ranks) if cand_ranks else None
            avg_rank = round(sum(cand_ranks) / len(cand_ranks), 1) if cand_ranks else None

            # Attempt matching in priority order: place_id -> domain -> business name
            matched_comp: Optional[Competitor] = None
            if cand_place_id and cand_place_id in existing_by_place_id:
                matched_comp = existing_by_place_id[cand_place_id]
            elif cand_domain and cand_domain in existing_by_domain:
                matched_comp = existing_by_domain[cand_domain]
            elif cand_title.lower() in existing_by_name:
                matched_comp = existing_by_name[cand_title.lower()]

            scan_entry = {
                "scan_id": scan_id,
                "keyword": keyword or "Local Search",
                "scanned_at": effective_time.isoformat(),
                "appearances": cand_appearances,
                "best_rank": min_rank,
                "worst_rank": max_rank,
                "avg_rank": avg_rank
            }

            if matched_comp:
                # Update existing competitor
                # Source management: manual + geogrid if added manually before
                current_src = matched_comp.source or "manual"
                if current_src == "manual":
                    matched_comp.source = "manual_and_geogrid"
                elif current_src not in ("geogrid", "manual_and_geogrid"):
                    matched_comp.source = "manual_and_geogrid"

                # Update place_id if discovered
                if cand_place_id and not matched_comp.place_id:
                    matched_comp.place_id = cand_place_id
                    existing_by_place_id[cand_place_id] = matched_comp

                # Update rating and review count
                if cand["rating"] is not None:
                    matched_comp.rating = cand["rating"]
                if cand["reviews"] is not None and cand["reviews"] > (matched_comp.reviews_count or 0):
                    matched_comp.reviews_count = cand["reviews"]

                if cand["address"] and not getattr(matched_comp, "address", None):
                    matched_comp.address = cand["address"]
                if cand["phone"] and not getattr(matched_comp, "phone", None):
                    matched_comp.phone = cand["phone"]

                # Rank statistics calculation
                if min_rank is not None:
                    curr_best = getattr(matched_comp, "best_rank", None)
                    matched_comp.best_rank = min(curr_best, min_rank) if curr_best is not None else min_rank

                if max_rank is not None:
                    curr_worst = getattr(matched_comp, "worst_rank", None)
                    matched_comp.worst_rank = max(curr_worst, max_rank) if curr_worst is not None else max_rank

                matched_comp.grid_appearances = (getattr(matched_comp, "grid_appearances", 0) or 0) + cand_appearances

                # Calculate combined average rank
                if avg_rank is not None:
                    if matched_comp.avg_maps_rank is not None:
                        matched_comp.avg_maps_rank = round((matched_comp.avg_maps_rank + avg_rank) / 2.0, 1)
                    else:
                        matched_comp.avg_maps_rank = avg_rank

                # Keywords found
                kws = list(getattr(matched_comp, "keywords_found", []) or [])
                if keyword and keyword not in kws:
                    kws.append(keyword)
                matched_comp.keywords_found = kws
                matched_comp.top_keywords_count = len(kws)
                flag_modified(matched_comp, "keywords_found")

                # Scan history
                s_data = list(getattr(matched_comp, "scans_data", []) or [])
                # Avoid duplicate scan_id entries if re-run
                s_data = [s for s in s_data if s.get("scan_id") != scan_id]
                s_data.append(scan_entry)
                matched_comp.scans_data = s_data
                flag_modified(matched_comp, "scans_data")

                matched_comp.last_seen_at = effective_time
                affected_competitors.append(matched_comp)

            else:
                # Create brand new competitor discovered via Geo-Grid
                new_comp = Competitor(
                    project_id=project_id,
                    name=cand_title,
                    domain=cand_domain,
                    website=cand_domain,
                    place_id=cand_place_id,
                    address=cand.get("address"),
                    phone=cand.get("phone"),
                    rating=cand.get("rating"),
                    reviews_count=cand.get("reviews") or 0,
                    source="geogrid",
                    best_rank=min_rank,
                    worst_rank=max_rank,
                    avg_maps_rank=avg_rank,
                    grid_appearances=cand_appearances,
                    top_keywords_count=1 if keyword else 0,
                    keywords_found=[keyword] if keyword else [],
                    scans_data=[scan_entry],
                    last_seen_at=effective_time,
                    created_at=effective_time
                )
                db.add(new_comp)
                affected_competitors.append(new_comp)

                # Update lookup indexes for remainder of batch
                if cand_place_id:
                    existing_by_place_id[cand_place_id] = new_comp
                if cand_domain:
                    existing_by_domain[cand_domain] = new_comp
                existing_by_name[cand_title.lower()] = new_comp

        await db.commit()
        logger.info(
            f"Geo-Grid scan #{scan_id} successfully ingested {len(affected_competitors)} competitors "
            f"for project #{project_id} (Keyword: '{keyword}')."
        )
        return affected_competitors
