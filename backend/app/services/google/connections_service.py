import re
import logging
import httpx

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.connections import (
    GoogleConnection,
    GoogleAdsAccount,
    GoogleSearchConsoleProperty,
    GoogleAnalyticsProperty
)
from app.models.project import Project, Location, Website
from app.models.gbp import GoogleAccount, GoogleBusinessProfile
from app.services.google.oauth import GoogleOAuthService
from app.services.google.gbp_client import GoogleBusinessProfileClient
from app.services.category_taxonomy import CategoryTaxonomy

logger = logging.getLogger("locallift.google.connections")

class GoogleConnectionsService:
    @classmethod
    async def get_connection_for_org(
        cls,
        organization_id: int,
        db: AsyncSession
    ) -> Optional[GoogleConnection]:
        result = await db.execute(
            select(GoogleConnection)
            .options(
                selectinload(GoogleConnection.ads_accounts),
                selectinload(GoogleConnection.search_console_properties),
                selectinload(GoogleConnection.analytics_properties)
            )
            .where(GoogleConnection.organization_id == organization_id)
            .order_by(GoogleConnection.id.desc())
        )
        return result.scalars().first()

    @classmethod
    async def save_connection_tokens(
        cls,
        organization_id: int,
        user_id: int,
        token_data: Dict[str, Any],
        db: AsyncSession,
        project_id: Optional[int] = None
    ) -> GoogleConnection:
        """
        Saves or updates the organization's Google OAuth connection.
        Ensures idempotency and updates access/refresh tokens securely.
        """
        existing = await cls.get_connection_for_org(organization_id, db)
        email = token_data.get("email") or "connected-user@gmail.com"
        scopes = token_data.get("scopes", [])
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        token_expiry = token_data.get("token_expiry")

        if existing:
            existing.account_email = email
            existing.access_token = access_token
            if refresh_token:
                existing.refresh_token = refresh_token
            existing.token_expiry = token_expiry
            existing.scopes = scopes
            existing.status = "connected"
            existing.sync_error = None
            existing.last_sync_at = datetime.now(timezone.utc)
            if project_id:
                existing.project_id = project_id
            conn = existing
        else:
            conn = GoogleConnection(
                organization_id=organization_id,
                project_id=project_id,
                account_email=email,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expiry=token_expiry,
                scopes=scopes,
                status="connected",
                last_sync_at=datetime.now(timezone.utc)
            )
            db.add(conn)

        await db.flush()

        # If project_id is provided, also sync legacy GoogleAccount relation
        if project_id:
            acc_res = await db.execute(
                select(GoogleAccount).where(GoogleAccount.project_id == project_id)
            )
            g_acc = acc_res.scalars().first()
            if g_acc:
                g_acc.account_email = email
                g_acc.access_token = access_token
                if refresh_token:
                    g_acc.refresh_token = refresh_token
                g_acc.token_expiry = token_expiry
                g_acc.scopes = scopes
                g_acc.is_connected = True
            else:
                db.add(GoogleAccount(
                    project_id=project_id,
                    account_email=email,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_expiry=token_expiry,
                    scopes=scopes,
                    is_connected=True
                ))

        await db.commit()
        return conn

    @classmethod
    async def discover_and_sync_all_resources(
        cls,
        connection: GoogleConnection,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Discovers all accessible Google services for the connected account:
        1. Google Business Profile locations
        2. Google Ads accounts
        3. Google Search Console verified sites
        4. Google Analytics 4 properties
        """
        if not connection.access_token:
            return {"error": "No valid access token available for synchronization."}

        access_token = connection.access_token
        refresh_token = connection.refresh_token
        expiry = connection.token_expiry

        # 1. Discover GBP Locations
        gbp_client = GoogleBusinessProfileClient(access_token, refresh_token, expiry)
        discovered_gbp: List[Dict[str, Any]] = []
        try:
            accounts = await gbp_client.list_accounts()
            for acc in accounts:
                acc_name = acc.get("name")
                if not acc_name:
                    continue
                locs = await gbp_client.list_locations(acc_name)
                for l in locs:
                    raw_addr = l.get("storefrontAddress", {})
                    addr_lines = raw_addr.get("addressLines", [])
                    city = raw_addr.get("locality", "")
                    state = raw_addr.get("administrativeArea", "")
                    full_addr = ", ".join(addr_lines + ([city] if city else []) + ([state] if state else []))
                    
                    cat = l.get("categories", {}).get("primaryCategory", {}).get("displayName", "Local Business")
                    web = l.get("websiteUri")
                    phone = l.get("phoneNumbers", {}).get("primaryPhone")
                    
                    discovered_gbp.append({
                        "account_id": acc_name,
                        "location_id": l.get("name", ""),
                        "business_name": l.get("title") or "Unnamed Location",
                        "primary_category": CategoryTaxonomy.normalize_category_name(cat),
                        "address": full_addr or None,
                        "phone": phone or None,
                        "website_url": web or None,
                        "is_verified": l.get("profile", {}).get("isVerified", True)
                    })
        except Exception as e:
            logger.warning(f"GBP discovery error: {e}")

        # 2. Discover Google Search Console Properties
        discovered_gsc: List[Dict[str, Any]] = []
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                gsc_resp = await client.get(
                    "https://www.googleapis.com/webmasters/v3/sites",
                    headers=headers
                )
                if gsc_resp.status_code == 200:
                    entries = gsc_resp.json().get("siteEntry", [])
                    for s in entries:
                        url = s.get("siteUrl", "")
                        perm = s.get("permissionLevel", "siteOwner")
                        if url:
                            discovered_gsc.append({"site_url": url, "permission_level": perm})
        except Exception as e:
            logger.warning(f"Search Console discovery error: {e}")

        # 3. Discover Google Ads Accounts
        discovered_ads: List[Dict[str, Any]] = []
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                ads_resp = await client.get(
                    "https://googleads.googleapis.com/v17/customers:listAccessibleCustomers",
                    headers=headers
                )
                if ads_resp.status_code == 200:
                    res_names = ads_resp.json().get("resourceNames", [])
                    for rn in res_names:
                        cid = rn.replace("customers/", "")
                        discovered_ads.append({
                            "customer_id": cid,
                            "name": f"Google Ads ({cid})",
                            "status": "ENABLED"
                        })
        except Exception as e:
            logger.warning(f"Google Ads discovery error: {e}")

        # 4. Discover GA4 Properties
        discovered_ga4: List[Dict[str, Any]] = []
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                ga_resp = await client.get(
                    "https://analyticsadmin.googleapis.com/v1beta/accountSummaries",
                    headers=headers
                )
                if ga_resp.status_code == 200:
                    summaries = ga_resp.json().get("accountSummaries", [])
                    for acc in summaries:
                        acc_title = acc.get("displayName", "GA Account")
                        for prop in acc.get("propertySummaries", []):
                            p_id = prop.get("property", "").replace("properties/", "")
                            p_name = prop.get("displayName", f"GA4 Property {p_id}")
                            discovered_ga4.append({
                                "property_id": p_id,
                                "display_name": p_name,
                                "account_name": acc_title
                            })
        except Exception as e:
            logger.warning(f"Google Analytics discovery error: {e}")

        # Idempotent persistence of discovered properties
        # GSC
        existing_gsc = {p.site_url: p for p in connection.search_console_properties}
        for s in discovered_gsc:
            if s["site_url"] not in existing_gsc:
                db.add(GoogleSearchConsoleProperty(
                    connection_id=connection.id,
                    site_url=s["site_url"],
                    permission_level=s["permission_level"],
                    is_linked=True
                ))

        # Ads
        existing_ads = {a.customer_id: a for a in connection.ads_accounts}
        for a in discovered_ads:
            if a["customer_id"] not in existing_ads:
                db.add(GoogleAdsAccount(
                    connection_id=connection.id,
                    customer_id=a["customer_id"],
                    name=a["name"],
                    status=a["status"],
                    is_linked=True
                ))

        # GA4
        existing_ga4 = {g.property_id: g for g in connection.analytics_properties}
        for g in discovered_ga4:
            if g["property_id"] not in existing_ga4:
                db.add(GoogleAnalyticsProperty(
                    connection_id=connection.id,
                    property_id=g["property_id"],
                    display_name=g["display_name"],
                    account_name=g["account_name"],
                    is_linked=True
                ))

        connection.last_sync_at = datetime.now(timezone.utc)
        connection.sync_error = None
        await db.commit()

        return {
            "gbp_locations": discovered_gbp,
            "search_console": discovered_gsc,
            "ads_accounts": discovered_ads,
            "analytics_properties": discovered_ga4
        }

    @classmethod
    async def import_resources_to_locallift(
        cls,
        organization_id: int,
        selected_gbp: List[Dict[str, Any]],
        selected_gsc_urls: List[str],
        db: AsyncSession,
        target_project_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Auto-creates LocalLift projects, locations, and websites from discovered Google resources.
        Prevents duplicate records using domain and name deduplication.
        """
        created_projects = 0
        imported_locations = 0
        imported_websites = 0

        # Import GBP Locations
        for loc_data in selected_gbp:
            biz_name = loc_data.get("business_name") or "Imported Business"
            raw_url = loc_data.get("website_url") or ""
            domain = raw_url.replace("https://", "").replace("http://", "").rstrip("/").split("/")[0]
            if not domain:
                clean_slug = re.sub(r'[^a-zA-Z0-9-]', '', biz_name.lower().replace(' ', '-'))
                domain = f"{clean_slug[:40]}.local"


            cat = CategoryTaxonomy.normalize_category_name(loc_data.get("primary_category"))

            # Check if project already exists for this domain in org
            proj_res = await db.execute(
                select(Project).where(
                    Project.organization_id == organization_id,
                    Project.domain == domain
                )
            )
            proj = proj_res.scalars().first()

            if not proj:
                proj = Project(
                    organization_id=organization_id,
                    name=biz_name,
                    domain=domain,
                    primary_category=cat,
                    additional_categories=[],
                    country="United States",
                    health_score=75
                )
                db.add(proj)
                await db.flush()
                created_projects += 1

                # Create website
                db.add(Website(
                    project_id=proj.id,
                    url=f"https://{domain}" if not raw_url else raw_url,
                    status="ready"
                ))
                imported_websites += 1

            # Check if location already exists
            existing_locs_res = await db.execute(
                select(Location).where(Location.project_id == proj.id)
            )
            existing_locs = existing_locs_res.scalars().all()
            loc_name = loc_data.get("business_name") or "Main Location"

            if not any(l.name == loc_name for l in existing_locs):
                db.add(Location(
                    project_id=proj.id,
                    name=loc_name,
                    address=loc_data.get("address"),
                    phone=loc_data.get("phone"),
                    country="United States"
                ))
                imported_locations += 1

        # Import Search Console Websites
        for gsc_url in selected_gsc_urls:
            clean_dom = gsc_url.replace("https://", "").replace("http://", "").replace("sc-domain:", "").rstrip("/")
            if not clean_dom:
                continue

            proj_res = await db.execute(
                select(Project).where(
                    Project.organization_id == organization_id,
                    Project.domain == clean_dom
                )
            )
            proj = proj_res.scalars().first()

            if not proj:
                name_guess = clean_dom.split(".")[0].capitalize()
                proj = Project(
                    organization_id=organization_id,
                    name=name_guess,
                    domain=clean_dom,
                    primary_category="Local Business",
                    additional_categories=[],
                    country="United States",
                    health_score=70
                )
                db.add(proj)
                await db.flush()
                created_projects += 1

                db.add(Website(
                    project_id=proj.id,
                    url=gsc_url if gsc_url.startswith("http") else f"https://{clean_dom}",
                    status="ready"
                ))
                imported_websites += 1

        await db.commit()
        return {
            "success": True,
            "created_projects_count": created_projects,
            "imported_locations_count": imported_locations,
            "imported_websites_count": imported_websites,
            "message": f"Successfully imported {created_projects} project(s), {imported_locations} location(s), and {imported_websites} website(s)."
        }

    @classmethod
    async def disconnect(
        cls,
        organization_id: int,
        db: AsyncSession
    ) -> bool:
        """
        Safely disconnects Google integration for the organization.
        Preserves historical LocalLift audit/project data.
        """
        conn = await cls.get_connection_for_org(organization_id, db)
        if not conn:
            return False

        conn.status = "disconnected"
        conn.access_token = None
        conn.refresh_token = None
        conn.sync_error = None
        conn.last_sync_at = datetime.now(timezone.utc)
        await db.commit()
        return True
