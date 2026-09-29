import json
import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.gbp import GoogleAccount, GoogleBusinessProfile, GBPChange
from app.models.project import Project, Location
from app.models.local_seo import Review
from app.core.security import decrypt_token
from app.services.google.gbp_client import GoogleBusinessProfileClient

from app.models.connections import GoogleConnection
from app.services.category_taxonomy import CategoryTaxonomy

logger = logging.getLogger("locallift.google.sync")

class GBPSyncService:
    @classmethod
    async def sync_project_gbp(
        cls,
        project_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Executes strict project-bound Google Business Profile synchronization.
        Traceable lookup chain:
        Project -> Bound GoogleBusinessProfile -> GoogleConnection -> Google API -> Exact Location Resource.
        Never syncs unrelated locations into this project.
        """
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalars().first()
        if not project:
            raise ValueError(f"Project {project_id} not found.")

        # 1. Fetch exact project-bound GBP profile
        prof_res = await db.execute(
            select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id)
        )
        profile = prof_res.scalars().first()
        if not profile or not profile.location_resource_name:
            return {
                "status": "not_connected",
                "error": "No bound Google Business Profile found for this project.",
                "profiles_synced": 0,
                "changes_detected": 0
            }

        # 2. Resolve Google OAuth Connection
        from app.services.google.connections_service import GoogleConnectionsService
        conn = None
        if profile.google_connection_id:
            conn_res = await db.execute(select(GoogleConnection).where(GoogleConnection.id == profile.google_connection_id))
            conn = conn_res.scalars().first()

        if not conn:
            conn = await GoogleConnectionsService.get_connection_for_service(project.organization_id, "business_profile", db)

        if not conn or not conn.access_token:
            profile.status = "AUTH_EXPIRED"
            profile.sync_status = "failed"
            profile.sync_error = "Google Business Profile connection is missing or expired."
            await db.commit()
            return {
                "status": "error",
                "error": profile.sync_error,
                "profiles_synced": 0,
                "changes_detected": 0
            }

        try:
            plain_access_token = await GoogleConnectionsService.get_valid_access_token(conn, db)
        except Exception as te:
            profile.status = "AUTH_EXPIRED"
            profile.sync_status = "failed"
            profile.sync_error = f"Google token refresh failed: {str(te)}"
            await db.commit()
            return {
                "status": "error",
                "error": profile.sync_error,
                "profiles_synced": 0,
                "changes_detected": 0
            }

        plain_refresh_token = decrypt_token(conn.refresh_token) if conn.refresh_token else None
        client = GoogleBusinessProfileClient(
            access_token=plain_access_token,
            refresh_token=plain_refresh_token,
            token_expiry=conn.token_expiry
        )

        loc_name = profile.location_resource_name
        detected_changes_count = 0

        try:
            # 3. Fetch exact location details from Google API
            loc_data = await client.fetch_location(loc_name)
            if not loc_data:
                logger.warning(f"[GBP_SYNC] Location {loc_name} not returned by Google API. Updating status.")
                profile.sync_status = "warning"
                profile.sync_error = "Location details could not be retrieved from Google API."
            else:
                title = loc_data.get("title") or profile.business_name
                categories_data = loc_data.get("categories", {})
                primary_cat = CategoryTaxonomy.normalize_category_name(
                    categories_data.get("primaryCategory", {}).get("displayName", profile.primary_category)
                )
                more_cats = [c.get("displayName") for c in categories_data.get("additionalCategories", []) if c.get("displayName")]

                address_str = GoogleBusinessProfileClient.parse_storefront_address(loc_data.get("storefrontAddress"))
                phone_numbers = loc_data.get("phoneNumbers", {})
                phone_str = phone_numbers.get("primaryPhone") or profile.phone
                website_uri = loc_data.get("websiteUri") or profile.website_url
                regular_hours = loc_data.get("regularHours", profile.regular_hours or {})

                # Detect changes and log GBPChange audit records
                changes_to_log = []
                if primary_cat and profile.primary_category != primary_cat:
                    changes_to_log.append(("Primary Category", profile.primary_category, primary_cat))
                    profile.primary_category = primary_cat

                if address_str and profile.address != address_str:
                    changes_to_log.append(("Address", profile.address, address_str))
                    profile.address = address_str

                if phone_str and profile.phone != phone_str:
                    changes_to_log.append(("Phone", profile.phone, phone_str))
                    profile.phone = phone_str

                if website_uri and profile.website_url != website_uri:
                    changes_to_log.append(("Website URL", profile.website_url, website_uri))
                    profile.website_url = website_uri

                for field_name, old_val, new_val in changes_to_log:
                    change = GBPChange(
                        gbp_profile_id=profile.id,
                        field_name=field_name,
                        old_value=str(old_val),
                        new_value=str(new_val),
                        detected_at=datetime.now(timezone.utc)
                    )
                    db.add(change)
                    detected_changes_count += 1

                profile.business_name = title
                profile.additional_categories = more_cats
                profile.regular_hours = regular_hours
                profile.opening_hours = regular_hours

            # 4. Fetch performance metrics for this exact location
            metrics = await client.fetch_location_performance(loc_name)
            profile.search_impressions = metrics.get("search_impressions", profile.search_impressions)
            profile.maps_impressions = metrics.get("maps_impressions", profile.maps_impressions)
            profile.call_clicks = metrics.get("call_clicks", profile.call_clicks)
            profile.website_clicks = metrics.get("website_clicks", profile.website_clicks)
            profile.direction_requests = metrics.get("direction_requests", profile.direction_requests)

            # 5. Fetch reviews for this exact location with real pagination and external_review_id
            reviews_synced_count = 0
            acc_name = profile.account_resource_name or "accounts/default"
            review_res = await client.fetch_location_reviews(acc_name, loc_name)
            if review_res.get("success"):
                reviews_data = review_res.get("reviews", [])
                seen_gbp_ext_ids = set()
                for rev in reviews_data:
                    raw_ext_id = rev.get("external_review_id") or rev.get("review_id") or rev.get("name")
                    author = rev.get("author_name") or "Google Customer"
                    rev_comment = rev.get("review_text") or ""
                    rev_date = rev.get("review_date") or datetime.now(timezone.utc)
                    up_date = rev.get("update_time")

                    if raw_ext_id:
                        ext_id = str(raw_ext_id)
                    else:
                        sig_str = f"{author}:{rev_comment}:{rev_date.isoformat() if hasattr(rev_date, 'isoformat') else rev_date}"
                        ext_id = f"gbp_fallback_{hashlib.sha256(sig_str.encode('utf-8')).hexdigest()[:24]}"

                    seen_gbp_ext_ids.add(ext_id)

                    # Lookup review by strict logical identity: (project_id, source, external_review_id)
                    stmt = select(Review).where(
                        Review.project_id == project_id,
                        Review.source == "Google Business Profile",
                        Review.external_review_id == ext_id
                    )
                    existing_rev_res = await db.execute(stmt)
                    existing_rev = existing_rev_res.scalars().first()

                    rating_val = rev.get("rating")
                    sentiment_val = None
                    if rating_val is not None:
                        sentiment_val = "positive" if rating_val >= 4 else ("neutral" if rating_val == 3 else "negative")

                    if existing_rev:
                        existing_rev.rating = rating_val
                        existing_rev.review_text = rev_comment
                        existing_rev.author_name = author
                        existing_rev.author_photo_url = rev.get("author_photo_url")
                        existing_rev.review_date = rev_date
                        existing_rev.update_time = up_date
                        existing_rev.collected_at = datetime.now(timezone.utc)
                        existing_rev.collection_status = "active"
                        if rev.get("response_text"):
                            existing_rev.response_text = rev["response_text"]
                            existing_rev.response_status = rev.get("response_status", "published")
                            existing_rev.response_date = datetime.now(timezone.utc)
                        if sentiment_val is not None:
                            existing_rev.sentiment = sentiment_val
                    else:
                        new_rev = Review(
                            project_id=project_id,
                            external_review_id=ext_id,
                            source="Google Business Profile",
                            author_name=author,
                            author_photo_url=rev.get("author_photo_url"),
                            rating=rating_val,
                            review_text=rev_comment,
                            review_date=rev_date,
                            update_time=up_date,
                            response_text=rev.get("response_text"),
                            response_status=rev.get("response_status", "unanswered"),
                            response_date=datetime.now(timezone.utc) if rev.get("response_text") else None,
                            sentiment=sentiment_val,
                            collected_at=datetime.now(timezone.utc),
                            raw_provider_reference=str(raw_ext_id or ""),
                            collection_status="active"
                        )
                        db.add(new_rev)
                    reviews_synced_count += 1

                # Mark disappeared GBP reviews if any
                if seen_gbp_ext_ids:
                    old_gbp_stmt = select(Review).where(
                        Review.project_id == project_id,
                        Review.source == "Google Business Profile",
                        Review.external_review_id.not_in(seen_gbp_ext_ids)
                    )
                    old_gbp_res = await db.execute(old_gbp_stmt)
                    for old_r in old_gbp_res.scalars().all():
                        old_r.collection_status = "NO_LONGER_RETURNED_BY_PROVIDER"

            profile.status = "CONNECTED"
            profile.sync_status = "synced"
            profile.sync_error = None
            profile.last_synced_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(profile)

            logger.info(f"[GBP_SYNC] Project {project_id} synced location {loc_name} successfully.")
            return {
                "status": "synced",
                "project_id": project_id,
                "location_resource_name": loc_name,
                "profiles_synced": 1,
                "changes_detected": detected_changes_count,
                "reviews_synced": reviews_synced_count,
                "last_synced_at": profile.last_synced_at
            }

        except Exception as e:
            logger.error(f"[GBP_SYNC] Sync error for project {project_id} (location {loc_name}): {e}")
            profile.sync_status = "error"
            profile.sync_error = str(e)
            await db.commit()
            raise

    @classmethod
    async def sync_google_account(
        cls,
        google_account: GoogleAccount,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Legacy adapter that handles account resolution without recursive delegation.
        """
        if not google_account:
            return {
                "status": "not_connected",
                "error": "No Google Account provided",
                "profiles_synced": 0,
                "changes_detected": 0
            }

        if google_account.project_id:
            prof_res = await db.execute(
                select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == google_account.project_id)
            )
            profile = prof_res.scalars().first()
            if profile and profile.location_resource_name:
                return await cls.sync_project_gbp(google_account.project_id, db)
            return {
                "status": "not_connected",
                "error": "Google Account is not bound to a specific Google Business Profile location resource.",
                "profiles_synced": 0,
                "changes_detected": 0
            }

        return {
            "status": "synced",
            "profiles_synced": 0,
            "changes_detected": 0,
            "last_synced_at": datetime.now(timezone.utc)
        }


sync_project_gbp = GBPSyncService.sync_project_gbp

