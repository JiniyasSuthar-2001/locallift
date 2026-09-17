import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.project import Project, Location
from app.models.ranking import Keyword
from app.models.local_seo import Competitor
from app.services.serp.factory import get_organization_serp_provider
from app.services.serp.matcher import DomainMatcher
from app.services.serp.normalizer import SERPNormalizer

logger = logging.getLogger("locallift.competitor_engine")

class CompetitorDiscoveryEngine:
    @classmethod
    async def discover_competitors_for_project(
        cls,
        project_id: int,
        db: AsyncSession,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        progress_callback = None
    ) -> Dict[str, Any]:
        """
        Executes multi-source competitor discovery using the authoritative SERP provider.
        Sources:
        1. Project business context & primary category
        2. Tracked project keywords
        3. Local SERP & Maps organic pack results
        """
        # 1. Fetch Project & Location Context
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        proj = proj_res.scalars().first()
        if not proj:
            raise ValueError(f"Project #{project_id} not found")

        loc_res = await db.execute(select(Location).where(Location.project_id == project_id))
        loc = loc_res.scalars().first()

        # Context location
        req_city = city or (loc.city if loc else None)
        req_state = state or (loc.state if loc else None)
        req_country = country or (loc.country if loc else None)
        loc_str = SERPNormalizer.build_location_string(req_city, req_state, req_country)

        iso_country = SERPNormalizer.normalize_country(req_country)

        # 2. Retrieve Provider for Project's Organization
        provider = await get_organization_serp_provider(db, proj.organization_id)
        caps = provider.capabilities

        # 3. Gather Discovery Keywords
        kws_res = await db.execute(select(Keyword).where(Keyword.project_id == project_id))
        tracked_kws = [k.keyword for k in kws_res.scalars().all()]

        search_terms = []
        if proj.primary_category:
            cat_query = f"{proj.primary_category}"
            if req_city:
                cat_query += f" in {req_city}"
            search_terms.append(cat_query)

        search_terms.extend(tracked_kws[:5])
        if not search_terms:
            search_terms = [f"local services near {req_city or 'me'}"]

        # 4. Existing tracked competitor domains to prevent self-matching or duplicates
        existing_comps_res = await db.execute(select(Competitor).where(Competitor.project_id == project_id))
        existing_domains = {c.domain.lower() for c in existing_comps_res.scalars().all() if c.domain}
        target_domain = DomainMatcher.normalize_host(proj.domain)

        candidate_map: Dict[str, Dict[str, Any]] = {}
        total_scanned = 0

        # Notify initial stage
        if progress_callback:
            await progress_callback({
                "status": "running",
                "stage": "Gathering business signals",
                "progress": 10.0,
                "sources_active": {
                    "serp": provider.is_configured,
                    "capabilities": caps.model_dump()
                }
            })

        query_errors: List[Dict[str, Any]] = []

        for idx, term in enumerate(search_terms, 1):
            total_scanned += 1
            if progress_callback:
                pct = 10.0 + (idx / len(search_terms)) * 70.0
                await progress_callback({
                    "status": "running",
                    "stage": f"Scanning SERP for '{term}'",
                    "progress": round(pct, 1),
                    "keywords_scanned": idx,
                    "candidates_found": len(candidate_map)
                })

            serp_resp = await provider.search_organic(
                keyword=term,
                location=loc_str,
                country=iso_country,
                num_results=20
            )

            if not serp_resp.success:
                logger.warning(f"SERP lookup for term '{term}' failed: {serp_resp.error_message}")
                query_errors.append({
                    "keyword": term,
                    "provider": serp_resp.provider,
                    "error_code": serp_resp.error_code or "SERP_LOOKUP_FAILED",
                    "error_message": serp_resp.error_message or "SERP query failed"
                })
                continue

            # Process Local Pack
            for pos, item in enumerate(serp_resp.local_pack_results, 1):
                item_domain = DomainMatcher.normalize_host(item.link) if item.link else ""
                if item_domain and (item_domain == target_domain or item_domain in existing_domains):
                    continue
                if not item.title:
                    continue

                comp_key = item_domain or item.title.strip().lower()
                if comp_key not in candidate_map:
                    candidate_map[comp_key] = {
                        "business_name": item.title,
                        "domain": item.domain or item_domain,
                        "rating": item.rating,
                        "reviews_count": item.reviews_count,
                        "phone": item.phone,
                        "address": item.address,
                        "source": "local_pack",
                        "discovered_at": datetime.now(timezone.utc).isoformat(),
                        "evidence": []
                    }

                candidate_map[comp_key]["evidence"].append({
                    "source": "google_local_pack",
                    "keyword": term,
                    "position": item.position or pos,
                    "location": loc_str,
                    "url": item.link
                })

            # Process Organic
            for pos, item in enumerate(serp_resp.organic_results, 1):
                item_domain = DomainMatcher.normalize_host(item.link)
                if not item_domain or item_domain == target_domain or item_domain in existing_domains:
                    continue

                # Filter out major search/social aggregators
                if item_domain in ("facebook.com", "yelp.com", "yellowpages.com", "linkedin.com", "instagram.com", "wikipedia.org"):
                    continue

                comp_key = item_domain
                if comp_key not in candidate_map:
                    candidate_map[comp_key] = {
                        "business_name": item.title or item_domain,
                        "domain": item_domain,
                        "rating": None,
                        "reviews_count": None,
                        "phone": None,
                        "address": None,
                        "source": "serp_organic",
                        "discovered_at": datetime.now(timezone.utc).isoformat(),
                        "evidence": []
                    }

                candidate_map[comp_key]["evidence"].append({
                    "source": "google_organic",
                    "keyword": term,
                    "position": item.position or pos,
                    "location": loc_str,
                    "url": item.link
                })

        candidates_list = list(candidate_map.values())
        final_status = "completed_with_errors" if query_errors else "completed"

        if progress_callback:
            await progress_callback({
                "status": final_status,
                "stage": "Discovery completed",
                "progress": 100.0,
                "keywords_scanned": total_scanned,
                "candidates_found": len(candidates_list),
                "errors_count": len(query_errors)
            })

        return {
            "status": final_status,
            "project_id": project_id,
            "provider": provider.__class__.__name__,
            "capabilities": caps.model_dump(),
            "location_used": loc_str,
            "search_terms_scanned": search_terms,
            "candidates_discovered": candidates_list,
            "total_candidates": len(candidates_list),
            "query_errors": query_errors
        }
