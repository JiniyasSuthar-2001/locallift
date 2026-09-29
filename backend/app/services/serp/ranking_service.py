"""
LocalLift — Canonical Keyword Ranking Service

Provides a single authoritative service contract for checking, calculating,
recording, and retrieving keyword rankings across Google Organic and Google Local Pack.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.project import Project, Location
from app.models.ranking import Keyword, KeywordRanking, RankingSnapshot
from app.models.gbp import GoogleBusinessProfile
from app.services.serp.factory import get_organization_serp_provider
from app.services.serp.matcher import DomainMatcher
from app.services.serp.base import SERPResponse, SERPItem

logger = logging.getLogger("locallift.ranking_service")


class KeywordRankingService:
    """
    Canonical service for keyword rank tracking across all entry points:
    - KeywordsView single check
    - KeywordsView check-all
    - Central Intelligence Scan
    - Scheduled background checks
    """

    @staticmethod
    def resolve_serp_config(project: Project, location: Optional[Location] = None, kw_location: Optional[str] = None) -> Dict[str, str]:
        """
        Resolves canonical country, language, device, and location string for SERP checks.
        Ensures strict parity across Central Scan, single keyword check, and bulk check.
        """
        # 1. Country resolution: explicit project.country -> location country -> domain TLD -> None
        country = (project.country or "").strip().lower()
        if not country and location and location.country:
            country = location.country.strip().lower()

        if not country:
            domain = (project.domain or "").lower()
            if domain.endswith(".au") or ".com.au" in domain or ".net.au" in domain:
                country = "au"
            elif domain.endswith(".in") or ".co.in" in domain:
                country = "in"
            elif domain.endswith(".uk") or ".co.uk" in domain:
                country = "uk"
            elif domain.endswith(".ca"):
                country = "ca"
            elif domain.endswith(".nz") or ".co.nz" in domain:
                country = "nz"
            elif domain.endswith(".sg"):
                country = "sg"
            elif domain.endswith(".ae"):
                country = "ae"
            elif domain.endswith(".de"):
                country = "de"
            elif domain.endswith(".fr"):
                country = "fr"
            else:
                country = ""

        # 2. Language
        language = (getattr(project, "language", None) or "en").strip().lower()

        # 3. Location: keyword target_location -> project primary location -> empty
        target_loc = ""
        if kw_location and kw_location.strip():
            target_loc = kw_location.strip()
        elif location:
            parts = [p for p in [location.city, location.state, location.country] if p and p.strip()]
            if parts:
                target_loc = ", ".join(parts)

        return {
            "country": country,
            "language": language,
            "device": "desktop",
            "location": target_loc
        }

    @staticmethod
    def calculate_movement(prev_rank: Optional[int], curr_rank: Optional[int], rank_status: str) -> Tuple[Optional[int], str]:
        """
        Computes numerical movement and descriptive movement label:
        #8 -> #5 = +3, "+3 improved"
        #5 -> #12 = -7, "-7 declined"
        #5 -> NOT_IN_TOP_100 = None, "Lost Top 100 visibility"
        None/NOT_IN_TOP_100 -> #9 = None, "Entered Top 100 (#9)"
        """
        if rank_status == "NOT_IN_TOP_100":
            if prev_rank is not None:
                return None, "Lost Top 100 visibility"
            return None, "Not in Top 100"

        if curr_rank is not None:
            if prev_rank is None:
                return None, f"Entered Top 100 (#{curr_rank})"
            diff = prev_rank - curr_rank  # Positive means improved
            if diff > 0:
                return diff, f"+{diff} improved"
            elif diff < 0:
                return diff, f"{diff} declined"
            else:
                return 0, "No change"

        return None, "—"

    @classmethod
    async def check_keyword(
        cls,
        db: AsyncSession,
        keyword_id: int,
        project_id: int,
        organization_id: int
    ) -> Dict[str, Any]:
        """
        Executes an authoritative SERP check for a single keyword.
        Never fabricates ranking values or promotes previous ranks on failed check attempts.
        Updates Keyword model, persists KeywordRanking history, and returns structured result.
        """
        now = datetime.now(timezone.utc)

        # 1. Fetch Keyword and Project context
        kw_res = await db.execute(select(Keyword).where(Keyword.id == keyword_id, Keyword.project_id == project_id))
        kw = kw_res.scalars().first()
        if not kw:
            raise ValueError(f"Keyword #{keyword_id} not found for Project #{project_id}")

        proj_res = await db.execute(
            select(Project)
            .options(selectinload(Project.locations))
            .where(Project.id == project_id)
        )
        project = proj_res.scalars().first()
        if not project:
            raise ValueError(f"Project #{project_id} not found")

        primary_loc = project.locations[0] if project.locations else None

        # Fetch Place ID if available for Google Local match
        gbp_res = await db.execute(select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id))
        gbp = gbp_res.scalars().first()
        target_place_id = (gbp.place_id if gbp else None) or (getattr(primary_loc, "place_id", None) if primary_loc else None)

        # 2. Resolve SERP config
        serp_cfg = cls.resolve_serp_config(project, primary_loc, kw.target_location)

        # 3. Fetch Provider
        provider = await get_organization_serp_provider(db, organization_id)
        kw.last_attempted_at = now

        if not getattr(provider, "is_configured", True):
            kw.rank_status = "NOT_CONFIGURED"
            kw.last_failed_at = now
            await db.commit()
            await db.refresh(kw)
            return {
                "keyword_id": kw.id,
                "keyword": kw.keyword,
                "target_domain": project.domain or "",
                "current_rank": None,
                "previous_rank": kw.current_rank,
                "organic_rank": None,
                "local_pack_rank": None,
                "maps_rank": None,
                "rank_movement": None,
                "movement_label": "Provider not configured",
                "ranking_url": None,
                "ranking_title": None,
                "serp_type": kw.serp_type,
                "provider": getattr(provider, "provider_name", type(provider).__name__),
                "status": "not_configured",
                "error_message": "SERP provider not configured. Connect your SERP provider in Settings to enable keyword tracking.",
                "last_checked_at": kw.last_successful_check_at or kw.last_checked_at
            }

        # 4. Search SERP
        try:
            serp_resp = await provider.search_keyword(
                keyword=kw.keyword,
                location=serp_cfg["location"] or None,
                country=serp_cfg["country"],
                language=serp_cfg["language"],
                device=serp_cfg["device"]
            )
        except Exception as ex:
            is_timeout = "timeout" in str(ex).lower()
            kw.rank_status = "TIMEOUT" if is_timeout else "PROVIDER_ERROR"
            kw.last_failed_at = now
            await db.commit()
            await db.refresh(kw)
            return {
                "keyword_id": kw.id,
                "keyword": kw.keyword,
                "target_domain": project.domain or "",
                "current_rank": None,
                "previous_rank": kw.current_rank,
                "organic_rank": None,
                "local_pack_rank": None,
                "maps_rank": None,
                "rank_movement": None,
                "movement_label": "Check failed",
                "ranking_url": None,
                "ranking_title": None,
                "serp_type": kw.serp_type,
                "provider": getattr(provider, "provider_name", type(provider).__name__),
                "status": "timeout" if is_timeout else "provider_error",
                "error_message": str(ex),
                "last_checked_at": kw.last_successful_check_at or kw.last_checked_at
            }

        if not serp_resp.success:
            err_code = getattr(serp_resp, "error_code", "SERP_ERROR")
            if err_code == "SERP_PROVIDER_NOT_CONFIGURED":
                status_label = "not_configured"
                db_status = "NOT_CONFIGURED"
            elif err_code == "TIMEOUT" or (serp_resp.error_message and "timeout" in serp_resp.error_message.lower()):
                status_label = "timeout"
                db_status = "TIMEOUT"
            elif err_code == "LOCATION_ERROR" or (serp_resp.error_message and "location" in serp_resp.error_message.lower()):
                status_label = "location_error"
                db_status = "LOCATION_ERROR"
            else:
                status_label = "provider_error"
                db_status = "PROVIDER_ERROR"

            kw.rank_status = db_status
            kw.last_failed_at = now
            await db.commit()
            await db.refresh(kw)
            return {
                "keyword_id": kw.id,
                "keyword": kw.keyword,
                "target_domain": project.domain or "",
                "current_rank": None,
                "previous_rank": kw.current_rank,
                "organic_rank": None,
                "local_pack_rank": None,
                "maps_rank": None,
                "rank_movement": None,
                "movement_label": "Check failed",
                "ranking_url": None,
                "ranking_title": None,
                "serp_type": kw.serp_type,
                "provider": serp_resp.provider or getattr(provider, "provider_name", "serp_provider"),
                "status": status_label,
                "error_message": serp_resp.error_message or "SERP request returned unsuccessful response.",
                "last_checked_at": kw.last_successful_check_at or kw.last_checked_at
            }

        # 5. Evaluate Distinct Surfaces: Organic vs Local Pack
        organic_rank: Optional[int] = None
        organic_url: Optional[str] = None
        organic_title: Optional[str] = None

        local_pack_rank: Optional[int] = None
        local_pack_title: Optional[str] = None

        # Check if provider explicitly supports local pack
        supports_local = bool(getattr(provider, "capabilities", None) and getattr(provider.capabilities, "local_search", False))

        # A. Organic Results Search
        for item in (serp_resp.organic_results or []):
            if DomainMatcher.matches_target(item.link, project.domain or ""):
                organic_rank = item.position
                organic_url = item.link
                organic_title = item.title
                break

        # B. Local Pack Results Search
        if supports_local and serp_resp.local_pack_results:
            for item in serp_resp.local_pack_results:
                is_match = False
                if target_place_id and item.place_id and item.place_id.strip() == target_place_id.strip():
                    is_match = True
                elif DomainMatcher.matches_target(item.link, project.domain or ""):
                    is_match = True
                elif DomainMatcher._normalize_name(item.title) == DomainMatcher._normalize_name(project.name):
                    is_match = True

                if is_match:
                    local_pack_rank = item.position
                    local_pack_title = item.title
                    break

        # C. Combined Primary Display Rank
        # If both exist, primary is the lowest/best position
        candidates = [r for r in [local_pack_rank, organic_rank] if r is not None]
        primary_rank = min(candidates) if candidates else None

        if primary_rank is not None:
            rank_status = "RANKED"
            primary_url = organic_url or (f"https://{project.domain}" if project.domain else None)
            primary_title = local_pack_title or organic_title or project.name
            primary_serp_type = "Local Pack" if local_pack_rank is not None else "Organic"
        else:
            rank_status = "NOT_IN_TOP_100"
            primary_url = None
            primary_title = None
            primary_serp_type = "Organic"

        # Movement calculated from previous successful rank
        diff, movement_label = cls.calculate_movement(kw.current_rank, primary_rank, rank_status)

        # Update Keyword Model
        kw.previous_rank = kw.current_rank
        kw.current_rank = primary_rank
        kw.organic_rank = organic_rank
        kw.local_pack_rank = local_pack_rank
        kw.rank_status = rank_status
        kw.ranking_url = primary_url
        kw.ranking_title = primary_title
        kw.serp_type = primary_serp_type
        kw.last_checked_at = now
        kw.last_successful_check_at = now

        # Add History Entry
        db.add(KeywordRanking(
            keyword_id=kw.id,
            location_name=serp_cfg["location"] or "Default",
            rank_position=primary_rank,
            organic_rank=organic_rank,
            local_pack_rank=local_pack_rank,
            rank_status=rank_status,
            serp_type=primary_serp_type,
            ranking_url=primary_url,
            country=serp_cfg["country"],
            device=serp_cfg["device"],
            checked_at=now
        ))

        # Add Ranking Snapshot for audit trail
        db.add(RankingSnapshot(
            project_id=project_id,
            keyword_id=kw.id,
            keyword=kw.keyword,
            location=serp_cfg["location"] or None,
            country=serp_cfg["country"],
            language=serp_cfg["language"],
            device=serp_cfg["device"],
            provider=serp_resp.provider or "serpapi",
            position=primary_rank,
            ranking_url=primary_url,
            serp_features=[f for f in ["local_pack", "organic"] if (local_pack_rank if f == "local_pack" else organic_rank) is not None],
            status="success" if rank_status == "RANKED" else "not_in_top_100",
            checked_at=now
        ))

        await db.commit()
        await db.refresh(kw)

        return {
            "keyword_id": kw.id,
            "keyword": kw.keyword,
            "target_domain": project.domain or "",
            "current_rank": primary_rank,
            "previous_rank": kw.previous_rank,
            "organic_rank": organic_rank,
            "local_pack_rank": local_pack_rank,
            "maps_rank": kw.maps_rank,
            "rank_movement": diff,
            "movement_label": movement_label,
            "ranking_url": primary_url,
            "ranking_title": primary_title,
            "serp_type": primary_serp_type,
            "provider": serp_resp.provider or "serpapi",
            "status": "checked" if rank_status == "RANKED" else "not_in_top_100",
            "error_message": None,
            "last_checked_at": now
        }

    @classmethod
    async def check_all_project_keywords(
        cls,
        db: AsyncSession,
        project_id: int,
        organization_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes live SERP checks for all active keywords in a project.
        """
        if organization_id is None:
            proj_res = await db.execute(select(Project).where(Project.id == project_id))
            proj = proj_res.scalars().first()
            organization_id = proj.organization_id if proj else None

        now = datetime.now(timezone.utc)
        kw_res = await db.execute(select(Keyword).where(Keyword.project_id == project_id))
        keywords = kw_res.scalars().all()

        results: List[Dict[str, Any]] = []
        checked_count = 0
        not_found_count = 0
        error_count = 0
        provider_name = "serp_provider"

        for kw in keywords:
            res = await cls.check_keyword(
                db=db,
                keyword_id=kw.id,
                project_id=project_id,
                organization_id=organization_id
            )
            results.append(res)
            provider_name = res.get("provider") or provider_name
            if res.get("status") == "checked":
                checked_count += 1
            elif res.get("status") == "not_in_top_100":
                not_found_count += 1
            else:
                error_count += 1

        return {
            "project_id": project_id,
            "checked_count": checked_count,
            "not_found_count": not_found_count,
            "error_count": error_count,
            "provider": provider_name,
            "results": results,
            "checked_at": now
        }
