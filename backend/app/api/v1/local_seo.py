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
from app.schemas.local_seo import (
    ReviewOut, ReviewDraftResponse, ReviewApprovePublish,
    CitationOut, NAPRecordOut, CompetitorOut, SchemaRecordOut, SchemaGenerateRequest
)
from app.services.ai_assistant import AIAssistantService

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

# Schema Generator & Validator
@router.get("/schema/{project_id}", response_model=List[SchemaRecordOut])
async def list_schemas(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(SchemaRecord).where(SchemaRecord.project_id == project_id))
    return result.scalars().all()

@router.post("/schema/generate")
async def generate_local_schema(
    req: SchemaGenerateRequest,
    current_user: User = Depends(get_current_user)
):
    schema_json = {
        "@context": "https://schema.org",
        "@type": req.business_type,
        "name": req.business_name,
        "url": req.url,
        "telephone": req.phone,
        "priceRange": req.price_range,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": req.street_address,
            "addressLocality": req.city,
            "addressRegion": req.state,
            "postalCode": req.postal_code,
            "addressCountry": req.country
        },
        "openingHoursSpecification": [
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "opens": "08:00",
                "closes": "18:00"
            }
        ]
    }
    if req.latitude and req.longitude:
        schema_json["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": req.latitude,
            "longitude": req.longitude
        }

    formatted_json = json.dumps(schema_json, indent=2)
    return {
        "schema_type": req.business_type,
        "json_ld": formatted_json,
        "html_tag": f'<script type="application/ld+json">\n{formatted_json}\n</script>'
    }
