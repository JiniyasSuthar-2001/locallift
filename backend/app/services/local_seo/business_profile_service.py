"""
LocalLift — Canonical Business Profile Domain Service

Provides single authoritative management of project business identity.
Ensures that NAP, GBP, citations, schema, Geo center, and audit systems
reference one synchronized business profile without fragmented data.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.local_seo import BusinessProfile, VerificationStatus
from app.models.project import Project, Location
from app.schemas.local_seo import BusinessProfileUpdate

logger = logging.getLogger("locallift.business_profile")


class BusinessProfileService:
    @staticmethod
    async def get_or_create_canonical_profile(
        project_id: int,
        db: AsyncSession
    ) -> BusinessProfile:
        """
        Retrieves existing canonical BusinessProfile or initializes one from
        the Project and primary Location records.
        """
        stmt = select(BusinessProfile).where(BusinessProfile.project_id == project_id)
        res = await db.execute(stmt)
        profile = res.scalars().first()

        if profile:
            return profile

        # Load project with locations
        proj_stmt = (
            select(Project)
            .options(selectinload(Project.locations))
            .where(Project.id == project_id)
        )
        proj_res = await db.execute(proj_stmt)
        project = proj_res.scalars().first()
        if not project:
            raise ValueError(f"Project {project_id} does not exist.")

        primary_loc = project.locations[0] if project.locations else None

        profile = BusinessProfile(
            project_id=project_id,
            business_name=project.name,
            website=f"https://{project.domain}" if project.domain and not project.domain.startswith("http") else project.domain,
            primary_phone=primary_loc.phone if primary_loc else None,
            primary_address=primary_loc.address if primary_loc else None,
            city=primary_loc.city if primary_loc else None,
            state=primary_loc.state if primary_loc else None,
            postal_code=primary_loc.postal_code if primary_loc else None,
            country=primary_loc.country if primary_loc else project.country,
            latitude=primary_loc.latitude if primary_loc else None,
            longitude=primary_loc.longitude if primary_loc else None,
            primary_category=project.primary_category,
            additional_categories=project.additional_categories or [],
            service_area=primary_loc.service_areas if primary_loc else [],
            place_id=primary_loc.place_id if primary_loc else None,
            source="USER_PROVIDED",
            verification_status=VerificationStatus.NOT_VERIFIED.value,
            created_at=datetime.now(timezone.utc)
        )

        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        logger.info(f"Initialized canonical business profile for project {project_id}")
        return profile

    @staticmethod
    async def update_canonical_profile(
        project_id: int,
        update_data: BusinessProfileUpdate,
        db: AsyncSession
    ) -> BusinessProfile:
        """
        Updates the canonical BusinessProfile and synchronizes identity fields
        back to Project and primary Location to maintain absolute consistency.
        """
        profile = await BusinessProfileService.get_or_create_canonical_profile(project_id, db)

        payload = update_data.model_dump(exclude_unset=True)

        for k, v in payload.items():
            if hasattr(profile, k) and v is not None:
                setattr(profile, k, v)

        profile.updated_at = datetime.now(timezone.utc)

        # Synchronize back to Project & primary Location
        proj_stmt = (
            select(Project)
            .options(selectinload(Project.locations))
            .where(Project.id == project_id)
        )
        proj_res = await db.execute(proj_stmt)
        project = proj_res.scalars().first()

        if project:
            if "business_name" in payload and payload["business_name"]:
                project.name = payload["business_name"]
            if "primary_category" in payload and payload["primary_category"]:
                project.primary_category = payload["primary_category"]
            if "additional_categories" in payload and payload["additional_categories"] is not None:
                project.additional_categories = payload["additional_categories"]

            if project.locations:
                primary_loc = project.locations[0]
            else:
                primary_loc = Location(
                    project_id=project_id,
                    name=payload.get("business_name") or project.name
                )
                db.add(primary_loc)

            if "primary_phone" in payload and payload["primary_phone"]:
                primary_loc.phone = payload["primary_phone"]
            if "primary_address" in payload and payload["primary_address"]:
                primary_loc.address = payload["primary_address"]
            if "city" in payload and payload["city"]:
                primary_loc.city = payload["city"]
            if "state" in payload and payload["state"]:
                primary_loc.state = payload["state"]
            if "postal_code" in payload and payload["postal_code"]:
                primary_loc.postal_code = payload["postal_code"]
            if "country" in payload and payload["country"]:
                primary_loc.country = payload["country"]
            if "latitude" in payload and payload["latitude"] is not None:
                primary_loc.latitude = payload["latitude"]
            if "longitude" in payload and payload["longitude"] is not None:
                primary_loc.longitude = payload["longitude"]
            if "place_id" in payload and payload["place_id"]:
                primary_loc.place_id = payload["place_id"]
            if "service_area" in payload and payload["service_area"] is not None:
                primary_loc.service_areas = payload["service_area"]

        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    def verify_profile_integrity(profile: BusinessProfile) -> Dict[str, Any]:
        """
        Validates profile completeness for local SEO operations and returns missing core attributes.
        """
        core_fields = {
            "business_name": profile.business_name,
            "website": profile.website,
            "primary_phone": profile.primary_phone,
            "primary_address": profile.primary_address,
            "city": profile.city,
            "state": profile.state,
            "postal_code": profile.postal_code,
            "latitude": profile.latitude,
            "longitude": profile.longitude,
            "primary_category": profile.primary_category
        }

        missing = [k for k, v in core_fields.items() if v is None or (isinstance(v, str) and not v.strip())]
        completeness_pct = round(((len(core_fields) - len(missing)) / len(core_fields)) * 100)

        return {
            "completeness_pct": completeness_pct,
            "missing_fields": missing,
            "is_audit_ready": len(missing) == 0,
            "has_coordinates": bool(profile.latitude is not None and profile.longitude is not None),
            "has_place_id": bool(profile.place_id)
        }
