"""
LocalLift — NAP Consistency Comparison Domain Service

Compares Canonical Business Profile against observed listings (citations, GBP, website, schema).
Ensures zero fabricated consistency: shows real expected vs. found values and provenance.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.local_seo import BusinessProfile, Citation, SchemaRecord
from app.models.gbp import GoogleBusinessProfile
from app.services.local_seo.business_profile_service import BusinessProfileService

logger = logging.getLogger("locallift.nap_service")


def _clean_str(s: Optional[str]) -> str:
    if not s:
        return ""
    # Normalize whitespace and lowercase
    return re.sub(r"\s+", " ", s.strip().lower())


def _clean_phone(p: Optional[str]) -> str:
    if not p:
        return ""
    digits = re.sub(r"[^\d]", "", p)
    # If 11 digits starting with 1 (US country code), strip 1 for standardized comparison
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


def _clean_address(a: Optional[str]) -> str:
    if not a:
        return ""
    norm = a.strip().lower()
    norm = re.sub(r"[,\.#]", " ", norm)
    # Standardize common address abbreviations and directional indicators (USPS standards)
    replacements = {
        r"\bstreet\b": "st",
        r"\bavenue\b": "ave",
        r"\broad\b": "rd",
        r"\bboulevard\b": "blvd",
        r"\bdrive\b": "dr",
        r"\bsuite\b": "ste",
        r"\bapartment\b": "apt",
        r"\blane\b": "ln",
        r"\bcourt\b": "ct",
        r"\bhighway\b": "hwy",
        r"\bparkway\b": "pkwy",
        r"\bcircle\b": "cir",
        r"\bplace\b": "pl",
        r"\bway\b": "way",
        r"\bbuilding\b": "bldg",
        r"\bfloor\b": "fl",
        r"\broom\b": "rm",
        r"\bunit\b": "unit",
        r"\bnorth\b": "n",
        r"\bsouth\b": "s",
        r"\beast\b": "e",
        r"\bwest\b": "w",
        r"\bnortheast\b": "ne",
        r"\bnorthwest\b": "nw",
        r"\bsoutheast\b": "se",
        r"\bsouthwest\b": "sw"
    }
    for pat, rep in replacements.items():
        norm = re.sub(pat, rep, norm)
    return re.sub(r"\s+", " ", norm).strip()


def _clean_url(u: Optional[str]) -> str:
    if not u:
        return ""
    norm = u.strip().lower()
    norm = re.sub(r"^https?://", "", norm)
    norm = re.sub(r"^www\.", "", norm)
    return norm.rstrip("/")


def _compare_field(expected: Optional[str], found: Optional[str], field_type: str = "text") -> str:
    if not found or not str(found).strip():
        return "missing"
    if not expected or not str(expected).strip():
        return "not_evaluated"

    if field_type == "phone":
        return "match" if _clean_phone(expected) == _clean_phone(found) else "mismatch"
    elif field_type == "address":
        exp_clean = _clean_address(expected)
        fnd_clean = _clean_address(found)
        if exp_clean == fnd_clean or (exp_clean and fnd_clean and (exp_clean in fnd_clean or fnd_clean in exp_clean)):
            return "match"
        return "mismatch"
    elif field_type == "website":
        return "match" if _clean_url(expected) == _clean_url(found) else "mismatch"
    
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

        # 1. Fetch exact project-bound GBP Profile
        gbp_res = await db.execute(
            select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id)
        )
        gbp_profile = gbp_res.scalars().first()

        # 2. Determine canonical reference source
        if gbp_profile and (gbp_profile.business_name or gbp_profile.phone or gbp_profile.address):
            canonical_source = "GOOGLE_BUSINESS_PROFILE"
            expected_name = gbp_profile.business_name
            expected_phone = gbp_profile.phone
            expected_address = gbp_profile.address
            expected_website = gbp_profile.website_url
            canonical_profile_data = {
                "source": "GOOGLE_BUSINESS_PROFILE",
                "business_name": gbp_profile.business_name,
                "primary_phone": gbp_profile.phone,
                "primary_address": gbp_profile.address,
                "city": gbp_profile.city or profile.city,
                "state": gbp_profile.state or profile.state,
                "postal_code": gbp_profile.postal_code or profile.postal_code,
                "country": gbp_profile.country or profile.country,
                "website": gbp_profile.website_url or profile.website
            }
        else:
            canonical_source = "PROJECT_USER_INPUT"
            expected_name = profile.business_name
            expected_phone = profile.primary_phone
            expected_address = profile.primary_address
            expected_website = profile.website
            canonical_profile_data = {
                "source": "PROJECT_USER_INPUT",
                "business_name": profile.business_name,
                "primary_phone": profile.primary_phone,
                "primary_address": profile.primary_address,
                "city": profile.city,
                "state": profile.state,
                "postal_code": profile.postal_code,
                "country": profile.country,
                "website": profile.website
            }

        comparisons: List[Dict[str, Any]] = []
        total_sources = 0
        consistent_sources = 0
        mismatch_sources = 0

        # If GBP is canonical, compare Project User Data against GBP
        if canonical_source == "GOOGLE_BUSINESS_PROFILE":
            total_sources += 1
            proj_name_st = _compare_field(expected_name, profile.business_name)
            proj_phone_st = _compare_field(expected_phone, profile.primary_phone, field_type="phone")
            proj_addr_st = _compare_field(expected_address, profile.primary_address, field_type="address")
            proj_web_st = _compare_field(expected_website, profile.website, field_type="website")

            is_proj_aligned = (
                any(s == "match" for s in [proj_name_st, proj_phone_st, proj_addr_st, proj_web_st]) and
                not any(s == "mismatch" for s in [proj_name_st, proj_phone_st, proj_addr_st, proj_web_st])
            )
            if is_proj_aligned:
                consistent_sources += 1
            else:
                mismatch_sources += 1

            proj_name_obj = {"expected": expected_name, "found": profile.business_name, "status": proj_name_st}
            proj_phone_obj = {"expected": expected_phone, "found": profile.primary_phone, "status": proj_phone_st}
            proj_addr_obj = {"expected": expected_address, "found": profile.primary_address, "status": proj_addr_st}
            proj_web_obj = {"expected": expected_website, "found": profile.website, "status": proj_web_st}

            comparisons.append({
                "source_type": "PROJECT_USER_INPUT",
                "source_name": "Project Settings / Profile",
                "listing_url": profile.website,
                "provenance": "PROJECT_USER_INPUT",
                "is_consistent": is_proj_aligned,
                "name": proj_name_obj,
                "phone": proj_phone_obj,
                "address": proj_addr_obj,
                "website": proj_web_obj,
                "fields": {
                    "business_name": proj_name_obj,
                    "phone": proj_phone_obj,
                    "address": proj_addr_obj,
                    "website": proj_web_obj
                }
            })
        elif gbp_profile and (gbp_profile.business_name or gbp_profile.phone or gbp_profile.address):
            # If Project User Input is canonical, compare GBP Profile against it
            total_sources += 1
            gbp_name_st = _compare_field(expected_name, gbp_profile.business_name)
            gbp_phone_st = _compare_field(expected_phone, gbp_profile.phone, field_type="phone")
            gbp_addr_st = _compare_field(expected_address, gbp_profile.address, field_type="address")
            gbp_web_st = _compare_field(expected_website, gbp_profile.website_url, field_type="website")

            is_gbp_aligned = (
                any(s == "match" for s in [gbp_name_st, gbp_phone_st, gbp_addr_st, gbp_web_st]) and
                not any(s == "mismatch" for s in [gbp_name_st, gbp_phone_st, gbp_addr_st, gbp_web_st])
            )
            if is_gbp_aligned:
                consistent_sources += 1
            else:
                mismatch_sources += 1

            gbp_name_obj = {"expected": expected_name, "found": gbp_profile.business_name, "status": gbp_name_st}
            gbp_phone_obj = {"expected": expected_phone, "found": gbp_profile.phone, "status": gbp_phone_st}
            gbp_addr_obj = {"expected": expected_address, "found": gbp_profile.address, "status": gbp_addr_st}
            gbp_web_obj = {"expected": expected_website, "found": gbp_profile.website_url, "status": gbp_web_st}

            comparisons.append({
                "source_type": "GOOGLE_BUSINESS_PROFILE",
                "source_name": "Google Business Profile",
                "listing_url": gbp_profile.website_url,
                "provenance": "GBP_CONNECTED",
                "is_consistent": is_gbp_aligned,
                "name": gbp_name_obj,
                "phone": gbp_phone_obj,
                "address": gbp_addr_obj,
                "website": gbp_web_obj,
                "fields": {
                    "business_name": gbp_name_obj,
                    "phone": gbp_phone_obj,
                    "address": gbp_addr_obj,
                    "website": gbp_web_obj
                }
            })

        # 3. Fetch Schema Records (Website Schema Markup)
        sch_res = await db.execute(
            select(SchemaRecord)
            .where(SchemaRecord.project_id == project_id)
            .order_by(SchemaRecord.id.desc())
        )
        schema_records = sch_res.scalars().all()

        for s in schema_records:
            stype = (s.schema_type or "").lower()
            if any(k in stype for k in ["localbusiness", "organization", "store", "restaurant", "dentist", "medicalbusiness", "professionalservice"]):
                sch_data = s.raw_json_ld if isinstance(s.raw_json_ld, dict) else {}
                if not sch_data and isinstance(s.raw_json_ld, str):
                    try:
                        sch_data = json.loads(s.raw_json_ld)
                    except Exception:
                        sch_data = {}

                found_s_name = sch_data.get("name")
                found_s_phone = sch_data.get("telephone") or sch_data.get("phone")
                addr_field = sch_data.get("address")
                if isinstance(addr_field, dict):
                    street = addr_field.get("streetAddress", "")
                    locality = addr_field.get("addressLocality", "")
                    region = addr_field.get("addressRegion", "")
                    postal = addr_field.get("postalCode", "")
                    found_s_addr = f"{street} {locality} {region} {postal}".strip() or None
                elif isinstance(addr_field, str):
                    found_s_addr = addr_field
                else:
                    found_s_addr = None

                found_s_web = sch_data.get("url")

                if found_s_name or found_s_phone or found_s_addr or found_s_web:
                    total_sources += 1
                    s_name_st = _compare_field(expected_name, found_s_name)
                    s_phone_st = _compare_field(expected_phone, found_s_phone, field_type="phone")
                    s_addr_st = _compare_field(expected_address, found_s_addr, field_type="address")
                    s_web_st = _compare_field(expected_website, found_s_web, field_type="website")

                    is_s_aligned = (
                        any(st == "match" for st in [s_name_st, s_phone_st, s_addr_st, s_web_st]) and
                        not any(st == "mismatch" for st in [s_name_st, s_phone_st, s_addr_st, s_web_st])
                    )
                    if is_s_aligned:
                        consistent_sources += 1
                    else:
                        mismatch_sources += 1

                    s_name_obj = {"expected": expected_name, "found": found_s_name, "status": s_name_st}
                    s_phone_obj = {"expected": expected_phone, "found": found_s_phone, "status": s_phone_st}
                    s_addr_obj = {"expected": expected_address, "found": found_s_addr, "status": s_addr_st}
                    s_web_obj = {"expected": expected_website, "found": found_s_web, "status": s_web_st}

                    comparisons.append({
                        "source_type": "WEBSITE_SCHEMA",
                        "source_name": f"Website Schema ({s.schema_type})",
                        "listing_url": s.page_url or profile.website,
                        "provenance": "WEBSITE_EXTRACTED",
                        "is_consistent": is_s_aligned,
                        "name": s_name_obj,
                        "phone": s_phone_obj,
                        "address": s_addr_obj,
                        "website": s_web_obj,
                        "fields": {
                            "business_name": s_name_obj,
                            "phone": s_phone_obj,
                            "address": s_addr_obj,
                            "website": s_web_obj
                        }
                    })
                    break  # Use primary business schema

        # 4. Fetch Citations
        cit_res = await db.execute(select(Citation).where(Citation.project_id == project_id))
        citations = cit_res.scalars().all()

        # Evaluate Citations against Canonical Source
        for c in citations:
            total_sources += 1
            name_status = _compare_field(expected_name, c.found_name) if c.found_name else "missing"
            phone_status = _compare_field(expected_phone, c.found_phone, field_type="phone") if c.found_phone else "missing"
            addr_status = _compare_field(expected_address, c.found_address, field_type="address") if c.found_address else "missing"
            web_status = _compare_field(expected_website, c.found_website, field_type="website") if c.found_website else "missing"

            # Check if citation has observed values that match
            observed_statuses = [s for s in [name_status, phone_status, addr_status, web_status] if s not in ["missing", "not_evaluated"]]
            if observed_statuses:
                is_aligned = all(s == "match" for s in observed_statuses)
            else:
                # If no raw found fields were stored, use explicit nap_status
                is_aligned = (c.nap_status == "consistent" and (c.status or "").lower() in ["approved", "listed"])

            if is_aligned:
                consistent_sources += 1
            else:
                mismatch_sources += 1

            cit_name_obj = {"expected": expected_name, "found": c.found_name, "status": name_status}
            cit_phone_obj = {"expected": expected_phone, "found": c.found_phone, "status": phone_status}
            cit_addr_obj = {"expected": expected_address, "found": c.found_address, "status": addr_status}
            cit_web_obj = {"expected": expected_website, "found": c.found_website, "status": web_status}

            comparisons.append({
                "source_type": "DIRECTORY_CITATION",
                "source_name": c.source_name or c.domain or "Directory Citation",
                "listing_url": c.listing_url,
                "provenance": c.citation_type or c.verification_status or "DIRECTORY_CITATION",
                "is_consistent": is_aligned,
                "name": cit_name_obj,
                "phone": cit_phone_obj,
                "address": cit_addr_obj,
                "website": cit_web_obj,
                "fields": {
                    "business_name": cit_name_obj,
                    "phone": cit_phone_obj,
                    "address": cit_addr_obj,
                    "website": cit_web_obj
                }
            })

        nap_score = round((consistent_sources / total_sources) * 100) if total_sources > 0 else None

        return {
            "project_id": project_id,
            "canonical_source": canonical_source,
            "canonical_profile": canonical_profile_data,
            "total_sources_evaluated": total_sources,
            "total_sources_checked": total_sources,
            "consistent_sources_count": consistent_sources,
            "consistent_sources": consistent_sources,
            "mismatch_sources_count": mismatch_sources,
            "mismatch_sources": mismatch_sources,
            "nap_consistency_pct": nap_score,
            "nap_score": nap_score,
            "score_available": nap_score is not None,
            "comparisons": comparisons
        }

