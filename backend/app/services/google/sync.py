import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.gbp import GoogleAccount, GoogleBusinessProfile, GBPChange
from app.models.project import Project, Location
from app.services.google.gbp_client import GoogleBusinessProfileClient

logger = logging.getLogger("locallift.google.sync")

class GBPSyncService:
    @classmethod
    async def sync_google_account(
        cls,
        google_account: GoogleAccount,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Idempotently synchronizes Google Business Profile accounts and locations.
        Discovers live locations, creates/updates GoogleBusinessProfile records,
        detects profile modifications and logs GBPChange audit entries.
        """
        client = GoogleBusinessProfileClient(
            access_token=google_account.access_token or "",
            refresh_token=google_account.refresh_token,
            token_expiry=google_account.token_expiry
        )

        try:
            # 1. Discover Accounts
            accounts = await client.list_accounts()
            if not accounts:
                # If no accounts returned via Account Management API, try direct search or default
                logger.info("No explicit GBP accounts returned. Checking default account access.")
                accounts = [{"name": "accounts/default", "accountName": google_account.account_email}]

            synced_profiles_count = 0
            detected_changes_count = 0

            # 2. Discover and sync locations for each account
            for acc in accounts:
                acc_name = acc.get("name", "")
                locations = await client.list_locations(acc_name)

                for loc in locations:
                    loc_name = loc.get("name", "")  # format: 'locations/12345...'
                    title = loc.get("title", "") or loc.get("storefrontAddress", {}).get("organization", "Local Business")
                    
                    # Categories
                    categories_data = loc.get("categories", {})
                    primary_cat = categories_data.get("primaryCategory", {}).get("displayName", "Local Business")
                    more_cats = [c.get("displayName") for c in categories_data.get("additionalCategories", []) if c.get("displayName")]

                    # Address & Phone
                    address_str = GoogleBusinessProfileClient.parse_storefront_address(loc.get("storefrontAddress"))
                    phone_numbers = loc.get("phoneNumbers", {})
                    phone_str = phone_numbers.get("primaryPhone") or ""
                    website_uri = loc.get("websiteUri", "")

                    # Hours
                    regular_hours = loc.get("regularHours", {})

                    # Fetch live performance metrics
                    metrics = await client.fetch_location_performance(loc_name)

                    # 3. Find existing profile record or create a new one (Idempotent lookup)
                    prof_res = await db.execute(
                        select(GoogleBusinessProfile).where(
                            GoogleBusinessProfile.google_account_id == google_account.id,
                            (GoogleBusinessProfile.location_name == loc_name) | (GoogleBusinessProfile.business_name == title)
                        )
                    )
                    profile = prof_res.scalars().first()

                    if not profile:
                        # Create new profile
                        profile = GoogleBusinessProfile(
                            google_account_id=google_account.id,
                            account_id=acc_name,
                            location_name=loc_name,
                            business_name=title,
                            primary_category=primary_cat,
                            additional_categories=more_cats,
                            address=address_str,
                            phone=phone_str,
                            website_url=website_uri,
                            opening_hours=regular_hours,
                            completeness_score=85,
                            is_verified=True,
                            search_impressions=metrics.get("search_impressions", 0),
                            maps_impressions=metrics.get("maps_impressions", 0),
                            call_clicks=metrics.get("call_clicks", 0),
                            website_clicks=metrics.get("website_clicks", 0),
                            direction_requests=metrics.get("direction_requests", 0),
                            last_synced_at=datetime.now(timezone.utc)
                        )
                        db.add(profile)
                        await db.flush()
                        synced_profiles_count += 1
                    else:
                        # 4. Detect changes and log GBPChange records
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

                        # Update profile details & metrics
                        profile.location_name = loc_name
                        profile.account_id = acc_name
                        profile.business_name = title
                        profile.additional_categories = more_cats
                        profile.opening_hours = regular_hours
                        profile.search_impressions = metrics.get("search_impressions", profile.search_impressions)
                        profile.maps_impressions = metrics.get("maps_impressions", profile.maps_impressions)
                        profile.call_clicks = metrics.get("call_clicks", profile.call_clicks)
                        profile.website_clicks = metrics.get("website_clicks", profile.website_clicks)
                        profile.direction_requests = metrics.get("direction_requests", profile.direction_requests)
                        profile.last_synced_at = datetime.now(timezone.utc)
                        synced_profiles_count += 1

            # 5. If access token was refreshed during the sync, persist updated tokens
            if client.token_refreshed:
                google_account.access_token = client.access_token
                google_account.token_expiry = client.token_expiry

            await db.commit()

            return {
                "status": "synced",
                "profiles_synced": synced_profiles_count,
                "changes_detected": detected_changes_count,
                "last_synced_at": datetime.now(timezone.utc)
            }

        except Exception as e:
            logger.error(f"GBP synchronization failed for account {google_account.id}: {e}")
            raise
