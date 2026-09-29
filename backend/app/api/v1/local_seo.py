import os
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import io
import csv
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger("locallift.local_seo")

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access
from app.models.user import User
from app.models.project import Project, Website, Location
from app.models.local_seo import Review, Citation, NAPRecord, Competitor, SchemaRecord
from app.models.audit import WebsitePage
from app.services.crawler import WebsiteCrawler
from app.models.connections import PublicBusinessListing
from app.services.google.public_maps_service import PublicGoogleMapsService
from app.services.local_seo.public_review_service import PublicReviewService
from app.services.local_seo.review_classifier_service import ReviewClassifierService
from app.services.serp.factory import get_organization_serp_provider
from app.services.serp.matcher import DomainMatcher
from app.services.reports.competitor_pdf_service import CompetitorPDFService
from app.schemas.local_seo import (
    ReviewOut, ReviewDraftResponse, ReviewApprovePublish,
    CitationCreate, CitationOut, CitationDistributionOut, CitationStatusUpdate,
    NAPRecordOut, CompetitorCreate, CompetitorOut,
    CompetitorSearchRequest, CompetitorSearchResponse, CompetitorCandidateOut,
    SchemaRecordOut, SchemaGenerateRequest,
    SchemaValidateRequest, SchemaValidateUrlRequest, SchemaDraftSaveRequest,
    SchemaValidateResponse, SchemaIntelligenceSummaryOut,
    PublicReviewsResponse, PublicPlaceInfo, PublicReviewSummary, PlaceSelectRequest
)
from app.services.ai_assistant import AIAssistantService
from app.services.ai_consumption_service import AIConsumptionService
from app.services.schema_intelligence import SchemaIntelligenceEngine, TIER_1_SCHEMAS, INDUSTRY_SCHEMAS
from app.services.schema_vocabulary import SchemaVocabulary, SCHEMA_CATEGORIES


router = APIRouter(prefix="/local-seo", tags=["Local SEO & Reputation"])


# ─── Public Places & Reviews Intelligence ───

