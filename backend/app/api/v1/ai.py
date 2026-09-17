import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access
from app.models.user import User
from app.models.project import Project, Location
from app.models.audit import SEOIssue, WebsitePage
from app.models.ranking import Keyword
from app.models.local_seo import Review, Citation
from app.models.gbp import GoogleAccount, GoogleBusinessProfile
from app.schemas.ai import AIChatRequest, AIAnalysisResponse, ContentOpportunityOut
from app.services.ai_assistant import AIAssistantService
from app.services.ai_consumption_service import AIConsumptionService

logger = logging.getLogger("locallift.api.ai")

router = APIRouter(prefix="/ai", tags=["AI SEO Assistant"])

@router.get("/usage-status")
async def get_ai_usage_status(
    project_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Exposes customer-facing AI credits balance, daily/monthly usage counters, and limit settings.
    """
    if project_id:
        await verify_project_access(project_id, current_user, db)

    org_id = await AIConsumptionService.resolve_organization_id(db, current_user, project_id)
    return await AIConsumptionService.get_usage_status(db, org_id)

@router.post("/diagnostic", response_model=AIAnalysisResponse)
async def analyze_project_query(
    req: AIChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes an evidence-backed Local SEO root cause diagnostic query
    gated by central AI access controls, daily/monthly limits, and credit balances.
    """
    clean_query = req.query.strip()
    if not clean_query:
        raise HTTPException(status_code=422, detail="Diagnostic query cannot be empty.")
    if len(clean_query) > 1000:
        raise HTTPException(status_code=422, detail="Diagnostic query exceeds maximum allowed length of 1000 characters.")

    project = await verify_project_access(req.project_id, current_user, db)

    # Gather project context
    iss_res = await db.execute(select(SEOIssue).where(SEOIssue.project_id == req.project_id).limit(15))
    kw_res = await db.execute(select(Keyword).where(Keyword.project_id == req.project_id).limit(20))
    rev_res = await db.execute(select(Review).where(Review.project_id == req.project_id).limit(10))
    cit_res = await db.execute(select(Citation).where(Citation.project_id == req.project_id))
    loc_res = await db.execute(select(Location).where(Location.project_id == req.project_id))
    loc = loc_res.scalars().first()

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
        "health_score": project.health_score,
        "issues": [{"title": i.title, "category": i.category, "severity": str(i.severity)} for i in iss_res.scalars().all()],
        "keywords": [{"keyword": k.keyword, "rank": k.current_rank, "location": k.target_location} for k in kw_res.scalars().all()],
        "reviews": [{"author": r.author_name, "rating": r.rating, "text": r.review_text, "sentiment": r.sentiment, "status": r.response_status} for r in rev_res.scalars().all()],
        "gbp": gbp_context,
        "citations": {
            "total_tracked": len(citations_list),
            "listed_count": len([c for c in citations_list if c.status == "listed"])
        }
    }

    # Pass through Central AI Access & Billing Gate
    async def _call_provider():
        return await AIAssistantService.analyze_project_query(clean_query, context)

    result = await AIConsumptionService.execute_gated_request(
        db=db,
        user=current_user,
        project_id=req.project_id,
        task_type="diagnostic",
        provider_fn=_call_provider,
        requested_cost=1.0
    )
    return AIAnalysisResponse(**result)

@router.post("/review-response/{review_id}")
async def generate_review_response(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Drafts a personalized reply tailored to customer feedback, gated by AI usage controls.
    """
    result = await db.execute(select(Review).where(Review.id == review_id))
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
    """
    Generates content opportunity recommendations gated by central AI access controls.
    """
    proj = await verify_project_access(project_id, current_user, db)
    loc_res = await db.execute(select(Location).where(Location.project_id == project_id))
    loc = loc_res.scalars().first()
    city = (loc.city if loc and loc.city else "Local Area").strip()
    category = (proj.primary_category or "Local Business").strip()

    kw_res = await db.execute(select(Keyword).where(Keyword.project_id == project_id).limit(10))
    keywords = [k.keyword for k in kw_res.scalars().all()]

    page_res = await db.execute(select(WebsitePage).where(WebsitePage.website_id == proj.id).limit(5))
    pages = [{"title": p.title, "url": p.url} for p in page_res.scalars().all()]

    project_context = {
        "project_id": proj.id,
        "business_name": proj.name,
        "domain": proj.domain,
        "category": category,
        "city": city,
        "keywords": keywords,
        "crawled_pages": pages
    }

    async def _call_provider():
        return await AIAssistantService.generate_content_opportunities(project_context)

    raw_opps = await AIConsumptionService.execute_gated_request(
        db=db,
        user=current_user,
        project_id=project_id,
        task_type="content_opportunities",
        provider_fn=_call_provider,
        requested_cost=1.0
    )

    out = []
    if isinstance(raw_opps, list):
        for o in raw_opps:
            if isinstance(o, dict):
                out.append(ContentOpportunityOut(
                    topic=o.get("topic") or f"Local {category} Guide",
                    page_type=o.get("page_type") or "Service Page",
                    primary_keyword=o.get("primary_keyword") or f"{category.lower()} in {city.lower()}",
                    secondary_keywords=o.get("secondary_keywords") or [f"best {category.lower()}", "near me"],
                    search_intent=o.get("search_intent") or "Transactional",
                    search_volume=o.get("search_volume"),
                    search_volume_status=o.get("search_volume_status") or "Volume unavailable — connect keyword data provider",
                    business_value=o.get("business_value") or "High",
                    competition_level=o.get("competition_level") or "Medium",
                    target_slug=o.get("target_slug") or f"/services/{category.lower().replace(' ', '-')}"
                ))
    if out:
        return out

    # Fallback structure if array empty
    cat_slug = category.lower().replace(" ", "-")
    city_slug = city.lower().replace(" ", "-")
    primary_kw = keywords[0] if keywords else f"{category.lower()} in {city.lower()}"
    return [
        ContentOpportunityOut(
            topic=f"Emergency {category} Near Me: 24/7 Rapid Response Guide",
            page_type="Service Page",
            primary_keyword=f"emergency {category.lower()} {city.lower()}",
            secondary_keywords=[f"24/7 {category.lower()}", f"urgent {category.lower()} service"],
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
            secondary_keywords=[f"licensed {category.lower()} {city.lower()}", f"best {category.lower()} near me"],
            search_intent="Commercial",
            search_volume=None,
            search_volume_status="Volume unavailable — connect keyword data provider",
            business_value="High",
            competition_level="Low",
            target_slug=f"/locations/{cat_slug}-{city_slug}"
        )
    ]
