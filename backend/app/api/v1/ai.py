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
from app.models.local_seo import Review
from app.models.gbp import GoogleBusinessProfile
from app.schemas.ai import AIChatRequest, AIAnalysisResponse, ContentOpportunityOut
from app.services.ai_assistant import AIAssistantService

router = APIRouter(prefix="/ai", tags=["AI SEO Assistant"])

@router.post("/diagnostic", response_model=AIAnalysisResponse)
async def analyze_project_query(
    req: AIChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await verify_project_access(req.project_id, current_user, db)

    # Gather structured context
    iss_res = await db.execute(select(SEOIssue).where(SEOIssue.project_id == req.project_id))
    kw_res = await db.execute(select(Keyword).where(Keyword.project_id == req.project_id))
    rev_res = await db.execute(select(Review).where(Review.project_id == req.project_id))

    context = {
        "name": project.name,
        "domain": project.domain,
        "health_score": project.health_score,
        "issues": [i.title for i in iss_res.scalars().all()],
        "keywords": [k.keyword for k in kw_res.scalars().all()],
        "reviews": [{"rating": r.rating, "response_status": r.response_status} for r in rev_res.scalars().all()],
        "gbp": {"completeness_score": 85}
    }

    result = await AIAssistantService.analyze_project_query(req.query, context)
    return AIAnalysisResponse(**result)

@router.post("/review-response/{review_id}")
async def generate_review_response(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    proj = await verify_project_access(review.project_id, current_user, db)
    business_name = proj.name if proj else "Our Business"

    drafted_text = AIAssistantService.draft_review_response(
        author_name=review.author_name,
        rating=review.rating,
        review_text=review.review_text or "",
        business_name=business_name
    )

    review.response_text = drafted_text
    review.response_status = "drafted"
    await db.commit()
    await db.refresh(review)
    return {"message": "AI draft created successfully", "review": review, "draft_response": drafted_text}

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
            search_volume=480,
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
            search_volume=620,
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
            search_volume=350,
            business_value="Medium",
            competition_level="Low",
            target_slug=f"/blog/{cat_slug}-selection-guide"
        )
    ]