@router.get("/places/search")
async def search_places(
    project_id: int,
    query: str,
    country: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Searches Google Places API (New) for matching public business locations.
    """
    await verify_project_access(project_id, current_user, db)
    res = await PublicGoogleMapsService.search_places_for_selection(query=query, country=country)
    return res


@router.post("/places/select")
async def select_place_for_project(
    payload: PlaceSelectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Binds a selected Google Place ID to the project and initiates public review synchronization.
    """
    project = await verify_project_access(payload.project_id, current_user, db)

    # 1. Update/create PublicBusinessListing
    pbl_stmt = select(PublicBusinessListing).where(
        PublicBusinessListing.organization_id == project.organization_id,
        PublicBusinessListing.project_id == project.id
    )
    pbl_res = await db.execute(pbl_stmt)
    listing = pbl_res.scalars().first()

    now = datetime.now(timezone.utc)
    if not listing:
        listing = PublicBusinessListing(
            organization_id=project.organization_id,
            project_id=project.id,
            place_id=payload.place_id,
            name=payload.name or project.name,
            formatted_address=payload.formatted_address,
            rating=payload.rating,
            review_count=payload.user_rating_count,
            maps_url=payload.maps_url,
            website_url=payload.website_url,
            latitude=payload.latitude,
            longitude=payload.longitude,
            source="google_places_api",
            lookup_status="found",
            lookup_error=None,
            last_checked_at=now
        )
        db.add(listing)
    else:
        listing.place_id = payload.place_id
        if payload.name:
            listing.name = payload.name
        if payload.formatted_address:
            listing.formatted_address = payload.formatted_address
        if payload.rating is not None:
            listing.rating = payload.rating
        if payload.user_rating_count is not None:
            listing.review_count = payload.user_rating_count
        if payload.maps_url:
            listing.maps_url = payload.maps_url
        if payload.website_url:
            listing.website_url = payload.website_url
        listing.lookup_status = "found"
        listing.lookup_error = None
        listing.last_checked_at = now

    # 2. Update BusinessProfile
    from app.models.local_seo import BusinessProfile
    bp_stmt = select(BusinessProfile).where(BusinessProfile.project_id == project.id)
    bp_res = await db.execute(bp_stmt)
    bp = bp_res.scalars().first()
    if bp:
        bp.place_id = payload.place_id
        if payload.maps_url:
            bp.maps_url = payload.maps_url
        if payload.formatted_address:
            bp.primary_address = payload.formatted_address

    # 3. Update primary Location
    loc_stmt = select(Location).where(Location.project_id == project.id)
    loc_res = await db.execute(loc_stmt)
    loc = loc_res.scalars().first()
    if loc:
        loc.place_id = payload.place_id
        if payload.latitude:
            loc.latitude = payload.latitude
        if payload.longitude:
            loc.longitude = payload.longitude

    await db.commit()

    # 4. Immediately sync public reviews
    sync_res = await PublicGoogleMapsService.fetch_and_sync_public_reviews(
        organization_id=project.organization_id,
        project_id=project.id,
        db=db,
        explicit_place_id=payload.place_id
    )

    return sync_res


@router.get("/reviews/{project_id}")
async def list_reviews(
    project_id: int,
    sentiment: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    response_status: Optional[str] = None,
    sort_by: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns public Google customer reviews and comprehensive sentiment/category intelligence.
    Automatically fetches public reviews via Google Places API (New) if Place ID is registered.
    """
    project = await verify_project_access(project_id, current_user, db)

    # 1. Fetch place info
    pbl_stmt = select(PublicBusinessListing).where(
        PublicBusinessListing.organization_id == project.organization_id,
        PublicBusinessListing.project_id == project.id
    )
    pbl_res = await db.execute(pbl_stmt)
    listing = pbl_res.scalars().first()

    # Check BusinessProfile place_id if listing place_id is empty
    from app.models.local_seo import BusinessProfile
    bp_stmt = select(BusinessProfile).where(BusinessProfile.project_id == project.id)
    bp_res = await db.execute(bp_stmt)
    bp = bp_res.scalars().first()

    effective_place_id = (listing.place_id if listing else None) or (bp.place_id if bp else None)

    # 2. Check existing reviews in DB
    rev_count_stmt = select(Review).where(Review.project_id == project_id)
    db_reviews_res = await db.execute(rev_count_stmt)
    all_db_reviews = db_reviews_res.scalars().all()

    # If place_id exists but no reviews cached yet, execute initial public fetch
    if effective_place_id and len(all_db_reviews) == 0:
        sync_result = await PublicGoogleMapsService.fetch_and_sync_public_reviews(
            organization_id=project.organization_id,
            project_id=project.id,
            db=db,
            explicit_place_id=effective_place_id
        )
        if sync_result.get("status") == "found":
            return sync_result

    # 3. Format and enrich all reviews from DB
    formatted_reviews = []
    positive_count = 0
    neutral_count = 0
    negative_count = 0
    category_counts: Dict[str, int] = {}

    for rev in all_db_reviews:
        topics = rev.topics or {}
        if isinstance(topics, list):
            topics = {"category": topics[0] if topics else "OTHER", "topic_list": topics}
        elif not isinstance(topics, dict):
            topics = {}

        rev_cat = topics.get("category")
        if not rev_cat:
            cat_calc = ReviewClassifierService.classify_review(rev.review_text, rev.rating)
            rev_cat = cat_calc["category"]
            topics["category"] = rev_cat
            topics["category_confidence"] = cat_calc["confidence"]
            topics["topic_list"] = cat_calc.get("topics", [])

        topic_list = topics.get("topic_list")
        if not topic_list and rev.review_text:
            topic_list = ReviewClassifierService.extract_topics(rev.review_text)
        if not topic_list:
            topic_list = ["Overall Experience"]

        rev_sent = rev.sentiment or "neutral"
        if rev_sent.lower() == "positive":
            positive_count += 1
        elif rev_sent.lower() == "negative":
            negative_count += 1
        else:
            neutral_count += 1

        category_counts[rev_cat] = category_counts.get(rev_cat, 0) + 1

        rev_item = {
            "id": rev.id,
            "project_id": rev.project_id,
            "source": rev.source or "Google Places API",
            "access_mode": getattr(rev, "access_mode", None) or ("OWNER_AUTHORIZED" if "Business Profile" in (rev.source or "") else "PUBLIC"),
            "verification_status": getattr(rev, "verification_status", None) or ("VERIFIED" if "Business Profile" in (rev.source or "") else "OBSERVED"),
            "external_review_id": getattr(rev, "external_review_id", None),
            "raw_provider_reference": getattr(rev, "raw_provider_reference", None),
            "provider_metadata": getattr(rev, "provider_metadata", None),
            "author_name": rev.author_name or "Google Reviewer",
            "author_photo_url": rev.author_photo_url,
            "author_uri": topics.get("author_uri"),
            "rating": rev.rating or 5,
            "review_text": rev.review_text or "",
            "review_date": rev.review_date.isoformat() if rev.review_date else None,
            "published_at": rev.review_date.isoformat() if rev.review_date else None,
            "relative_publish_time_description": topics.get("relative_publish_time_description"),
            "google_maps_uri": topics.get("google_maps_uri") or (listing.maps_url if listing else None),
            "category": rev_cat,
            "category_confidence": topics.get("category_confidence", 0.9),
            "sentiment": rev_sent,
            "sentiment_score": rev.sentiment_score or 0.8,
            "topics": topic_list,
            "topic_list": topic_list,
            "response_text": rev.response_text,
            "response_status": rev.response_status or "unanswered",
            "created_at": rev.created_at.isoformat() if rev.created_at else None
        }
        formatted_reviews.append(rev_item)

    # 4. Apply Filters
    filtered_reviews = formatted_reviews
    if sentiment and sentiment.lower() != "all":
        filtered_reviews = [r for r in filtered_reviews if (r.get("sentiment") or "").lower() == sentiment.strip().lower()]

    if category and category.lower() != "all":
        filtered_reviews = [r for r in filtered_reviews if (r.get("category") or "").upper() == category.strip().upper()]

    if search and search.strip():
        q_term = search.strip().lower()
        filtered_reviews = [
            r for r in filtered_reviews
            if q_term in (r.get("review_text") or "").lower()
            or q_term in (r.get("author_name") or "").lower()
            or q_term in (r.get("category") or "").lower()
            or any(q_term in str(t).lower() for t in r.get("topic_list", []))
        ]

    if response_status and response_status.lower() != "all":
        filtered_reviews = [r for r in filtered_reviews if (r.get("response_status") or "").lower() == response_status.strip().lower()]

    # 5. Apply Sorting
    ordering_label = "Google Relevance"
    if sort_by == "newest":
        filtered_reviews = sorted(filtered_reviews, key=lambda r: r.get("review_date") or "", reverse=True)
        ordering_label = "Newest Published"
    elif sort_by == "rating_desc":
        filtered_reviews = sorted(filtered_reviews, key=lambda r: r.get("rating") or 0, reverse=True)
        ordering_label = "Highest Rating"
    elif sort_by == "rating_asc":
        filtered_reviews = sorted(filtered_reviews, key=lambda r: r.get("rating") or 0)
        ordering_label = "Lowest Rating"

    from app.config import settings
    from app.models.gbp import GoogleAccount, GoogleBusinessProfile
    from app.models.connections import GoogleConnection

    api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", "").strip()

    # Resolve connected Google Account for this project
    gbp_prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id)
    )
    gbp_prof = gbp_prof_res.scalars().first()
    connected_email = None
    if gbp_prof:
        if gbp_prof.google_account_id:
            gacc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.id == gbp_prof.google_account_id))
            gacc = gacc_res.scalars().first()
            if gacc:
                connected_email = gacc.account_email
        elif gbp_prof.google_connection_id:
            conn_res = await db.execute(select(GoogleConnection).where(GoogleConnection.id == gbp_prof.google_connection_id))
            gconn = conn_res.scalars().first()
            if gconn:
                connected_email = gconn.account_email

    total_google_revs = listing.review_count if (listing and listing.review_count is not None) else len(formatted_reviews)
    avg_rating = listing.rating if (listing and listing.rating is not None) else (
        round(sum(r["rating"] for r in formatted_reviews) / len(formatted_reviews), 1) if formatted_reviews else None
    )

    place_info = None
    if effective_place_id:
        place_info = {
            "place_id": effective_place_id,
            "name": (listing.name if listing else None) or project.name,
            "formatted_address": listing.formatted_address if listing else (bp.primary_address if bp else None),
            "rating": avg_rating,
            "user_rating_count": total_google_revs,
            "maps_url": listing.maps_url if listing else (bp.maps_url if bp else None),
            "website_url": listing.website_url if listing else (bp.website if bp else None),
            "last_synced_at": listing.last_checked_at.isoformat() if (listing and listing.last_checked_at) else None,
            "connected_google_account": connected_email
        }

    summary_payload = {
        "total_google_reviews": total_google_revs,
        "reviews_available": len(filtered_reviews),
        "stored_reviews_count": len(all_db_reviews),
        "average_rating": avg_rating,
        "positive_count": positive_count,
        "neutral_count": neutral_count,
        "negative_count": negative_count,
        "categories_breakdown": category_counts,
        "reviews_ordering": ordering_label,
        "last_synced_at": listing.last_checked_at.isoformat() if (listing and listing.last_checked_at) else None,
        "connected_google_account": connected_email,
        "places_api_configured": bool(api_key or os.environ.get("TESTING") == "true"),
        "has_place_id": bool(effective_place_id)
    }

    return {
        "status": "found" if effective_place_id else "no_place_id",
        "error": None if effective_place_id else "Select a Google business location to load public reviews.",
        "place": place_info,
        "reviews": filtered_reviews,
        "summary": summary_payload
    }


@router.post("/reviews/{project_id}/public-sync")
async def sync_public_reviews(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Explicitly synchronizes live public reviews from Google Places API (New) / SerpApi Google Maps Reviews.
    Does NOT require GBP OAuth credentials.
    """
    project = await verify_project_access(project_id, current_user, db)
    res = await PublicReviewService.sync_project_reviews(
        db=db,
        project_id=project.id
    )
    return res


@router.post("/reviews/{project_id}/sync")
async def sync_reviews_from_gbp(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Synchronizes live customer reviews directly from the connected Google Business Profile API.
    Preserves manual reviews, deduplicates by author/source, and updates project reviews score.
    """
    proj = await verify_project_access(project_id, current_user, db)
    from app.models.gbp import GoogleAccount, GoogleBusinessProfile
    from app.models.connections import GoogleConnection
    from app.services.google.gbp_client import GoogleBusinessProfileClient
    from app.services.google.connections_service import GoogleConnectionsService
    from app.core.security import decrypt_token

    # 1. Fetch exact project-bound GoogleBusinessProfile
    prof_res = await db.execute(
        select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id)
    )
    profile = prof_res.scalars().first()
    if not profile or not profile.location_resource_name:
        raise HTTPException(
            status_code=400,
            detail="No Google Business Profile is bound to this project. Please connect and select your specific location in Connections."
        )

    # 2. Retrieve GBP connection or GoogleAccount credentials
    access_token = None
    refresh_token = None
    expiry = None

    if profile.google_connection_id:
        conn_res = await db.execute(
            select(GoogleConnection).where(GoogleConnection.id == profile.google_connection_id)
        )
        conn = conn_res.scalars().first()
        if conn and conn.status in ("connected", "expired") and conn.access_token:
            access_token = await GoogleConnectionsService.get_valid_access_token(conn, db)
            refresh_token = decrypt_token(conn.refresh_token) if conn.refresh_token else None
            expiry = conn.token_expiry

    if not access_token:
        gbp_conn = await GoogleConnectionsService.get_connection_for_service(proj.organization_id, "business_profile", db)
        if gbp_conn and gbp_conn.status in ("connected", "expired") and gbp_conn.access_token:
            access_token = await GoogleConnectionsService.get_valid_access_token(gbp_conn, db)
            refresh_token = decrypt_token(gbp_conn.refresh_token) if gbp_conn.refresh_token else None
            expiry = gbp_conn.token_expiry
        else:
            acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
            g_acc = acc_res.scalars().first()
            if g_acc and g_acc.access_token:
                access_token = decrypt_token(g_acc.access_token)
                refresh_token = decrypt_token(g_acc.refresh_token) if g_acc.refresh_token else None
                expiry = g_acc.token_expiry

    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="Google Business Profile authorization credentials missing or expired. Please connect your Google account in Connections."
        )

    client = GoogleBusinessProfileClient(
        access_token=access_token,
        refresh_token=refresh_token,
        token_expiry=expiry
    )

    account_resource = profile.account_resource_name or profile.account_id or "accounts/default"
    location_resource = profile.location_resource_name or profile.location_name

    # 3. Fetch live reviews strictly for this bound location
    try:
        reviews_data = await client.fetch_location_reviews(account_resource, location_resource)
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "RATE_LIMIT_EXCEEDED" in err_str:
            raise HTTPException(
                status_code=400,
                detail="GBP API access is not approved or quota is 0 for this GCP project. Live review sync is paused."
            )
        raise HTTPException(status_code=502, detail=f"Google Reviews API request failed: {err_str}")

    new_count = 0
    updated_count = 0

    for rev in reviews_data:
        existing_res = await db.execute(
            select(Review).where(
                Review.project_id == project_id,
                Review.author_name == rev["author_name"],
                Review.source == "Google"
            )
        )
        existing = existing_res.scalars().first()

        if existing:
            existing.rating = rev["rating"]
            existing.review_text = rev["review_text"]
            if rev.get("response_text"):
                existing.response_text = rev["response_text"]
                existing.response_status = rev["response_status"]
            existing.sentiment = "positive" if rev["rating"] >= 4 else ("neutral" if rev["rating"] == 3 else "negative")
            updated_count += 1
        else:
            new_rev = Review(
                project_id=project_id,
                source="Google",
                author_name=rev["author_name"],
                author_photo_url=rev.get("author_photo_url"),
                rating=rev["rating"],
                review_text=rev.get("review_text"),
                review_date=rev.get("review_date", datetime.now(timezone.utc)),
                response_text=rev.get("response_text"),
                response_status=rev.get("response_status", "unanswered"),
                sentiment="positive" if rev["rating"] >= 4 else ("neutral" if rev["rating"] == 3 else "negative")
            )
            db.add(new_rev)
            new_count += 1

    # Recalculate project reviews_score
    all_rev_res = await db.execute(select(Review).where(Review.project_id == project_id))
    all_reviews = all_rev_res.scalars().all()
    if all_reviews:
        tot = len(all_reviews)
        answered = len([r for r in all_reviews if r.response_status in ("published", "answered")])
        avg_r = sum(r.rating for r in all_reviews) / tot
        new_score = max(0, min(100, int(((avg_r / 5.0) * 70.0) + ((answered / tot) * 30.0))))
        proj.reviews_score = new_score

    await db.commit()

    return {
        "success": True,
        "message": f"Successfully synchronized {len(reviews_data)} reviews from Google Business Profile.",
        "new_reviews": new_count,
        "updated_reviews": updated_count,
        "total_reviews": len(all_reviews),
        "reviews_score": proj.reviews_score
    }

@router.post("/reviews/draft-response")
async def draft_review_response(
    req: ReviewDraftResponse,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Review).where(Review.id == req.review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    proj = await verify_project_access(review.project_id, current_user, db)
    business_name = proj.name if proj else "Our Business"

    async def _call_provider():
        return await AIAssistantService.draft_review_response(
            author_name=review.author_name,
            rating=review.rating,
            review_text=review.review_text or "",
            business_name=business_name,
            business_category=proj.primary_category if proj else None
        )

    drafted_text = await AIConsumptionService.execute_gated_request(
        db=db,
        user=current_user,
        project_id=review.project_id,
        task_type="review_response",
        provider_fn=_call_provider,
        requested_cost=1.0
    )

    review.response_text = drafted_text
    review.response_status = "drafted"
    await db.commit()
    await db.refresh(review)
    return {"message": "AI draft created successfully", "review": review, "draft_response": drafted_text}

@router.post("/reviews/{review_id}/approve")
@router.post("/reviews/{review_id}/approve-publish")
@router.post("/reviews/{review_id}/respond")
async def approve_and_save_review_response(
    review_id: int,
    payload: ReviewApprovePublish,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    await verify_project_access(review.project_id, current_user, db)

    review.response_text = payload.response_text
    review.response_status = "approved" if payload.action in (None, "approved", "save_draft") else payload.action
    review.response_date = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(review)
    return {"message": "Response approved and saved locally.", "review": review}

# ─── Local Citations & Directory Distribution Engine ───

DIRECTORY_CATALOG = [
    {
        "source_name": "Google Business Profile",
        "domain": "google.com",
        "category": "Core Map & Search",
        "domain_authority": 98,
        "claim_url": "https://business.google.com",
        "submission_type": "api"
    },
    {
        "source_name": "Apple Maps",
        "domain": "maps.apple.com",
        "category": "Core Map & Search",
        "domain_authority": 96,
        "claim_url": "https://mapsconnect.apple.com",
        "submission_type": "manual"
    },
    {
        "source_name": "Bing Places",
        "domain": "bingplaces.com",
        "category": "Search & Navigation",
        "domain_authority": 93,
        "claim_url": "https://www.bingplaces.com",
        "submission_type": "manual"
    },
    {
        "source_name": "Yelp",
        "domain": "yelp.com",
        "category": "Local Reviews & Directory",
        "domain_authority": 94,
        "claim_url": "https://biz.yelp.com",
        "submission_type": "manual"
    },
    {
        "source_name": "YellowPages",
        "domain": "yellowpages.com",
        "category": "General Directory",
        "domain_authority": 87,
        "claim_url": "https://adsolutions.yp.com/claim-your-listing",
        "submission_type": "manual"
    },
    {
        "source_name": "Better Business Bureau",
        "domain": "bbb.org",
        "category": "Trust & Accreditation",
        "domain_authority": 91,
        "claim_url": "https://www.bbb.org/get-listed",
        "submission_type": "manual"
    },
    {
        "source_name": "Foursquare",
        "domain": "foursquare.com",
        "category": "Location Data Aggregator",
        "domain_authority": 92,
        "claim_url": "https://foursquare.com/business",
        "submission_type": "manual"
    },
    {
        "source_name": "MapQuest",
        "domain": "mapquest.com",
        "category": "Navigation & Maps",
        "domain_authority": 89,
        "claim_url": "https://business.mapquest.com",
        "submission_type": "manual"
    },
    {
        "source_name": "Hotfrog",
        "domain": "hotfrog.com",
        "category": "General Directory",
        "domain_authority": 76,
        "claim_url": "https://www.hotfrog.com/add",
        "submission_type": "manual"
    },
    {
        "source_name": "CitySearch",
        "domain": "citysearch.com",
        "category": "City Guide",
        "domain_authority": 81,
        "claim_url": "https://www.citysearch.com",
        "submission_type": "manual"
    }
]


@router.get("/citations/{project_id}", response_model=List[CitationOut])
async def list_citations(
    project_id: int,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns verified and tracked directory citations for a project without injecting fake data.
    """
    await verify_project_access(project_id, current_user, db)

    query = select(Citation).where(Citation.project_id == project_id)
    if status_filter and status_filter.lower() != "all":
        query = query.where(Citation.status.ilike(status_filter.strip()))
    
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            (Citation.source_name.ilike(term)) |
            (Citation.domain.ilike(term)) |
            (Citation.category.ilike(term))
        )

    result = await db.execute(query.order_by(Citation.domain_authority.desc().nullslast(), Citation.id.desc()))
    return result.scalars().all()


@router.get("/citations/{project_id}/distribution", response_model=CitationDistributionOut)
async def get_citation_distribution(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculates live citation distribution health, directory coverage, NAP consistency, and approval metrics
    from actual tracked citation records in the database.
    """
    await verify_project_access(project_id, current_user, db)

    result = await db.execute(
        select(Citation).where(Citation.project_id == project_id).order_by(Citation.id.desc())
    )
    citations = result.scalars().all()

    total = len(citations)
    approved_count = 0
    submitted_count = 0
    pending_count = 0
    rejected_count = 0
    failed_count = 0
    missing_count = 0
    verified_count = 0
    observed_count = 0
    mismatch_count = 0
    unable_to_verify_count = 0

    for c in citations:
        st = (c.status or "").lower()
        v_st = (c.verification_status or "").upper()
        nap = (c.nap_status or "").lower()

        if v_st == "VERIFIED":
            verified_count += 1
            approved_count += 1
        elif v_st == "OBSERVED":
            observed_count += 1
            approved_count += 1
        elif v_st == "MISMATCH" or nap == "mismatch":
            mismatch_count += 1
        elif v_st in ["UNABLE_TO_VERIFY", "NOT_VERIFIED"]:
            unable_to_verify_count += 1

        if st in ["approved", "listed"]:
            pass
        elif st in ["submitted", "manual_required"]:
            submitted_count += 1
        elif st == "pending":
            pending_count += 1
        elif st == "rejected":
            rejected_count += 1
        elif st in ["failed", "provider_error"]:
            failed_count += 1
        elif st in ["missing", "unclaimed"]:
            missing_count += 1

    # Load canonical profile and NAP comparisons
    from app.services.local_seo.nap_service import NAPComparisonService
    from app.services.local_seo.business_profile_service import BusinessProfileService

    nap_comp_res = await NAPComparisonService.compare_project_nap(project_id, db)
    canonical_profile = nap_comp_res.get("canonical_profile")
    nap_comparisons = nap_comp_res.get("comparisons", [])
    nap_consistency_pct = nap_comp_res.get("nap_consistency_pct") or 0

    completion_pct = int(round(((verified_count + observed_count) / max(1, total)) * 100)) if total else 0
    health_score = int(round(nap_consistency_pct * 0.6 + completion_pct * 0.4)) if total else 0

    last_scanned = max([c.last_checked_at for c in citations if c.last_checked_at], default=None)

    return {
        "health_score": health_score,
        "total_directories": total,
        "total_citations": total,
        "submitted_count": submitted_count,
        "approved_count": approved_count,
        "verified_count": verified_count,
        "observed_count": observed_count,
        "mismatch_count": mismatch_count,
        "unable_to_verify_count": unable_to_verify_count,
        "pending_count": pending_count,
        "rejected_count": rejected_count,
        "failed_count": failed_count,
        "nap_consistency_pct": nap_consistency_pct,
        "missing_count": missing_count,
        "completion_pct": completion_pct,
        "last_scanned_at": last_scanned,
        "canonical_profile": canonical_profile,
        "nap_comparisons": nap_comparisons,
        "citations": citations
    }


@router.post("/citations/{project_id}/discover")
@router.post("/citations/{project_id}/scan-verify")
async def discover_citations(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes open-web citation discovery and listing verification using multi-query SERP exploration
    and live page NAP extraction. Does not rely on a fixed catalog.
    """
    project = await verify_project_access(project_id, current_user, db)

    from app.services.local_seo.business_profile_service import BusinessProfileService
    from app.services.local_seo.citation_service import CitationService
    from app.services.serp.factory import get_organization_serp_provider

    profile = await BusinessProfileService.get_or_create_canonical_profile(project_id, db)

    canonical_identity = {
        "business_name": (profile.business_name if profile and profile.business_name else None) or project.name,
        "city": (profile.city if profile and profile.city else "") or "",
        "state": (profile.state if profile and profile.state else "") or "",
        "phone": (profile.primary_phone if profile and profile.primary_phone else "") or "",
        "address": (profile.primary_address if profile and profile.primary_address else "") or "",
        "country": (profile.country if profile and profile.country else "") or (project.country if project and project.country else "") or "",
        "website": (profile.website if profile and profile.website else "") or (f"https://{project.domain}" if project.domain else "")
    }

    serp_provider = await get_organization_serp_provider(db, project.organization_id)
    if not serp_provider or not getattr(serp_provider, "is_configured", True):
        raise HTTPException(
            status_code=400,
            detail="SERP search provider is not configured for this organization. Configure SerpApi / DataForSEO in Connections."
        )

    res = await CitationService.discover_open_web_citations(
        project_id=project_id,
        canonical_identity=canonical_identity,
        serp_provider=serp_provider,
        db=db
    )

    return {
        "message": f"Open-web citation discovery complete. Scanned {res['candidates_found']} candidate listings, indexed {res['verified_citations']} verified/observed citations.",
        "project_id": project_id,
        "details": res
    }


@router.get("/citations/{citation_id}/detail")
async def get_citation_detail(
    citation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns full citation detail with complete forensic evidence, field comparisons, and page extraction metadata.
    """
    res = await db.execute(select(Citation).where(Citation.id == citation_id))
    cit = res.scalars().first()
    if not cit:
        raise HTTPException(status_code=404, detail="Citation not found")
    await verify_project_access(cit.project_id, current_user, db)

    from app.services.local_seo.business_profile_service import BusinessProfileService
    profile = await BusinessProfileService.get_or_create_canonical_profile(cit.project_id, db)

    return {
        "citation": cit,
        "canonical_profile": {
            "business_name": profile.business_name if profile else None,
            "primary_phone": profile.primary_phone if profile else None,
            "primary_address": profile.primary_address if profile else None,
            "city": profile.city if profile else None,
            "state": profile.state if profile else None,
            "country": profile.country if profile else None,
            "website": profile.website if profile else None
        }
    }


@router.post("/citations", response_model=CitationOut)
async def add_citation(
    cit_in: CitationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Adds a new user-provided directory citation to the project without synthetic defaults.
    """
    await verify_project_access(cit_in.project_id, current_user, db)
    src_name = cit_in.source_name or cit_in.directory_name or "Directory Listing"
    dom = cit_in.domain
    if not dom and cit_in.listing_url:
        import urllib.parse
        parsed = urllib.parse.urlparse(cit_in.listing_url)
        dom = parsed.netloc or cit_in.listing_url
    dom = dom or f"{src_name.lower().replace(' ', '')}.com"

    cit = Citation(
        project_id=cit_in.project_id,
        source_name=src_name,
        domain=dom,
        listing_url=cit_in.listing_url,
        domain_authority=cit_in.domain_authority,
        category=cit_in.category or "General Directory",
        status=cit_in.status or "submitted",
        nap_status=cit_in.nap_status or "not_checked",
        citation_type=cit_in.citation_type or "USER_PROVIDED",
        verification_status=cit_in.verification_status or "NOT_VERIFIED",
        confidence=cit_in.confidence,
        evidence=cit_in.evidence or {},
        source_type="manual",
        last_checked_at=datetime.now(timezone.utc)
    )
    db.add(cit)
    await db.commit()
    await db.refresh(cit)
    return cit


@router.post("/citations/{citation_id}/retry", response_model=CitationOut)
async def retry_citation_submission(
    citation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retries directory submission and updates verification status.
    """
    res = await db.execute(select(Citation).where(Citation.id == citation_id))
    cit = res.scalars().first()
    if not cit:
        raise HTTPException(status_code=404, detail="Citation not found")

    await verify_project_access(cit.project_id, current_user, db)

    cit.status = "submitted"
    cit.verification_status = "PENDING"
    cit.last_checked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(cit)
    return cit


@router.post("/citations/{citation_id}/status", response_model=CitationOut)
async def update_citation_status(
    citation_id: int,
    status_update: CitationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates the submission or verification status of a directory listing.
    """
    res = await db.execute(select(Citation).where(Citation.id == citation_id))
    cit = res.scalars().first()
    if not cit:
        raise HTTPException(status_code=404, detail="Citation not found")

    await verify_project_access(cit.project_id, current_user, db)

    cit.status = status_update.status
    if status_update.nap_status:
        cit.nap_status = status_update.nap_status
    if status_update.listing_url:
        cit.listing_url = status_update.listing_url
    cit.last_checked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(cit)
    return cit


@router.delete("/citations/{citation_id}")
async def delete_citation(
    citation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Deletes a directory citation record.
    """
    res = await db.execute(select(Citation).where(Citation.id == citation_id))
    cit = res.scalars().first()
    if not cit:
        raise HTTPException(status_code=404, detail="Citation not found")

    await verify_project_access(cit.project_id, current_user, db)

    await db.delete(cit)
    await db.commit()
    return {"message": "Citation removed successfully", "id": citation_id}


@router.post("/citations/{project_id}/distribute-all", response_model=CitationDistributionOut)
async def distribute_all_citations(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Scans and verifies all citations for the project and updates the citation distribution.
    """
    await verify_project_access(project_id, current_user, db)

    from app.services.local_seo.business_profile_service import BusinessProfileService
    from app.services.local_seo.citation_service import CitationService
    from app.services.serp.factory import get_organization_serp_provider

    proj_res = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_res.scalars().first()

    profile = await BusinessProfileService.get_or_create_canonical_profile(project_id, db)
    canonical_identity = {
        "business_name": (profile.business_name if profile and profile.business_name else None) or (project.name if project else ""),
        "city": (profile.city if profile and profile.city else "") or "",
        "state": (profile.state if profile and profile.state else "") or "",
        "phone": (profile.primary_phone if profile and profile.primary_phone else "") or "",
        "address": (profile.primary_address if profile and profile.primary_address else "") or "",
        "country": (profile.country if profile and profile.country else "") or (project.country if project and project.country else "") or "",
        "website": (profile.website if profile and profile.website else "") or (f"https://{project.domain}" if project and project.domain else "")
    }

    if project:
        serp_provider = await get_organization_serp_provider(db, project.organization_id)
        if serp_provider and getattr(serp_provider, "is_configured", True):
            try:
                await CitationService.discover_open_web_citations(
                    project_id=project_id,
                    canonical_identity=canonical_identity,
                    serp_provider=serp_provider,
                    db=db
                )
            except Exception as e:
                logger.warning(f"Citation re-scan notice: {e}")

    return await get_citation_distribution(project_id=project_id, current_user=current_user, db=db)


# NAP Consistency
@router.get("/nap/{project_id}", response_model=Optional[NAPRecordOut])
async def get_nap_record(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(project_id, current_user, db)
    result = await db.execute(
        select(NAPRecord).where(NAPRecord.project_id == project_id).order_by(NAPRecord.id.desc())
    )
    return result.scalars().first()

@router.get("/nap/comparison/{project_id}")
async def get_nap_comparison(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Detailed NAP comparison engine:
    Compares the Canonical Business Profile against observed directory citations
    and GBP data without false consistency.
    """
    await verify_project_access(project_id, current_user, db)
    from app.services.local_seo.nap_service import NAPComparisonService
    return await NAPComparisonService.compare_project_nap(project_id, db)

# Competitors
# ─── Competitor Intelligence & Benchmarking ───

@router.get("/competitors/{project_id}", response_model=List[CompetitorOut])
async def list_competitors(
    project_id: int,
    source: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(project_id, current_user, db)
    query = select(Competitor).where(Competitor.project_id == project_id)

    if source and source.lower() != "all":
        s = source.lower()
        if s == "manual":
            query = query.where(Competitor.source.in_(["manual", "manual_and_geogrid"]))
        elif s == "geogrid":
            query = query.where(Competitor.source.in_(["geogrid", "manual_and_geogrid"]))
        else:
            query = query.where(Competitor.source == s)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            (Competitor.name.ilike(term)) | (Competitor.domain.ilike(term))
        )

    result = await db.execute(query.order_by(Competitor.id.desc()))
    return result.scalars().all()


@router.post("/competitors", response_model=CompetitorOut)
async def add_competitor(
    comp_in: CompetitorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await verify_project_access(comp_in.project_id, current_user, db)

    clean_domain = comp_in.domain.replace("https://", "").replace("http://", "").rstrip("/") if comp_in.domain else (
        comp_in.website.replace("https://", "").replace("http://", "").rstrip("/") if comp_in.website else f"{comp_in.name.lower().replace(' ', '')}.com"
    )
    clean_domain = DomainMatcher.normalize_host(clean_domain) or clean_domain

    # Check for existing competitor for deduplication
    existing_stmt = select(Competitor).where(Competitor.project_id == comp_in.project_id)
    existing_res = await db.execute(existing_stmt)
    existing_comps = existing_res.scalars().all()

    matched: Optional[Competitor] = None
    if comp_in.place_id:
        matched = next((c for c in existing_comps if c.place_id == comp_in.place_id), None)
    if not matched and clean_domain:
        matched = next((c for c in existing_comps if DomainMatcher.normalize_host(c.domain) == clean_domain), None)
    if not matched:
        matched = next((c for c in existing_comps if c.name.strip().lower() == comp_in.name.strip().lower()), None)

    now_utc = datetime.now(timezone.utc)
    if matched:
        # Reconcile existing competitor
        curr_src = matched.source or "manual"
        if curr_src == "geogrid":
            matched.source = "manual_and_geogrid"
        elif curr_src not in ("geogrid", "manual_and_geogrid"):
            matched.source = "manual"

        if comp_in.place_id and not matched.place_id:
            matched.place_id = comp_in.place_id
        if comp_in.rating is not None:
            matched.rating = comp_in.rating
        if comp_in.reviews_count is not None and comp_in.reviews_count > (matched.reviews_count or 0):
            matched.reviews_count = comp_in.reviews_count
        if comp_in.address and not getattr(matched, "address", None):
            matched.address = comp_in.address
        if comp_in.phone and not getattr(matched, "phone", None):
            matched.phone = comp_in.phone
        if comp_in.website and not getattr(matched, "website", None):
            matched.website = comp_in.website
        matched.last_seen_at = now_utc

        await db.commit()
        await db.refresh(matched)
        return matched

    # New competitor
    comp = Competitor(
        project_id=comp_in.project_id,
        name=comp_in.name,
        domain=clean_domain,
        website=comp_in.website or clean_domain,
        gbp_name=comp_in.gbp_name,
        place_id=comp_in.place_id,
        address=comp_in.address,
        phone=comp_in.phone,
        rating=comp_in.rating,
        reviews_count=comp_in.reviews_count or 0,
        source=comp_in.source or "manual",
        local_visibility_score=0,
        top_keywords_count=0,
        last_seen_at=now_utc,
        created_at=now_utc
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@router.post("/competitors/search", response_model=CompetitorSearchResponse)
async def search_competitors(
    payload: CompetitorSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Discovers local competitor candidates using SERP API organic & local pack searches.
    """
    project = await verify_project_access(payload.project_id, current_user, db)

    # 1. Fetch location & organization SERP provider
    loc_res = await db.execute(select(Location).where(Location.project_id == project.id))
    loc = loc_res.scalars().first()

    provider = await get_organization_serp_provider(db, project.organization_id)

    # Build query term
    query_term = payload.query.strip() if payload.query and payload.query.strip() else (
        f"{project.primary_category}" if project.primary_category else f"{project.name} competitors"
    )

    req_city = payload.location or (loc.city if loc else None)
    req_state = loc.state if loc else None
    req_country = payload.country or (loc.country if loc else None)

    loc_str = None
    if req_city:
        loc_str = f"{req_city}, {req_state}" if req_state else req_city
        if req_country:
            loc_str += f", {req_country}"

    # Fetch existing competitors to mark already-tracked items
    existing_comps_res = await db.execute(select(Competitor).where(Competitor.project_id == project.id))
    existing_comps = existing_comps_res.scalars().all()
    existing_domains = {DomainMatcher.normalize_host(c.domain) for c in existing_comps if c.domain}
    existing_names = {c.name.strip().lower() for c in existing_comps if c.name}
    existing_place_ids = {c.place_id for c in existing_comps if c.place_id}

    target_domain = DomainMatcher.normalize_host(project.domain)
    target_name = project.name.strip().lower()

    # Search via SERP provider
    serp_resp = await provider.search_organic(
        keyword=query_term,
        location=loc_str,
        country=req_country or (project.country if project and project.country else "INDIA"),
        num_results=20
    )

    candidates: List[CompetitorCandidateOut] = []
    seen_keys = set()

    # 1. Local Pack results
    for pos, item in enumerate(serp_resp.local_pack_results, 1):
        item_domain = DomainMatcher.normalize_host(item.link) if item.link else ""
        item_title = (item.title or "").strip()
        if not item_title:
            continue

        if target_domain and item_domain == target_domain:
            continue
        if target_name and item_title.lower() == target_name:
            continue

        cand_key = item.place_id or item_domain or item_title.lower()
        if cand_key in seen_keys:
            continue
        seen_keys.add(cand_key)

        is_tracked = bool(
            (item.place_id and item.place_id in existing_place_ids) or
            (item_domain and item_domain in existing_domains) or
            (item_title.lower() in existing_names)
        )

        candidates.append(CompetitorCandidateOut(
            title=item_title,
            domain=item.domain or item_domain or None,
            rating=item.rating,
            reviews_count=item.reviews_count,
            address=item.address,
            phone=item.phone,
            place_id=item.place_id,
            source="local_pack",
            position=item.position or pos,
            category=item.category if hasattr(item, "category") else None,
            is_already_tracked=is_tracked
        ))

    # 2. Organic results
    for pos, item in enumerate(serp_resp.organic_results, 1):
        item_domain = DomainMatcher.normalize_host(item.link) if item.link else ""
        item_title = (item.title or item_domain or "").strip()
        if not item_domain or not item_title:
            continue

        if item_domain in ("google.com", "facebook.com", "yelp.com", "yellowpages.com", "linkedin.com", "instagram.com", "wikipedia.org"):
            continue
        if target_domain and item_domain == target_domain:
            continue
        if target_name and item_title.lower() == target_name:
            continue

        if item_domain in seen_keys or item_title.lower() in seen_keys:
            continue
        seen_keys.add(item_domain)

        is_tracked = bool(
            (item_domain in existing_domains) or (item_title.lower() in existing_names)
        )

        candidates.append(CompetitorCandidateOut(
            title=item_title,
            domain=item_domain,
            rating=None,
            reviews_count=None,
            address=None,
            phone=None,
            place_id=None,
            source="organic",
            position=item.position or pos,
            is_already_tracked=is_tracked
        ))

    return CompetitorSearchResponse(
        query=query_term,
        location=loc_str,
        total_found=len(candidates),
        results=candidates
    )


@router.get("/competitors/{project_id}/export/csv")
async def export_competitors_csv(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await verify_project_access(project_id, current_user, db)

    result = await db.execute(
        select(Competitor).where(Competitor.project_id == project_id).order_by(Competitor.id.desc())
    )
    competitors = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        "Business Name",
        "Website / Domain",
        "Category",
        "Source",
        "Google Rating",
        "Review Count",
        "Average Maps Rank",
        "Best Rank",
        "Worst Rank",
        "Grid Appearances",
        "Keywords Found",
        "First Seen",
        "Last Seen"
    ])

    for comp in competitors:
        src = getattr(comp, "source", "manual")
        if src == "manual_and_geogrid":
            src_str = "Manual + Geo-Grid"
        elif src == "geogrid":
            src_str = "Geo-Grid"
        else:
            src_str = "Manual"

        kws = getattr(comp, "keywords_found", []) or []
        kws_str = ", ".join(kws) if isinstance(kws, list) else str(kws)

        writer.writerow([
            comp.name or "",
            comp.domain or getattr(comp, "website", "") or "",
            comp.category if hasattr(comp, "category") and comp.category else (comp.categories[0] if comp.categories else ""),
            src_str,
            str(comp.rating) if comp.rating is not None else "",
            str(comp.reviews_count or 0),
            f"{comp.avg_maps_rank:.1f}" if comp.avg_maps_rank is not None else "",
            str(comp.best_rank) if getattr(comp, "best_rank", None) is not None else "",
            str(comp.worst_rank) if getattr(comp, "worst_rank", None) is not None else "",
            str(getattr(comp, "grid_appearances", 0) or 0),
            kws_str,
            comp.created_at.strftime("%Y-%m-%d %H:%M:%S") if comp.created_at else "",
            comp.last_seen_at.strftime("%Y-%m-%d %H:%M:%S") if getattr(comp, "last_seen_at", None) else ""
        ])

    csv_data = output.getvalue()
    filename = f"competitors_project_{project_id}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )


@router.get("/competitors/{project_id}/export/pdf")
async def export_competitors_pdf(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await verify_project_access(project_id, current_user, db)

    # Fetch competitors
    comp_res = await db.execute(
        select(Competitor).where(Competitor.project_id == project_id).order_by(Competitor.id.desc())
    )
    competitors = comp_res.scalars().all()

    # Location info
    loc_res = await db.execute(select(Location).where(Location.project_id == project_id))
    loc = loc_res.scalars().first()
    loc_str = f"{loc.city}, {loc.state}" if loc and loc.city and loc.state else (loc.city if loc and loc.city else "Business Location")

    pdf_bytes = CompetitorPDFService.generate_report(
        project=project,
        competitors=competitors,
        location_str=loc_str
    )

    filename = f"competitor_benchmarking_{project_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )


@router.delete("/competitors/{competitor_id}")
async def delete_competitor(
    competitor_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Competitor).where(Competitor.id == competitor_id))
    comp = result.scalars().first()
    if not comp:
        raise HTTPException(status_code=404, detail="Competitor not found")

    await verify_project_access(comp.project_id, current_user, db)
    await db.delete(comp)
    await db.commit()
    return {"message": "Competitor deleted successfully"}


# -----------------------------------------------------------------------------
# Schema Intelligence, Generator & Validator Endpoints
# -----------------------------------------------------------------------------
@router.get("/schema/vocabulary")
async def get_schema_vocabulary(current_user: User = Depends(get_current_user)):
    """
    Returns the complete Schema.org v28.0 vocabulary registry, category index,
    and recommended quick presets for universal schema generation.
    """
    return {
        "version": "Schema.org v28.0",
        "categories": SCHEMA_CATEGORIES,
        "types": SchemaVocabulary.get_all_types(),
        "presets": [
            {"name": "LocalBusiness", "category": "Local Business & Places", "description": "Physical local business or store"},
            {"name": "Electrician", "category": "Local Business & Places", "description": "Electrical contractor / service"},
            {"name": "Plumber", "category": "Local Business & Places", "description": "Plumbing contractor / service"},
            {"name": "HVACBusiness", "category": "Local Business & Places", "description": "Heating & Air Conditioning service"},
            {"name": "Dentist", "category": "Local Business & Places", "description": "Dental clinic or practitioner"},
            {"name": "Restaurant", "category": "Local Business & Places", "description": "Food establishment / restaurant"},
            {"name": "RealEstateAgent", "category": "Local Business & Places", "description": "Real estate brokerage or agent"},
            {"name": "Organization", "category": "Organizations & Brands", "description": "Umbrella corporate organization or brand"},
            {"name": "WebSite", "category": "Web Structure & Navigation", "description": "Top-level site with search action"},
            {"name": "WebPage", "category": "Web Structure & Navigation", "description": "Individual crawled web page"},
            {"name": "FAQPage", "category": "Web Structure & Navigation", "description": "Frequently Asked Questions page"},
            {"name": "Product", "category": "Products, Offers & Commerce", "description": "Retail or wholesale item for sale"},
            {"name": "Service", "category": "Products, Offers & Commerce", "description": "Commercial service offering"},
            {"name": "Article", "category": "Content, Media & Creative Works", "description": "Editorial or informational article"},
            {"name": "BlogPosting", "category": "Content, Media & Creative Works", "description": "Blog post or content entry"},
            {"name": "Person", "category": "People, Events & Roles", "description": "Individual professional, author, or founder"},
            {"name": "JobPosting", "category": "People, Events & Roles", "description": "Career opening or job vacancy"},
            {"name": "Event", "category": "People, Events & Roles", "description": "Scheduled event or gathering"},
            {"name": "Recipe", "category": "Content, Media & Creative Works", "description": "Food recipe with ingredients and steps"},
            {"name": "HowTo", "category": "Content, Media & Creative Works", "description": "Step-by-step instructions or tutorial"},
            {"name": "SoftwareApplication", "category": "Content, Media & Creative Works", "description": "Software, web app, or mobile app"}
        ]
    }

@router.get("/schema/vocabulary/type/{type_name}")
async def get_schema_type_definition(type_name: str, current_user: User = Depends(get_current_user)):
    """
    Returns the schema type definition with all inherited properties,
    data types, descriptions, and Google Rich Result specifications.
    """
    type_def = SchemaVocabulary.get_type_definition(type_name)
    if not type_def:
        raise HTTPException(status_code=404, detail=f"Schema.org type '{type_name}' not found in vocabulary registry.")
    return type_def

@router.get("/schema/{project_id}", response_model=List[SchemaRecordOut])
async def list_schemas(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(project_id, current_user, db)
    result = await db.execute(select(SchemaRecord).where(SchemaRecord.project_id == project_id))
    return result.scalars().all()

@router.get("/schema/{project_id}/intelligence", response_model=SchemaIntelligenceSummaryOut)
async def get_schema_intelligence_summary(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    proj = await verify_project_access(project_id, current_user, db)

    records_res = await db.execute(select(SchemaRecord).where(SchemaRecord.project_id == project_id))
    records = records_res.scalars().all()

    page_analyses = []
    all_detected_types = set()
    total_valid = 0
    total_warnings = 0
    total_errors = 0
    total_missing_opportunities = 0

    for rec in records:
        det = rec.detected_types or []
        for d in det:
            all_detected_types.add(d)
        if rec.is_valid:
            total_valid += 1
        total_warnings += len(rec.warnings or [])
        total_errors += len(rec.errors or [])
        total_missing_opportunities += len(rec.missing_properties or [])

        page_analyses.append({
            "url": rec.page_url,
            "page_type": rec.page_type,
            "business_type": rec.business_type,
            "detected_types": det,
            "errors": rec.errors or [],
            "warnings": rec.warnings or [],
            "nap_status": rec.nap_status
        })

    # Determine Project Context (Prioritize bound GBP if connected, else fallback to project location/data)
    from app.models.gbp import GoogleBusinessProfile
    gbp_res = await db.execute(select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id))
    gbp = gbp_res.scalars().first()

    loc_res = await db.execute(select(Location).where(Location.project_id == project_id))
    loc = loc_res.scalars().first()

    if gbp and (gbp.business_name or gbp.phone or gbp.address):
        project_context = {
            "canonical_source": "GOOGLE_BUSINESS_PROFILE",
            "name": gbp.business_name or proj.name,
            "domain": proj.domain,
            "phone": gbp.phone or (loc.phone if loc else None),
            "address": gbp.address or (loc.address if loc else None),
            "city": gbp.city or (loc.city if loc else None),
            "state": gbp.state or (loc.state if loc else None),
            "postal_code": gbp.postal_code or (loc.postal_code if loc else None),
            "country": gbp.country or (loc.country if loc else None),
            "latitude": gbp.latitude if gbp.latitude is not None else (loc.latitude if loc else None),
            "longitude": gbp.longitude if gbp.longitude is not None else (loc.longitude if loc else None),
            "primary_category": gbp.primary_category or proj.primary_category
        }
    else:
        project_context = {
            "canonical_source": "PROJECT_USER_INPUT",
            "name": proj.name,
            "domain": proj.domain,
            "phone": loc.phone if loc else None,
            "address": loc.address if loc else None,
            "city": loc.city if loc else None,
            "state": loc.state if loc else None,
            "postal_code": loc.postal_code if loc else None,
            "country": loc.country if loc else None,
            "latitude": loc.latitude if loc else None,
            "longitude": loc.longitude if loc else None,
            "primary_category": proj.primary_category
        }

    score_result = SchemaIntelligenceEngine.calculate_quality_score(page_analyses)
    recommendations = SchemaIntelligenceEngine.generate_recommendations(page_analyses, project_context)

    # Calculate Dynamic Site-Wide Applicability and Tier 1 Schema Matrix Status
    industry_type = proj.primary_category or "LocalBusiness"
    
    # Detect site-wide signals from crawled records
    has_faq_site = any(
        (r.page_type == "FAQ") or ("faq" in (r.page_url or "").lower()) or ("FAQPage" in (r.detected_types or []))
        for r in records
    )
    has_reviews_site = any(
        (r.page_type == "Review/Testimonial") or ("AggregateRating" in (r.detected_types or [])) or ("Review" in (r.detected_types or []))
        for r in records
    )
    has_product_site = any(
        (r.page_type in ["Product", "Pricing"]) or ("Product" in (r.detected_types or []))
        for r in records
    )
    has_events_site = any(
        (r.page_type == "Event") or ("Event" in (r.detected_types or []))
        for r in records
    )
    has_jobs_site = any(
        (r.page_type == "Career/Job") or ("JobPosting" in (r.detected_types or []))
        for r in records
    )
    has_services = any(
        (r.page_type in ["Service", "Service Location", "Homepage"]) or ("Service" in (r.detected_types or []))
        for r in records
    )

    from app.services.schema_intelligence import SCHEMA_METADATA

    tier_1_status = {}
    for s_name in TIER_1_SCHEMAS:
        meta = SCHEMA_METADATA.get(s_name, {})
        
        # Determine dynamic applicability
        if s_name in ["WebSite", "WebPage", "Organization"]:
            app_level = "Highly Applicable"
            reason = meta.get("why_it_matters", "Core foundation schema for machine-readable identity.")
        elif s_name == "LocalBusiness":
            app_level = "Highly Applicable" if industry_type in INDUSTRY_SCHEMAS or industry_type == "LocalBusiness" else "Potentially Applicable"
            reason = f"Essential for local visibility and Google Maps indexation for {industry_type}."
        elif s_name == "BreadcrumbList":
            app_level = "Highly Applicable" if len(records) > 1 else "Potentially Applicable"
            reason = "Generates structured breadcrumb navigation in Google Search for subpages."
        elif s_name == "Service":
            app_level = "Highly Applicable"
            reason = f"Highlights primary commercial service offerings for {industry_type}."
        elif s_name == "Product":
            app_level = "Highly Applicable" if has_product_site else "Not Applicable"
            reason = "Recommended when commercial products or pricing are cataloged on site." if has_product_site else "Not applicable for non-ecommerce local service business."
        elif s_name == "FAQPage":
            app_level = "Highly Applicable" if has_faq_site else "Not Applicable"
            reason = "Unlocks rich question/answer accordions in search results." if has_faq_site else "No dedicated FAQ or Q&A sections detected on crawled pages."
        elif s_name == "AggregateRating":
            app_level = "Applicable" if has_reviews_site else "Not Applicable"
            reason = "Enables gold star ratings in search snippets when customer reviews are published." if has_reviews_site else "No on-site customer reviews detected."
        elif s_name == "Review":
            app_level = "Applicable" if has_reviews_site else "Not Applicable"
            reason = "Enables rich review author and testimonial markup." if has_reviews_site else "No individual review quotations detected on site."
        elif s_name == "Offer":
            app_level = "Applicable" if (has_product_site or has_services) else "Potentially Applicable"
            reason = "Specifies pricing terms and quotation availability for services and products."
        elif s_name in ["Article", "BlogPosting"]:
            has_blog = any(r.page_type == "Blog Article" or "/blog" in (r.page_url or "").lower() for r in records)
            app_level = "Highly Applicable" if has_blog else "Not Applicable"
            reason = "Recommended for educational articles and company blog posts." if has_blog else "No editorial blog articles detected on site."
        elif s_name == "Person":
            has_about = any(r.page_type in ["About", "Team/Profile"] for r in records)
            app_level = "Applicable" if has_about else "Potentially Applicable"
            reason = "Establishes Google E-E-A-T credentials for key practitioners and founders."
        elif s_name == "Event":
            app_level = "Highly Applicable" if has_events_site else "Not Applicable"
            reason = "Enables interactive Google Event cards for upcoming scheduled events." if has_events_site else "No scheduled events or workshops detected on site."
        elif s_name == "JobPosting":
            app_level = "Highly Applicable" if has_jobs_site else "Not Applicable"
            reason = "Feeds Google for Jobs index for active employment openings." if has_jobs_site else "No careers or job vacancy pages detected on site."
        elif s_name == "ImageObject":
            app_level = "Applicable"
            reason = "Powers Google Images rich previews and visual search presence."
        elif s_name == "VideoObject":
            has_video = any("VideoObject" in (r.detected_types or []) for r in records)
            app_level = "Applicable" if has_video else "Not Applicable"
            reason = "Generates video rich results with duration and thumbnail." if has_video else "No embedded video elements detected on crawled pages."
        else:
            app_level = "Potentially Applicable"
            reason = meta.get("why_it_matters", "General Schema.org structured data entity.")

        # Check detection across all crawled page records
        matching_entities = []
        for r in records:
            ents = r.schema_entities or []
            if not ents and r.raw_json_ld:
                try:
                    parsed_raw = json.loads(r.raw_json_ld)
                    temp_ents = []
                    SchemaIntelligenceEngine._flatten_entities(parsed_raw, temp_ents, source="JSON-LD", raw_script=r.raw_json_ld)
                    ents = temp_ents
                except Exception:
                    pass

            for ent in ents:
                ent_type = ent.get("@type")
                is_match = False
                if ent_type == s_name:
                    is_match = True
                elif isinstance(ent_type, list) and s_name in ent_type:
                    is_match = True
                elif s_name == "LocalBusiness" and isinstance(ent_type, str) and (ent_type in INDUSTRY_SCHEMAS or "Business" in ent_type or "Store" in ent_type or "Restaurant" in ent_type or "Clinic" in ent_type):
                    is_match = True

                if is_match:
                    raw_obj = ent.get("raw") or ent.get("properties") or {}
                    clean_props = {k: v for k, v in raw_obj.items() if k not in ["@context"]}
                    
                    val_res = SchemaIntelligenceEngine.validate_entity(
                        {"@type": s_name, "raw": raw_obj},
                        project_context=project_context
                    )

                    raw_snippet = ent.get("raw_script")
                    if not raw_snippet and raw_obj:
                        raw_snippet = json.dumps(raw_obj, indent=2)
                    elif not raw_snippet:
                        raw_snippet = r.raw_json_ld or f'{{\n  "@context": "https://schema.org",\n  "@type": "{s_name}"\n}}'

                    matching_entities.append({
                        "instance_id": f"{r.id}_{len(matching_entities)+1}",
                        "name": ent.get("name") or raw_obj.get("name") or raw_obj.get("headline") or f"{s_name} (#{len(matching_entities)+1})",
                        "page_url": r.page_url,
                        "source_format": ent.get("source", "JSON-LD"),
                        "properties": clean_props if clean_props else {"@type": s_name},
                        "raw_entity": raw_obj if raw_obj else {"@type": s_name},
                        "raw_markup": raw_snippet,
                        "validation_errors": val_res.get("errors", []),
                        "validation_warnings": val_res.get("warnings", []),
                        "missing_properties": val_res.get("missing_properties", []),
                        "scanned_at": r.last_validated_at.isoformat() if r.last_validated_at else None
                    })

        detected_data = None
        if matching_entities:
            primary = matching_entities[0]
            has_err = any(len(m["validation_errors"]) > 0 for m in matching_entities)
            status_val = "Invalid" if has_err else "Detected"

            detected_data = {
                "page_url": primary["page_url"],
                "source_format": primary["source_format"],
                "properties": primary["properties"],
                "raw_entity": primary["raw_entity"],
                "raw_markup": primary["raw_markup"],
                "all_instances": matching_entities,
                "validation_errors": primary["validation_errors"],
                "validation_warnings": primary["validation_warnings"],
                "missing_properties": primary["missing_properties"],
                "scanned_at": primary["scanned_at"]
            }
        else:
            if len(records) == 0:
                status_val = "Not Scanned"
            elif app_level == "Not Applicable":
                status_val = "Not Applicable"
            elif app_level in ["Highly Applicable", "Applicable"]:
                status_val = "Missing"
            else:
                status_val = "Not Applicable"

        # Generator prefill for this entity type
        generator_prefill = {
            "schema_type": s_name if s_name in ["LocalBusiness", "Organization", "Service", "Product", "FAQPage", "Article", "Event", "JobPosting"] else ("LocalBusiness" if s_name in ["WebSite", "WebPage", "BreadcrumbList"] else s_name),
            "business_name": project_context.get("name") or proj.name,
            "url": f"https://{proj.domain}" if proj.domain else "",
            "phone": project_context.get("phone") or "",
            "street": project_context.get("address") or "",
            "city": project_context.get("city") or "",
            "state": project_context.get("state") or "",
            "postal_code": project_context.get("postal_code") or "",
            "country": project_context.get("country") or "",
            "latitude": str(project_context.get("latitude") or "") if project_context.get("latitude") is not None else "",
            "longitude": str(project_context.get("longitude") or "") if project_context.get("longitude") is not None else "",
            "service_name": f"{industry_type} Service" if s_name == "Service" else "",
            "service_description": f"Professional {industry_type} services in {project_context.get('city') or 'local area'}." if s_name == "Service" else ""
        }

        tier_1_status[s_name] = {
            "status": status_val,
            "applicability": app_level,
            "reason": reason,
            "definition": meta.get("definition", f"Schema.org entity for {s_name}."),
            "why_it_matters": meta.get("why_it_matters", "Improves machine-readability and rich snippet eligibility."),
            "recommended_page_types": meta.get("recommended_page_types", ["Homepage"]),
            "required_properties": meta.get("required_properties", ["@type", "name"]),
            "recommended_properties": meta.get("recommended_properties", ["description", "url"]),
            "detected_data": detected_data,
            "generator_prefill": generator_prefill
        }

    return {
        "project_id": project_id,
        "domain": proj.domain,
        "health_score": score_result["health_score"],
        "score_breakdown": score_result["breakdown"],
        "deductions": score_result["deductions"],
        "stats": {
            "pages_crawled": len(records),
            "schemas_detected": len(all_detected_types),
            "valid_count": total_valid,
            "warnings_count": total_warnings,
            "errors_count": total_errors,
            "missing_opportunities": total_missing_opportunities
        },
        "tier_1_status": tier_1_status,
        "industry_type": industry_type,
        "records": records,
        "recommendations": recommendations
    }

@router.post("/schema/generate")
async def generate_local_schema(
    req: SchemaGenerateRequest,
    current_user: User = Depends(get_current_user)
):
    # If custom properties or connected entities are provided, use universal generator
    if req.custom_properties is not None or req.connected_entities is not None:
        props = dict(req.custom_properties or {})
        if req.business_name and "name" not in props:
            props["name"] = req.business_name
        if req.url and "url" not in props:
            props["url"] = req.url
        if req.phone and "telephone" not in props:
            props["telephone"] = req.phone
        if (req.street_address or req.city) and "address" not in props:
            props["address"] = {
                "@type": "PostalAddress",
                "streetAddress": req.street_address,
                "addressLocality": req.city,
                "addressRegion": req.state,
                "postalCode": req.postal_code,
                "addressCountry": req.country or None
            }
        if (req.latitude is not None or req.longitude is not None) and "geo" not in props:
            props["geo"] = {
                "@type": "GeoCoordinates",
                "latitude": req.latitude,
                "longitude": req.longitude
            }
        if req.price_range and "priceRange" not in props:
            props["priceRange"] = req.price_range
            
        result = SchemaVocabulary.generate_universal_schema(
            main_type=req.business_type or "LocalBusiness",
            properties=props,
            connected_entities=req.connected_entities,
            include_graph=req.include_graph if req.include_graph is not None else True,
            base_url=req.url
        )
        return result

    result = SchemaIntelligenceEngine.generate_safe_schema(
        business_type=req.business_type,
        business_name=req.business_name or "",
        url=req.url or "",
        phone=req.phone,
        street_address=req.street_address,
        city=req.city,
        state=req.state,
        postal_code=req.postal_code,
        country=req.country,
        latitude=req.latitude,
        longitude=req.longitude,
        opening_hours=req.opening_hours,
        price_range=req.price_range,
        social_profiles=req.social_profiles,
        service_name=req.service_name,
        service_description=req.service_description,
        breadcrumbs=req.breadcrumbs,
        include_graph=req.include_graph if req.include_graph is not None else True
    )
    return result

@router.post("/schema/validate", response_model=SchemaValidateResponse)
async def validate_schema_snippet(
    req: SchemaValidateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project_context = None
    if req.project_id:
        try:
            proj = await verify_project_access(req.project_id, current_user, db)
            loc_res = await db.execute(select(Location).where(Location.project_id == req.project_id))
            loc = loc_res.scalars().first()
            if loc:
                project_context = {
                    "name": proj.name,
                    "phone": loc.phone,
                    "address": loc.address,
                    "city": loc.city,
                    "state": loc.state,
                    "postal_code": loc.postal_code
                }
        except Exception:
            pass
    return SchemaVocabulary.deep_validate_json_ld(req.json_ld, project_context=project_context)

@router.post("/schema/validate-url")
async def validate_schema_from_url(
    req: SchemaValidateUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    target_url = req.url.strip() if req.url else ""
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = f"https://{target_url}"

    if not PublicGoogleMapsService.is_safe_url(target_url):
        raise HTTPException(status_code=400, detail="Provided URL is invalid or blocked by SSRF security policy.")

    project_context = None
    if req.project_id:
        try:
            proj = await verify_project_access(req.project_id, current_user, db)
            loc_res = await db.execute(select(Location).where(Location.project_id == req.project_id))
            loc = loc_res.scalars().first()
            if loc:
                project_context = {
                    "name": proj.name,
                    "phone": loc.phone,
                    "address": loc.address,
                    "city": loc.city,
                    "state": loc.state,
                    "postal_code": loc.postal_code
                }
        except Exception:
            pass

    import httpx
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers={"User-Agent": "LocalLift-SchemaValidator/2.0"}) as client:
            resp = await client.get(target_url)
            html_content = resp.text
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch content from URL: {str(e)}")

    extracted_schemas, raw_json_scripts = SchemaIntelligenceEngine.extract_json_ld_from_html(html_content, target_url)
    consolidated_json = ""
    if raw_json_scripts:
        if len(raw_json_scripts) == 1:
            consolidated_json = raw_json_scripts[0]
        else:
            consolidated_json = json.dumps({"@context": "https://schema.org", "@graph": extracted_schemas}, indent=2)
    elif extracted_schemas:
        consolidated_json = json.dumps({"@context": "https://schema.org", "@graph": extracted_schemas}, indent=2)

    val_res = SchemaVocabulary.deep_validate_json_ld(consolidated_json if consolidated_json else "{}", project_context=project_context)
    if not consolidated_json:
        val_res["warnings"].append("No Schema.org JSON-LD scripts were detected on this webpage.")

    return {
        "url": target_url,
        "extracted_count": len(extracted_schemas),
        "entities": val_res["entities"],
        "raw_json_ld": consolidated_json,
        "is_valid": val_res["is_valid"] if consolidated_json else False,
        "syntax_valid": val_res.get("syntax_valid", True),
        "errors": val_res["errors"],
        "warnings": val_res["warnings"],
        "rich_results": val_res.get("rich_results", []),
        "nap_status": val_res.get("nap_status", "Consistent")
    }

@router.post("/schema/drafts")
async def save_schema_draft(
    req: SchemaDraftSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(req.project_id, current_user, db)
    
    rec_res = await db.execute(
        select(SchemaRecord).where(
            SchemaRecord.project_id == req.project_id,
            SchemaRecord.page_url == req.page_url
        )
    )
    rec = rec_res.scalars().first()

    val_res = SchemaVocabulary.deep_validate_json_ld(req.generated_json_ld)
    
    if rec:
        rec.generated_json_ld = req.generated_json_ld
        rec.schema_type = req.schema_type
        rec.is_valid = val_res["is_valid"]
        rec.errors = val_res["errors"]
        rec.warnings = val_res["warnings"]
        rec.detected_types = val_res["entities"]
        if req.entities:
            rec.schema_entities = req.entities
        rec.last_validated_at = datetime.now(timezone.utc)
    else:
        rec = SchemaRecord(
            project_id=req.project_id,
            page_url=req.page_url,
            schema_type=req.schema_type,
            page_type="Custom",
            business_type=req.schema_type,
            is_valid=val_res["is_valid"],
            quality_score=90 if val_res["is_valid"] else 50,
            score_breakdown={"validity": 40, "completeness": 30, "syntax": 20},
            detected_types=val_res["entities"],
            applicable_schemas={},
            errors=val_res["errors"],
            warnings=val_res["warnings"],
            missing_properties=[],
            property_results=[],
            recommendations=[],
            schema_source="Generated Draft",
            schema_entities=req.entities or [{"@type": req.schema_type}],
            nap_status=val_res.get("nap_status", "Consistent"),
            raw_json_ld=None,
            generated_json_ld=req.generated_json_ld,
            last_validated_at=datetime.now(timezone.utc)
        )
        db.add(rec)

    await db.commit()
    await db.refresh(rec)
    return {
        "message": "Schema draft saved successfully",
        "record_id": rec.id,
        "page_url": rec.page_url,
        "schema_type": rec.schema_type,
        "is_valid": rec.is_valid,
        "errors": rec.errors,
        "warnings": rec.warnings
    }

@router.get("/schema/drafts/{project_id}")
async def list_schema_drafts(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(project_id, current_user, db)
    res = await db.execute(
        select(SchemaRecord).where(
            SchemaRecord.project_id == project_id,
            SchemaRecord.generated_json_ld.isnot(None)
        ).order_by(SchemaRecord.last_validated_at.desc())
    )
    drafts = res.scalars().all()
    return [
        {
            "id": d.id,
            "page_url": d.page_url,
            "schema_type": d.schema_type,
            "is_valid": d.is_valid,
            "generated_json_ld": d.generated_json_ld,
            "last_validated_at": d.last_validated_at
        }
        for d in drafts
    ]


@router.post("/schema/analyze/{project_id}", response_model=SchemaIntelligenceSummaryOut)
async def analyze_project_schemas(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    proj = await verify_project_access(project_id, current_user, db)

    from app.models.gbp import GoogleBusinessProfile
    gbp_res = await db.execute(select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id))
    gbp = gbp_res.scalars().first()

    loc_res = await db.execute(select(Location).where(Location.project_id == project_id))
    loc = loc_res.scalars().first()

    if gbp and (gbp.business_name or gbp.phone or gbp.address):
        project_context = {
            "canonical_source": "GOOGLE_BUSINESS_PROFILE",
            "name": gbp.business_name or proj.name,
            "domain": proj.domain,
            "phone": gbp.phone or (loc.phone if loc else None),
            "address": gbp.address or (loc.address if loc else None),
            "city": gbp.city or (loc.city if loc else None),
            "state": gbp.state or (loc.state if loc else None),
            "postal_code": gbp.postal_code or (loc.postal_code if loc else None),
            "country": gbp.country or (loc.country if loc else None),
            "latitude": gbp.latitude if gbp.latitude is not None else (loc.latitude if loc else None),
            "longitude": gbp.longitude if gbp.longitude is not None else (loc.longitude if loc else None),
            "primary_category": gbp.primary_category or proj.primary_category
        }
    else:
        project_context = {
            "canonical_source": "PROJECT_USER_INPUT",
            "name": proj.name,
            "domain": proj.domain,
            "phone": loc.phone if loc else None,
            "address": loc.address if loc else None,
            "city": loc.city if loc else None,
            "state": loc.state if loc else None,
            "postal_code": loc.postal_code if loc else None,
            "country": loc.country if loc else None,
            "latitude": loc.latitude if loc else None,
            "longitude": loc.longitude if loc else None,
            "primary_category": proj.primary_category
        }

    # 1. Fetch crawled pages from website or crawl live domain
    web_res = await db.execute(select(Website).where(Website.project_id == project_id))
    website = web_res.scalars().first()
    
    pages_to_process = []
    if website:
        pages_res = await db.execute(select(WebsitePage).where(WebsitePage.website_id == website.id))
        stored_pages = pages_res.scalars().all()
        if stored_pages:
            for p in stored_pages:
                s_data = p.schema_data or {}
                s_types = p.schema_types or s_data.get("schema_types", [])
                s_ld = s_data.get("json_ld_schemas", [])
                s_ents = s_data.get("schema_entities", [])
                pages_to_process.append({
                    "url": p.url,
                    "title": p.title,
                    "h1": p.h1,
                    "h2_list": p.h2_list or [],
                    "schema_types": s_types,
                    "json_ld_schemas": s_ld,
                    "schema_entities": s_ents,
                    "schema_parse_errors": s_data.get("schema_parse_errors", []),
                    "raw_json_ld": json.dumps(s_ld, indent=2) if s_ld else None
                })

    # If no stored pages yet, crawl domain or root URL directly
    if not pages_to_process and proj.domain:
        domain = proj.domain.strip()
        start_url = domain if domain.startswith(("http://", "https://")) else f"https://{domain}"
        try:
            crawler = WebsiteCrawler(start_url=start_url, max_pages=10)
            crawled_data = await crawler.crawl()
            for cp in crawled_data:
                json_schemas = cp.get("json_ld_schemas", [])
                pages_to_process.append({
                    "url": cp.get("url"),
                    "title": cp.get("title"),
                    "h1": cp.get("h1"),
                    "h2_list": cp.get("h2_list", []),
                    "schema_types": cp.get("schema_types", []),
                    "json_ld_schemas": json_schemas,
                    "schema_entities": cp.get("schema_entities", []),
                    "schema_parse_errors": cp.get("schema_parse_errors", []),
                    "raw_json_ld": json.dumps(json_schemas, indent=2) if json_schemas else None
                })
        except Exception as e:
            logger.warning("Crawler execution during schema analysis failed gracefully: %s", e)

        # If crawler returned nothing or DNS was unreachable, record the root domain page for evaluation
        if not pages_to_process:
            pages_to_process.append({
                "url": start_url,
                "title": proj.name,
                "h1": None,
                "h2_list": [],
                "schema_types": [],
                "json_ld_schemas": [],
                "schema_entities": [],
                "schema_parse_errors": [],
                "raw_json_ld": None
            })

    # 2. Existing records mapping
    rec_res = await db.execute(select(SchemaRecord).where(SchemaRecord.project_id == project_id))
    existing_records = {r.page_url: r for r in rec_res.scalars().all()}

    # 3. Process each page into SchemaRecord
    industry_type = proj.primary_category or "LocalBusiness"
    
    for page in pages_to_process:
        p_url = page.get("url")
        if not p_url:
            continue
        
        # Detect page type
        pt_res = SchemaIntelligenceEngine.detect_page_type(
            url=p_url,
            title=page.get("title"),
            h1=page.get("h1"),
            h2_list=page.get("h2_list", []),
            existing_schemas=page.get("schema_types", [])
        )
        detected_page_type = pt_res.get("page_type", "Homepage")
        
        # Evaluate applicability
        app_map = SchemaIntelligenceEngine.evaluate_applicability(
            page_type=detected_page_type,
            business_type=industry_type
        )
        
        # Validate schema entities
        detected_types = list(page.get("schema_types", []))
        json_ld_schemas = list(page.get("json_ld_schemas", []))
        schema_entities = list(page.get("schema_entities", []))
        raw_json = page.get("raw_json_ld")
        
        errors = list(page.get("schema_parse_errors", []))
        warnings = []
        missing_props = []
        nap_status = "Consistent"
        is_valid = True
        
        if json_ld_schemas:
            for s in json_ld_schemas:
                if isinstance(s, dict):
                    val_res = SchemaIntelligenceEngine.validate_entity(s, project_context=project_context)
                    if not val_res.get("is_valid", True):
                        is_valid = False
                    for err in val_res.get("errors", []):
                        if isinstance(err, dict):
                            errors.append(f"{err.get('field', 'schema')}: {err.get('message', '')}")
                        else:
                            errors.append(str(err))
                    for warn in val_res.get("warnings", []):
                        if isinstance(warn, dict):
                            warnings.append(f"{warn.get('field', 'schema')}: {warn.get('message', '')}")
                        else:
                            warnings.append(str(warn))
                    if val_res.get("nap_check", {}).get("nap_status") == "Mismatch" or val_res.get("nap_match_status") == "Mismatch":
                        nap_status = "Mismatch"
        elif raw_json:
            v_res = SchemaIntelligenceEngine.validate_json_ld_string(raw_json)
            is_valid = v_res.get("is_valid", True)
            errors.extend(v_res.get("errors", []))
            warnings.extend(v_res.get("warnings", []))
        
        # Determine missing opportunities based on applicability
        for s_name, s_info in app_map.items():
            if s_info.get("applicability") in ["Highly Applicable", "Applicable"] and s_name not in detected_types:
                missing_props.append(f"Missing recommended {s_name} schema for {detected_page_type} page")

        # Page quality score
        page_analysis = {
            "url": p_url,
            "page_type": detected_page_type,
            "business_type": industry_type,
            "detected_types": detected_types,
            "errors": errors,
            "warnings": warnings,
            "nap_status": nap_status
        }
        score_res = SchemaIntelligenceEngine.calculate_quality_score([page_analysis])
        
        rec = existing_records.get(p_url)
        if rec:
            rec.page_type = detected_page_type
            rec.business_type = industry_type
            rec.detected_types = detected_types
            rec.applicable_schemas = app_map
            rec.errors = errors
            rec.warnings = warnings
            rec.missing_properties = missing_props
            rec.schema_entities = schema_entities
            rec.is_valid = is_valid and (len(errors) == 0)
            rec.quality_score = score_res["health_score"]
            rec.score_breakdown = score_res["breakdown"]
            rec.nap_status = nap_status
            if raw_json:
                rec.raw_json_ld = raw_json
            rec.last_validated_at = datetime.now(timezone.utc)
        else:
            new_rec = SchemaRecord(
                project_id=project_id,
                page_url=p_url,
                schema_type=detected_types[0] if detected_types else "LocalBusiness",
                page_type=detected_page_type,
                business_type=industry_type,
                is_valid=is_valid and (len(errors) == 0),
                quality_score=score_res["health_score"],
                score_breakdown=score_res["breakdown"],
                detected_types=detected_types,
                applicable_schemas=app_map,
                errors=errors,
                warnings=warnings,
                missing_properties=missing_props,
                schema_source="JSON-LD" if json_ld_schemas else "None",
                schema_entities=schema_entities,
                nap_status=nap_status,
                raw_json_ld=raw_json,
                last_validated_at=datetime.now(timezone.utc)
            )
            db.add(new_rec)

    # Re-validate any remaining existing records
    for r_url, rec in existing_records.items():
        if r_url not in [p.get("url") for p in pages_to_process]:
            rec.last_validated_at = datetime.now(timezone.utc)
            if rec.raw_json_ld:
                val_res = SchemaIntelligenceEngine.validate_json_ld_string(rec.raw_json_ld)
                rec.is_valid = val_res["is_valid"]
                rec.errors = val_res["errors"]
                rec.warnings = val_res["warnings"]

    await db.commit()
    return await get_schema_intelligence_summary(project_id, current_user, db)

@router.post("/schema/recheck/{project_id}")
async def recheck_project_schemas(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(project_id, current_user, db)
    summary_before = await get_schema_intelligence_summary(project_id, current_user, db)
    # Refresh records by executing full schema analysis
    summary_after = await analyze_project_schemas(project_id, current_user, db)
    return {
        "message": "Schema re-analysis completed successfully",
        "score_before": summary_before["health_score"] if isinstance(summary_before, dict) else getattr(summary_before, "health_score", 0),
        "score_after": summary_after["health_score"] if isinstance(summary_after, dict) else getattr(summary_after, "health_score", 0),
        "summary": summary_after
    }
