from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.project import Project
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
    proj_res = await db.execute(select(Project).where(Project.id == req.project_id))
    project = proj_res.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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

@router.get("/content-opportunities/{project_id}", response_model=List[ContentOpportunityOut])
async def get_content_opportunities(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    proj_res = await db.execute(select(Project).where(Project.id == project_id))
    proj = proj_res.scalars().first()
    category = proj.primary_category if proj else "Electrician"

    return [
        ContentOpportunityOut(
            topic=f"Emergency {category} Near Me: 24/7 Rapid Response Guide",
            page_type="Service Page",
            primary_keyword=f"emergency {category.lower()} brisbane",
            secondary_keywords=[f"24/7 {category.lower()}", f"urgent {category.lower()} repair", "same day service"],
            search_intent="Transactional",
            search_volume=720,
            business_value="High",
            competition_level="Medium",
            target_slug=f"/services/emergency-{category.lower().replace(' ', '-')}"
        ),
        ContentOpportunityOut(
            topic=f"Commercial {category} & Switchboard Upgrades for Businesses",
            page_type="Service Page",
            primary_keyword=f"commercial {category.lower()} brisbane cbd",
            secondary_keywords=["industrial maintenance", "switchboard compliance audit", "commercial wiring"],
            search_intent="Commercial",
            search_volume=480,
            business_value="High",
            competition_level="High",
            target_slug=f"/services/commercial-{category.lower().replace(' ', '-')}"
        ),
        ContentOpportunityOut(
            topic=f"{category} Services in Logan & South Brisbane Suburbs",
            page_type="Location Page",
            primary_keyword=f"{category.lower()} logan city",
            secondary_keywords=["local contractor south brisbane", "residential repair logan", "licensed technician"],
            search_intent="Commercial",
            search_volume=590,
            business_value="High",
            competition_level="Low",
            target_slug=f"/locations/{category.lower().replace(' ', '-')}-logan"
        ),
        ContentOpportunityOut(
            topic="How to Tell If Your Home Wiring Needs An Urgent Safety Inspection",
            page_type="Blog Guide",
            primary_keyword="electrical safety inspection signs",
            secondary_keywords=["tripping safety switch causes", "old home rewiring cost", "safety certificate checklist"],
            search_intent="Informational",
            search_volume=880,
            business_value="Medium",
            competition_level="Low",
            target_slug="/blog/home-safety-inspection-guide"
        )
    ]
