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

    total_kw = len(keywords)
    top_3 = len([k for k in keywords if k.current_rank and k.current_rank <= 3])
    top_10 = len([k for k in keywords if k.current_rank and k.current_rank <= 10])
    completed_tasks = len([t for t in tasks if t.status == 'completed'])
    open_issues = len([i for i in issues if i.status == 'open'])
    total_revs = len(reviews)
    avg_rating = round(sum(r.rating for r in reviews) / total_revs, 1) if total_revs > 0 else None

    # Construct truthful executive summary
    summary_parts = []
    if project.health_score is not None:
        summary_parts.append(f"{project.name} has an overall Local SEO Health Score of {project.health_score}/100.")
    else:
        summary_parts.append(f"{project.name} Local SEO Health Score is awaiting initial audit.")

    if total_kw == 0:
        summary_parts.append("No local search keywords are currently configured or tracked.")
    elif top_3 > 0:
        summary_parts.append(f"The business currently tracks {total_kw} local search terms with {top_3} ranking in the Top 3 Local Pack.")
    elif top_10 > 0:
        summary_parts.append(f"The business currently tracks {total_kw} local search terms with {top_10} ranking in the Top 10.")
    else:
        summary_parts.append(f"The business currently tracks {total_kw} local search terms awaiting first rank scan or visibility improvements.")

    if completed_tasks > 0:
        summary_parts.append(f"During the last 30 days, {completed_tasks} technical and on-page optimization tasks were completed.")
    else:
        summary_parts.append("No optimization tasks have been completed in the last 30 days.")

    executive_summary = " ".join(summary_parts)

    # Dynamic data-driven recommendations
    recommendations: List[str] = []
    if project.health_score is None:
        recommendations.append("Execute an initial website technical and on-page audit to identify baseline crawl issues.")
    elif open_issues > 0:
        recommendations.append(f"Resolve {open_issues} open technical and on-page SEO issues to improve site crawlability.")

    if total_kw == 0:
        recommendations.append("Add high-intent local target keywords to begin monitoring local map pack rankings.")
    elif top_3 == 0 and total_kw > 0:
        recommendations.append("Optimize localized landing pages and GBP categories to push tracked keywords into the Top 3 Local Pack.")
    else:
        recommendations.append("Continue proactive review generation campaign to maintain Top 3 Local Pack density.")

    if total_revs == 0:
        recommendations.append("Launch a customer review acquisition campaign to build initial local social proof and star ratings.")
    elif avg_rating is not None and avg_rating < 4.5:
        recommendations.append("Improve customer sentiment and actively respond to feedback to raise the average review rating.")

    if nap is None or nap.nap_score is None or nap.nap_score < 85:
        recommendations.append("Audit and standardize NAP (Name, Address, Phone) consistency across major directory citations.")

    if len(recommendations) < 3:
        recommendations.append("Deploy localized Schema markup across key service pages to enhance search engine rich snippets.")
    if len(recommendations) < 4:
        recommendations.append("Publish regular Google Business Profile updates and localized service posts to boost engagement.")

    seen_recs = set()
    final_recommendations = []
    for r in recommendations:
        if r not in seen_recs:
            seen_recs.add(r)
            final_recommendations.append(r)
        if len(final_recommendations) == 4:
            break

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
        "executive_summary": executive_summary,
        "metrics": {
            "total_keywords": total_kw,
            "top_3_keywords": top_3,
            "top_10_keywords": top_10,
            "total_reviews": total_revs,
            "avg_rating": avg_rating,
            "nap_consistency_score": nap.nap_score if (nap and nap.nap_score is not None) else project.citations_score,
            "open_issues_count": open_issues,
            "completed_tasks_count": completed_tasks
        },
        "next_month_recommendations": final_recommendations
    }
