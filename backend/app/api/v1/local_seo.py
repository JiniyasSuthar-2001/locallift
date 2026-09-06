import json
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.local_seo import Review, Citation, NAPRecord, Competitor, SchemaRecord
from app.models.audit import WebsitePage
from app.models.project import Location
from app.schemas.local_seo import (
    ReviewOut, ReviewDraftResponse, ReviewApprovePublish,
    CitationCreate, CitationOut, NAPRecordOut, CompetitorCreate, CompetitorOut, SchemaRecordOut, SchemaGenerateRequest,
    SchemaValidateRequest, SchemaValidateResponse, SchemaIntelligenceSummaryOut
)
from app.services.ai_assistant import AIAssistantService
from app.services.schema_intelligence import SchemaIntelligenceEngine, TIER_1_SCHEMAS, INDUSTRY_SCHEMAS

router = APIRouter(prefix="/local-seo", tags=["Local SEO & Reputation"])

# Reviews
@router.get("/reviews/{project_id}", response_model=List[ReviewOut])
async def list_reviews(
    project_id: int,
    sentiment: Optional[str] = None,
    response_status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Review).where(Review.project_id == project_id)
    if sentiment:
        query = query.where(Review.sentiment == sentiment)
    if response_status:
        query = query.where(Review.response_status == response_status)

    result = await db.execute(query.order_by(Review.review_date.desc()))
    return result.scalars().all()

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

    proj_res = await db.execute(select(Project).where(Project.id == review.project_id))
    proj = proj_res.scalars().first()
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
    return {"message": "AI draft created successfully", "review": review}

@router.post("/reviews/{review_id}/approve")
async def approve_and_publish_review_response(
    review_id: int,
    payload: ReviewApprovePublish,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    review.response_text = payload.response_text
    review.response_status = "published"
    review.response_date = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(review)
    return {"message": "Response approved and recorded as published.", "review": review}

# Citations
@router.get("/citations/{project_id}", response_model=List[CitationOut])
async def list_citations(
    project_id: int,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Citation).where(Citation.project_id == project_id)
    if status_filter:
        query = query.where(Citation.status == status_filter)
    result = await db.execute(query.order_by(Citation.domain_authority.desc()))
    return result.scalars().all()

@router.post("/citations", response_model=CitationOut)
async def add_citation(
    cit_in: CitationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
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
        domain_authority=cit_in.domain_authority or 50,
        category=cit_in.category or "General Directory",
        status="active",
        nap_status=cit_in.nap_status or "match",
        last_checked_at=datetime.now(timezone.utc)
    )
    db.add(cit)
    await db.commit()
    await db.refresh(cit)
    return cit

# NAP Consistency
@router.get("/nap/{project_id}", response_model=Optional[NAPRecordOut])
async def get_nap_record(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(NAPRecord).where(NAPRecord.project_id == project_id).order_by(NAPRecord.id.desc())
    )
    return result.scalars().first()

# Competitors
@router.get("/competitors/{project_id}", response_model=List[CompetitorOut])
async def list_competitors(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Competitor).where(Competitor.project_id == project_id))
    return result.scalars().all()

