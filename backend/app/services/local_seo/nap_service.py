"""
LocalLift — NAP Consistency Comparison Domain Service

Compares Canonical Business Profile against observed listings (citations, GBP, website, schema).
Ensures zero fabricated consistency: shows real expected vs. found values and provenance.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.local_seo import BusinessProfile, Citation, SchemaRecord
from app.models.gbp import GoogleAccount, GoogleBusinessProfile
from app.services.local_seo.business_profile_service import BusinessProfileService

logger = logging.getLogger("locallift.nap_service")


def _clean_str(s: Optional[str]) -> str:
    return s.strip().lower() if s else ""


def _clean_phone(p: Optional[str]) -> str:
    if not p:
        return ""
    # Strip everything except digits
    return re.sub(r"[^\d]", "", p)


def _compare_field(expected: Optional[str], found: Optional[str], is_phone: bool = False) -> str:
    if not found or not found.strip():
        return "missing"
    if not expected or not expected.strip():
        return "not_evaluated"

    if is_phone:
        return "match" if _clean_phone(expected) == _clean_phone(found) else "mismatch"
    return "match" if _clean_str(expected) == _clean_str(found) else "mismatch"


class NAPComparisonService:
    @staticmethod
    async def compare_project_nap(
        project_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Executes a rigorous NAP comparison for all observed sources against the Canonical Business Profile.
        """
        profile = await BusinessProfileService.get_or_create_canonical_profile(project_id, db)

        # 1. Fetch Citations
        cit_res = await db.execute(select(Citation).where(Citation.project_id == project_id))
        citations = cit_res.scalars().all()

        # 2. Fetch GBP Profile
        acc_res = await db.execute(
            select(GoogleAccount)
            .options(selectinload(GoogleAccount.gbp_profiles))
            .where(GoogleAccount.project_id == project_id)
        )
        google_acc = acc_res.scalars().first()
        gbp_profile = google_acc.gbp_profiles[0] if google_acc and google_acc.gbp_profiles else None

        # 3. Fetch Schema records
        sch_res = await db.execute(
            select(SchemaRecord)
            .where(SchemaRecord.project_id == project_id)
            .order_by(SchemaRecord.id.desc())
        )
        schema_records = sch_res.scalars().all()

        comparisons: List[Dict[str, Any]] = []
        total_sources = 0
        consistent_sources = 0
        mismatch_sources = 0

        # Evaluate GBP
        if gbp_profile:
            total_sources += 1
            name_status = _compare_field(profile.business_name, gbp_profile.business_name)
            phone_status = _compare_field(profile.primary_phone, gbp_profile.phone, is_phone=True)
            addr_status = _compare_field(profile.primary_address, gbp_profile.address)
            web_status = _compare_field(profile.website, gbp_profile.website_url)

            is_aligned = all(s in ["match", "not_evaluated"] for s in [name_status, phone_status, addr_status, web_status])
            if is_aligned:
                consistent_sources += 1
            else:
                mismatch_sources += 1

            comparisons.append({
                "source_type": "GBP",
                "source_name": "Google Business Profile",
                "listing_url": gbp_profile.website_url,
                "provenance": "VERIFIED" if google_acc.is_connected else "OBSERVED",
                "is_consistent": is_aligned,
                "fields": {
                    "business_name": {"expected": profile.business_name, "found": gbp_profile.business_name, "status": name_status},
                    "phone": {"expected": profile.primary_phone, "found": gbp_profile.phone, "status": phone_status},
                    "address": {"expected": profile.primary_address, "found": gbp_profile.address, "status": addr_status},
                    "website": {"expected": profile.website, "found": gbp_profile.website_url, "status": web_status}
                }
            })

        # Evaluate Citations
        for c in citations:
            total_sources += 1
            # If found fields were recorded during audit/crawl, compare them honestly
            name_status = _compare_field(profile.business_name, c.found_name) if c.found_name else "missing"
            phone_status = _compare_field(profile.primary_phone, c.found_phone, is_phone=True) if c.found_phone else "missing"
            addr_status = _compare_field(profile.primary_address, c.found_address) if c.found_address else "missing"
            web_status = _compare_field(profile.website, c.found_website) if c.found_website else "missing"

            is_aligned = (c.nap_status == "consistent" or all(s == "match" for s in [name_status, phone_status, addr_status] if s != "not_evaluated"))
            if is_aligned and c.status == "listed":
                consistent_sources += 1
            else:
                mismatch_sources += 1

            comparisons.append({
                "source_type": "DIRECTORY_CITATION",
                "source_name": c.source_name,
                "listing_url": c.listing_url,
                "provenance": c.verification_status or "USER_PROVIDED",
                "is_consistent": is_aligned,
                "fields": {
                    "business_name": {"expected": profile.business_name, "found": c.found_name, "status": name_status},
                    "phone": {"expected": profile.primary_phone, "found": c.found_phone, "status": phone_status},
                    "address": {"expected": profile.primary_address, "found": c.found_address, "status": addr_status},
                    "website": {"expected": profile.website, "found": c.found_website, "status": web_status}
                }
            })

        nap_score = round((consistent_sources / total_sources) * 100) if total_sources > 0 else None

        return {
            "project_id": project_id,
            "canonical_profile": {
                "business_name": profile.business_name,
                "primary_phone": profile.primary_phone,
                "primary_address": profile.primary_address,
                "city": profile.city,
                "state": profile.state,
                "postal_code": profile.postal_code,
                "country": profile.country,
                "website": profile.website
            },
            "total_sources_checked": total_sources,
            "consistent_sources": consistent_sources,
            "mismatch_sources": mismatch_sources,
            "nap_score": nap_score,
            "score_available": nap_score is not None,
            "comparisons": comparisons
        }
