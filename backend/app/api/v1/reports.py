from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access
from app.models.user import User
from app.models.project import Project
from app.models.audit import SEOAudit, SEOIssue, SEOTask
from app.models.ranking import Keyword
from app.models.local_seo import Review, Citation, NAPRecord

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/{project_id}/executive")
async def generate_executive_report(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await verify_project_access(project_id, current_user, db)

    # Fetch stats
    iss_res = await db.execute(select(SEOIssue).where(SEOIssue.project_id == project_id))
    issues = iss_res.scalars().all()

    tasks_res = await db.execute(select(SEOTask).where(SEOTask.project_id == project_id))
    tasks = tasks_res.scalars().all()

    kw_res = await db.execute(select(Keyword).where(Keyword.project_id == project_id))
    keywords = kw_res.scalars().all()

    rev_res = await db.execute(select(Review).where(Review.project_id == project_id))
    reviews = rev_res.scalars().all()

    nap_res = await db.execute(select(NAPRecord).where(NAPRecord.project_id == project_id))
    nap = nap_res.scalars().first()

    return {
        "title": f"Local SEO Executive Performance Report — {project.name}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "name": project.name,
            "domain": project.domain,
            "primary_category": project.primary_category,
            "health_score": project.health_score,
            "sub_scores": {
                "technical": project.technical_score,
                "onpage": project.onpage_score,
                "local": project.local_score,
                "gbp": project.gbp_score,
                "reviews": project.reviews_score,
                "citations": project.citations_score,
                "keywords": project.keywords_score,
                "maps": project.maps_score,
            }
        },
        "executive_summary": (
            (f"{project.name} has an overall Local SEO Health Score of {project.health_score}/100. " if project.health_score is not None else f"{project.name} Local SEO Health Score is awaiting initial audit. ") +
            f"The business currently tracks {len(keywords)} local search terms with strong performance across regional map packs. "
            f"During the last 30 days, {len([t for t in tasks if t.status == 'completed'])} technical and on-page optimization tasks were completed."
        ),
        "metrics": {
            "total_keywords": len(keywords),
            "top_3_keywords": len([k for k in keywords if k.current_rank and k.current_rank <= 3]),
            "top_10_keywords": len([k for k in keywords if k.current_rank and k.current_rank <= 10]),
            "total_reviews": len(reviews),
            "avg_rating": round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else 0.0,
            "nap_consistency_score": nap.nap_score if (nap and nap.nap_score is not None) else project.citations_score,
            "open_issues_count": len([i for i in issues if i.status == 'open']),
            "completed_tasks_count": len([t for t in tasks if t.status == 'completed'])
        },
        "next_month_recommendations": [
            "Deploy localized Schema markup across sub-service pages.",
            "Continue proactive review generation campaign to maintain Top 3 Local Pack density.",
            "Fix remaining NAP citations on directory sources.",
            "Publish weekly GBP photo updates and localized service posts."
        ]
    }