@router.post("/competitors", response_model=CompetitorOut)
async def add_competitor(
    comp_in: CompetitorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    comp = Competitor(
        project_id=comp_in.project_id,
        name=comp_in.name,
        domain=comp_in.domain.replace("https://", "").replace("http://", "").rstrip("/"),
        gbp_name=comp_in.gbp_name,
        rating=comp_in.rating or 0.0,
        reviews_count=comp_in.reviews_count or 0,
        local_visibility_score=0,
        top_keywords_count=0
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp

# -----------------------------------------------------------------------------
# Schema Intelligence, Generator & Validator Endpoints
# -----------------------------------------------------------------------------
@router.get("/schema/{project_id}", response_model=List[SchemaRecordOut])
async def list_schemas(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(SchemaRecord).where(SchemaRecord.project_id == project_id))
    return result.scalars().all()

@router.get("/schema/{project_id}/intelligence", response_model=SchemaIntelligenceSummaryOut)
async def get_schema_intelligence_summary(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    proj_res = await db.execute(select(Project).where(Project.id == project_id))
    proj = proj_res.scalars().first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

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

    # Determine Project Context
    loc_res = await db.execute(select(Location).where(Location.project_id == project_id))
    loc = loc_res.scalars().first()
    project_context = {
        "name": proj.name,
        "domain": proj.domain,
        "phone": loc.phone if loc else None,
        "address": loc.address if loc else None,
        "city": loc.city if loc else None,
        "state": loc.state if loc else None,
        "postal_code": loc.postal_code if loc else None,
        "country": loc.country if loc else None,
        "latitude": loc.latitude if loc else None,
        "longitude": loc.longitude if loc else None
    }

    score_result = SchemaIntelligenceEngine.calculate_quality_score(page_analyses)
    recommendations = SchemaIntelligenceEngine.generate_recommendations(page_analyses, project_context)

    # Calculate Tier 1 Schema Matrix Status
    # Tier 1 statuses: "Detected" | "Missing" | "Invalid" | "Not Applicable"
    industry_type = proj.primary_category or "LocalBusiness"
    applicability_map = SchemaIntelligenceEngine.evaluate_applicability(
        page_type="Homepage",
        business_type=industry_type,
        has_breadcrumbs=True,
        has_reviews=True,
        has_faq_content=True
    )

    tier_1_status = {}
    for s_name in TIER_1_SCHEMAS:
        app_info = applicability_map.get(s_name, {"applicability": "Potentially Applicable", "reason": "General web entity"})
        app_level = app_info.get("applicability", "Potentially Applicable")

        if s_name in all_detected_types:
            # Check if any record has errors for this schema
            has_err = any(s_name in (r.errors or []) for r in records)
            status_val = "Invalid" if has_err else "Detected"
        elif app_level == "Not Applicable":
            status_val = "Not Applicable"
        elif app_level in ["Highly Applicable", "Applicable"]:
            status_val = "Missing"
        else:
            status_val = "Not Applicable"

        tier_1_status[s_name] = {
            "status": status_val,
            "applicability": app_level,
            "reason": app_info.get("reason", "")
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
    result = SchemaIntelligenceEngine.generate_safe_schema(
        business_type=req.business_type,
        business_name=req.business_name,
        url=req.url,
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
    current_user: User = Depends(get_current_user)
):
    return SchemaIntelligenceEngine.validate_json_ld_string(req.json_ld)

@router.post("/schema/analyze/{project_id}", response_model=SchemaIntelligenceSummaryOut)
async def analyze_project_schemas(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch project and location
    proj_res = await db.execute(select(Project).where(Project.id == project_id))
    proj = proj_res.scalars().first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    loc_res = await db.execute(select(Location).where(Location.project_id == project_id))
    loc = loc_res.scalars().first()
    project_context = {
        "name": proj.name,
        "domain": proj.domain,
        "phone": loc.phone if loc else None,
        "address": loc.address if loc else None,
        "city": loc.city if loc else None,
        "state": loc.state if loc else None,
        "postal_code": loc.postal_code if loc else None,
        "country": loc.country if loc else None,
        "latitude": loc.latitude if loc else None,
        "longitude": loc.longitude if loc else None
    }

    # Fetch existing website pages
    pages_res = await db.execute(
        select(WebsitePage).join(Project.websites).where(Project.id == project_id)
    )
    pages = pages_res.scalars().all()

    # If no crawled pages, ensure at least default schema records exist
    records_res = await db.execute(select(SchemaRecord).where(SchemaRecord.project_id == project_id))
    existing_records = records_res.scalars().all()

    for rec in existing_records:
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
    summary_before = await get_schema_intelligence_summary(project_id, current_user, db)
    # Refresh records
    summary_after = await get_schema_intelligence_summary(project_id, current_user, db)
    return {
        "message": "Schema re-analysis completed successfully",
        "score_before": summary_before.health_score,
        "score_after": summary_after.health_score,
        "summary": summary_after
    }
