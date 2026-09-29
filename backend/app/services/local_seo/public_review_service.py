import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import Settings
from app.models.project import Project, Location
from app.models.local_seo import Review, BusinessProfile
from app.models.gbp import GoogleBusinessProfile, PublicObservationSnapshot
from app.models.connections import PublicBusinessListing
from app.services.serp import get_organization_serp_provider
from app.services.local_seo.review_classifier_service import ReviewClassifierService

logger = logging.getLogger("locallift.public_review_service")
_settings = Settings()


class PublicReviewService:
    """
    Orchestrates public review ingestion, deduplication, and provenance tracking
    across Google Places API, SerpApi Google Maps Reviews, and Owner-Authorized GBP.
    """

    @classmethod
    async def resolve_place_identifiers(
        cls,
        db: AsyncSession,
        project_id: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolves the canonical Place ID and Data ID for a project.
        """
        # 1. Location
        loc_res = await db.execute(select(Location).where(Location.project_id == project_id))
        loc = loc_res.scalars().first()
        if loc and loc.place_id:
            return loc.place_id, getattr(loc, "data_id", None)

        # 2. GBP profile
        gbp_res = await db.execute(select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id))
        gbp = gbp_res.scalars().first()
        if gbp and gbp.place_id:
            return gbp.place_id, None

        # 3. PublicBusinessListing
        pbl_res = await db.execute(select(PublicBusinessListing).where(PublicBusinessListing.project_id == project_id))
        pbl = pbl_res.scalars().first()
        if pbl and pbl.place_id:
            return pbl.place_id, None

        # 4. BusinessProfile
        bp_res = await db.execute(select(BusinessProfile).where(BusinessProfile.project_id == project_id))
        bp = bp_res.scalars().first()
        if bp and bp.place_id:
            return bp.place_id, None

        return None, None

    @classmethod
    async def sync_project_reviews(
        cls,
        db: AsyncSession,
        project_id: int,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Synchronizes public reviews for a project using the organization's configured SERP provider
        (SerpApi engine=google_maps_reviews) or Google Places API fallback.
        Preserves provenance and eliminates duplicate review records.
        """
        now = datetime.now(timezone.utc)
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalars().first()
        if not project:
            return {
                "status": "ERROR",
                "collection_status": "ERROR",
                "error": f"Project #{project_id} not found.",
                "reviews_synced": 0,
                "total_reviews": 0
            }

        place_id, data_id = await cls.resolve_place_identifiers(db, project_id)
        if not place_id and not data_id:
            return {
                "status": "NOT_CONFIGURED",
                "collection_status": "NOT_CONFIGURED",
                "error": "No Google Place ID or Data ID configured for this project.",
                "reviews_synced": 0,
                "total_reviews": 0
            }

        # 1. Resolve Organization SERP provider (BYO SerpApi)
        provider = await get_organization_serp_provider(db, project.organization_id)
        pages_limit = max_pages or _settings.SERPAPI_MAX_REVIEW_PAGES

        raw_reviews: List[Dict[str, Any]] = []
        collection_status = "NOT_CONFIGURED"
        provider_name = "SERPAPI_GOOGLE_MAPS_REVIEWS"
        total_listing_reviews: Optional[int] = None
        avg_rating: Optional[float] = None
        error_msg: Optional[str] = None
        error_code: Optional[str] = None
        pages_fetched = 0

        if provider and provider.is_configured and getattr(provider, "capabilities", None) and getattr(provider.capabilities, "maps_reviews", False):
            # Execute SerpApi Google Maps Reviews pagination
            serp_res = await provider.get_google_maps_reviews(
                place_id=place_id,
                data_id=data_id,
                max_pages=pages_limit
            )
            raw_reviews = serp_res.get("reviews", [])
            collection_status = serp_res.get("collection_status", "NOT_AVAILABLE")
            total_listing_reviews = serp_res.get("total_reviews_on_listing")
            avg_rating = serp_res.get("average_rating")
            pages_fetched = serp_res.get("pages_fetched", 0)
            error_msg = serp_res.get("error")
            error_code = serp_res.get("error_code")
        else:
            # Fallback to Google Places API if configured
            from app.services.google.public_maps_service import PublicMapsService
            places_res = await PublicMapsService.sync_place_reviews(
                organization_id=project.organization_id,
                project_id=project_id,
                place_id=place_id,
                db=db
            )
            st = places_res.get("status")
            if st == "found":
                provider_name = "Google Places API"
                collection_status = places_res.get("summary", {}).get("review_collection_status", "PARTIAL")
                total_listing_reviews = places_res.get("summary", {}).get("total_google_reviews")
                avg_rating = places_res.get("summary", {}).get("average_rating")
                return {
                    "status": "SUCCESS",
                    "collection_status": collection_status,
                    "provider": provider_name,
                    "reviews_synced": len(places_res.get("reviews", [])),
                    "total_reviews": total_listing_reviews or len(places_res.get("reviews", [])),
                    "average_rating": avg_rating,
                    "pages_fetched": 1,
                    "error": None
                }
            elif st == "not_configured":
                collection_status = "NOT_CONFIGURED"
                error_msg = "Neither SerpApi nor Google Places API is configured."
            else:
                collection_status = "ERROR"
                error_msg = places_res.get("error")

        # 2. Ingest, Deduplicate & Classify Reviews
        saved_count = 0
        seen_ext_ids = set()

        for rev_item in raw_reviews:
            ext_id = rev_item.get("external_review_id")
            author_name = rev_item.get("author_name") or "Google User"
            r_rating = rev_item.get("rating")
            r_text = rev_item.get("review_text") or ""
            r_date_raw = rev_item.get("review_date_raw")

            # Parse date safely
            pub_date = now
            if r_date_raw:
                try:
                    pub_date = datetime.fromisoformat(r_date_raw.replace("Z", "+00:00"))
                except Exception:
                    pub_date = now

            # Deduplication Check
            # Priority 1: Match by (project_id, source="Google", external_review_id)
            # Deduplication Check
            # Priority 1: Match by external_review_id within the project
            existing_rev = None
            if ext_id:
                seen_ext_ids.add(ext_id)
                stmt = select(Review).where(
                    Review.project_id == project_id,
                    Review.external_review_id == ext_id
                )
                res = await db.execute(stmt)
                existing_rev = res.scalars().first()

            # Priority 2: Fallback match by author_name + rating + snippet hash or raw_provider_reference
            if not existing_rev:
                text_hash = hashlib.sha256(f"{author_name}|{r_rating}|{r_text[:80]}".encode()).hexdigest()[:24]
                stmt = select(Review).where(
                    Review.project_id == project_id,
                    (
                        (Review.raw_provider_reference.like(f"%{text_hash}%"))
                        | ((Review.author_name == author_name) & (Review.rating == r_rating) & (Review.review_text == r_text))
                    )
                )
                res = await db.execute(stmt)
                existing_rev = res.scalars().first()

            # Analyze sentiment & topic
            sent_info = ReviewClassifierService.analyze_sentiment(r_text, r_rating)
            cat_info = ReviewClassifierService.classify_review(r_text, r_rating)
            topics_payload = [cat_info["category"]] if cat_info.get("category") else ["Overall Experience"]

            if existing_rev:
                # Update existing record without downgrading owner-authorized status
                if existing_rev.access_mode != "OWNER_AUTHORIZED":
                    existing_rev.access_mode = "PUBLIC"
                    existing_rev.verification_status = "OBSERVED"
                existing_rev.review_text = r_text or existing_rev.review_text
                existing_rev.rating = r_rating if r_rating is not None else existing_rev.rating
                existing_rev.author_photo_url = rev_item.get("author_photo_url") or existing_rev.author_photo_url
                existing_rev.response_text = rev_item.get("response_text") or existing_rev.response_text
                existing_rev.collection_status = "active"
                existing_rev.collected_at = now
                if not existing_rev.sentiment:
                    existing_rev.sentiment = sent_info["sentiment"]
                    existing_rev.sentiment_score = sent_info["sentiment_score"]
                    existing_rev.topics = topics_payload
                db.add(existing_rev)
            else:
                new_rev = Review(
                    project_id=project_id,
                    external_review_id=ext_id,
                    source="Google",
                    access_mode="PUBLIC",
                    verification_status="OBSERVED",
                    author_name=author_name,
                    author_photo_url=rev_item.get("author_photo_url"),
                    rating=r_rating,
                    review_text=r_text,
                    review_date=pub_date,
                    sentiment=sent_info["sentiment"],
                    sentiment_score=sent_info["sentiment_score"],
                    topics=topics_payload,
                    provider_url=rev_item.get("provider_url"),
                    provider_metadata={
                        "provider": "SERPAPI_GOOGLE_MAPS_REVIEWS",
                        "place_id": place_id,
                        "data_id": data_id,
                        "access_mode": "PUBLIC",
                        "verification_status": "OBSERVED"
                    },
                    collected_at=now,
                    raw_provider_reference=f"serpapi:google_maps_reviews:{place_id or data_id}:{ext_id or text_hash}",
                    collection_status="active",
                    response_text=rev_item.get("response_text"),
                    response_status="answered" if rev_item.get("response_text") else "unanswered"
                )
                db.add(new_rev)
                saved_count += 1

        # 3. Create PublicObservationSnapshot
        is_complete = bool(collection_status == "COMPLETE")
        snapshot = PublicObservationSnapshot(
            project_id=project_id,
            organization_id=project.organization_id,
            provider=provider_name,
            place_id=place_id,
            fetched_at=now,
            status="FOUND" if len(raw_reviews) > 0 or (is_complete and total_listing_reviews == 0) else collection_status,
            completeness="COMPLETE" if is_complete else "PARTIAL",
            fields_returned=["reviews", "place_info", "serpapi_pagination"],
            reviews_returned=len(raw_reviews),
            errors=error_msg,
            provider_metadata={
                "total_reviews_on_listing": total_listing_reviews,
                "pages_fetched": pages_fetched,
                "collection_status": collection_status,
                "error_code": error_code
            },
            created_at=now
        )
        db.add(snapshot)
        await db.commit()

        return {
            "status": "SUCCESS" if len(raw_reviews) > 0 or (is_complete and total_listing_reviews == 0) else collection_status,
            "collection_status": collection_status,
            "provider": provider_name,
            "reviews_synced": len(raw_reviews),
            "new_reviews_saved": saved_count,
            "total_reviews_on_listing": total_listing_reviews,
            "average_rating": avg_rating,
            "pages_fetched": pages_fetched,
            "error": error_msg,
            "error_code": error_code,
            "snapshot_id": getattr(snapshot, "id", None)
        }
