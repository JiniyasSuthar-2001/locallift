import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access
from app.models.user import User
from app.models.project import Project, Location
from app.models.audit import SEOIssue
from app.models.ranking import Keyword
from app.models.local_seo import Review, Citation
from app.models.gbp import GoogleAccount, GoogleBusinessProfile
from app.schemas.ai import AIChatRequest, AIAnalysisResponse, ContentOpportunityOut
from app.services.ai_assistant import AIAssistantService

logger = logging.getLogger("locallift.api.ai")

router = APIRouter(prefix="/ai", tags=["AI SEO Assistant"])

@router.post("/diagnostic", response_model=AIAnalysisResponse)
async def analyze_project_query(
    req: AIChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes an evidence-backed Local SEO root cause diagnostic query
    synthesizing real rankings, GBP connection, reviews, and audit signals.
    """
    # 1. Input Validation / Protection
    clean_query = req.query.strip()
    if not clean_query:
        raise HTTPException(status_code=422, detail="Diagnostic query cannot be empty.")
    if len(clean_query) > 1000:
        raise HTTPException(status_code=422, detail="Diagnostic query exceeds maximum allowed length of 1000 characters.")

    project = await verify_project_access(req.project_id, current_user, db)

    # 2. Gather verified real project context
    iss_res = await db.execute(select(SEOIssue).where(SEOIssue.project_id == req.project_id).limit(15))
    kw_res = await db.execute(select(Keyword).where(Keyword.project_id == req.project_id).limit(20))
    rev_res = await db.execute(select(Review).where(Review.project_id == req.project_id).limit(10))
    cit_res = await db.execute(select(Citation).where(Citation.project_id == req.project_id))
    loc_res = await db.execute(select(Location).where(Location.project_id == req.project_id))
    loc = loc_res.scalars().first()

    # GBP Profile connection
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == req.project_id))
    google_acc = acc_res.scalars().first()
    gbp = None
    if google_acc:
        gbp_res = await db.execute(
            select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == google_acc.id)
        )
        gbp = gbp_res.scalars().first()

    gbp_context = {
        "connected": gbp is not None,
        "business_name": gbp.business_name if gbp else None,
        "completeness_score": gbp.completeness_score if gbp else 0,
        "search_impressions": gbp.search_impressions if gbp else 0,
        "maps_impressions": gbp.maps_impressions if gbp else 0,
        "is_verified": gbp.is_verified if gbp else False
    } if gbp else {"connected": False}

    citations_list = cit_res.scalars().all()

    context = {
        "name": project.name,
        "domain": project.domain,
        "primary_category": project.primary_category,
        "city": loc.city if loc else "",
        "state": loc.state if loc else "",
        "country": loc.country if loc else project.country,
        "health_score": project.health_score or 0,
        "issues": [{"title": i.title, "category": i.category, "severity": str(i.severity)} for i in iss_res.scalars().all()],
        "keywords": [{"keyword": k.keyword, "rank": k.current_rank, "location": k.target_location} for k in kw_res.scalars().all()],
        "reviews": [{"author": r.author_name, "rating": r.rating, "text": r.review_text, "sentiment": r.sentiment, "status": r.response_status} for r in rev_res.scalars().all()],
        "gbp": gbp_context,
        "citations": {
            "total_tracked": len(citations_list),
            "listed_count": len([c for c in citations_list if c.status == "listed"])
        }
    }

    try:
        result = await AIAssistantService.analyze_project_query(clean_query, context)
        return AIAnalysisResponse(**result)
    except Exception as e:
        err_str = str(e)
        logger.error(f"AI Assistant diagnostic error: {err_str}")
        if "AI_NOT_CONFIGURED" in err_str:
            raise HTTPException(
                status_code=400,
                detail="AI_NOT_CONFIGURED: AI_API_KEY is not configured in environment settings. Please configure your AI API key to enable real AI diagnostics."
            )
        elif "AI_RATE_LIMIT" in err_str:
            raise HTTPException(status_code=429, detail="AI_RATE_LIMIT: Rate limit exceeded on AI provider. Please retry in a few moments.")
        elif "AI_TIMEOUT" in err_str:
            raise HTTPException(status_code=504, detail="AI_TIMEOUT: AI request timed out. Please try again.")
        else:
            raise HTTPException(status_code=500, detail=f"AI diagnostic failed: {err_str[:200]}")

@router.post("/review-response/{review_id}")
async def generate_review_response(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Drafts a personalized, evidence-based reply tailored to the specific customer feedback text.
    Result is stored as a DRAFT requiring human review & approval before publishing.
    """
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    proj = await verify_project_access(review.project_id, current_user, db)
    business_name = proj.name if proj else "Our Business"

    try:
        drafted_text = await AIAssistantService.draft_review_response(
            author_name=review.author_name,
            rating=review.rating,
            review_text=review.review_text or "",
            business_name=business_name,
            business_category=proj.primary_category if proj else None
        )
    except Exception as e:
        err_str = str(e)
        logger.error(f"AI review response generation error: {err_str}")
        if "AI_NOT_CONFIGURED" in err_str:
            raise HTTPException(
                status_code=400,
                detail="AI_NOT_CONFIGURED: AI_API_KEY is not configured in environment settings. Please configure your AI API key to enable AI review drafting."
            )
        elif "AI_RATE_LIMIT" in err_str:
            raise HTTPException(status_code=429, detail="AI_RATE_LIMIT: Rate limit exceeded on AI provider. Please retry shortly.")
        elif "AI_TIMEOUT" in err_str:
            raise HTTPException(status_code=504, detail="AI_TIMEOUT: AI request timed out. Please try again.")
        else:
            raise HTTPException(status_code=500, detail=f"AI review draft failed: {err_str[:200]}")

    review.response_text = drafted_text
    review.response_status = "drafted"
    await db.commit()
    await db.refresh(review)
    return {
        "message": "AI draft created successfully (Pending Human Approval)",
        "review": review,
        "draft_response": drafted_text,
        "status": "drafted"
    }

@router.get("/content-opportunities/{project_id}", response_model=List[ContentOpportunityOut])
async def get_content_opportunities(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    proj = await verify_project_access(project_id, current_user, db)
    loc_res = await db.execute(select(Location).where(Location.project_id == project_id))
    loc = loc_res.scalars().first()
    city = (loc.city if loc and loc.city else "Local Area").strip()
    category = (proj.primary_category or "Local Business").strip()
    cat_lower = category.lower()
    city_lower = city.lower()
    cat_slug = cat_lower.replace(" ", "-")
    city_slug = city_lower.replace(" ", "-")

    # Fetch real keywords if present
    kw_res = await db.execute(select(Keyword).where(Keyword.project_id == project_id).limit(3))
    kw_list = [k.keyword for k in kw_res.scalars().all()]
    primary_kw = kw_list[0] if kw_list else f"{cat_lower} in {city_lower}"

    return [
        ContentOpportunityOut(
            topic=f"Emergency {category} Near Me: 24/7 Rapid Response Guide",
            page_type="Service Page",
            primary_keyword=f"emergency {cat_lower} {city_lower}",
            secondary_keywords=[f"24/7 {cat_lower}", f"urgent {cat_lower} service", f"same day {cat_lower} {city_lower}"],
            search_intent="Transactional",
            search_volume=None,
            search_volume_status="Volume unavailable — connect keyword data provider",
            business_value="High",
            competition_level="Medium",
            target_slug=f"/services/emergency-{cat_slug}"
        ),
        ContentOpportunityOut(
            topic=f"Commercial & Residential {category} in {city}",
            page_type="Location Page",
            primary_keyword=primary_kw,
            secondary_keywords=[f"licensed {cat_lower} {city_lower}", f"best {cat_lower} near me", f"{city_lower} contractor"],
            search_intent="Commercial",
            search_volume=None,
            search_volume_status="Volume unavailable — connect keyword data provider",
            business_value="High",
            competition_level="Low",
            target_slug=f"/locations/{cat_slug}-{city_slug}"
        ),
        ContentOpportunityOut(
            topic=f"Complete Checklist: How to Choose a Trusted {category} in {city}",
            page_type="Blog Guide",
            primary_keyword=f"how to choose a {cat_lower} in {city_lower}",
            secondary_keywords=[f"{cat_lower} cost guide {city_lower}", f"hiring a licensed {cat_lower}", "pricing checklist"],
            search_intent="Informational",
            search_volume=None,
            search_volume_status="Volume unavailable — connect keyword data provider",
            business_value="Medium",
            competition_level="Low",
            target_slug=f"/blog/{cat_slug}-selection-guide"
        )
    ]
