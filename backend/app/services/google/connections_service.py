import re
import logging
import httpx
import uuid

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.security import encrypt_token, decrypt_token, is_plaintext_token
from app.models.connections import (
    GoogleConnection,
    GoogleAdsAccount,
    GoogleSearchConsoleProperty,
    GoogleAnalyticsProperty
)
from app.models.project import Project, Location, Website
from app.models.gbp import GoogleAccount, GoogleBusinessProfile
from app.services.google.oauth import GoogleOAuthCore
from app.services.google.gbp_client import GoogleBusinessProfileClient
from app.services.category_taxonomy import CategoryTaxonomy

from app.services.google.nap_matcher import NAPMatcher

logger = logging.getLogger("locallift.google.connections")

VALID_SERVICES = ["business_profile", "google_ads", "search_console", "analytics"]


class GoogleConnectionsService:
    @classmethod
    async def get_connection_for_service(
        cls,
        organization_id: int,
        service: str,
        db: AsyncSession
    ) -> Optional[GoogleConnection]:
        """
        Retrieves the active GoogleConnection record for a specific organization and Google service.
        """
        result = await db.execute(
            select(GoogleConnection)
            .options(
                selectinload(GoogleConnection.ads_accounts),
                selectinload(GoogleConnection.search_console_properties),
                selectinload(GoogleConnection.analytics_properties)
            )
            .where(
                GoogleConnection.organization_id == organization_id,
                GoogleConnection.service == service
            )
            .order_by(GoogleConnection.id.desc())
        )
        return result.scalars().first()

    @classmethod
    async def get_all_connections_for_org(
        cls,
        organization_id: int,
        db: AsyncSession
    ) -> Dict[str, Optional[GoogleConnection]]:
        """
        Retrieves a map of all 4 service connection records for the organization.
        """
        result = await db.execute(
            select(GoogleConnection)
            .options(
                selectinload(GoogleConnection.ads_accounts),
                selectinload(GoogleConnection.search_console_properties),
                selectinload(GoogleConnection.analytics_properties)
            )
            .where(GoogleConnection.organization_id == organization_id)
        )
        connections = result.scalars().all()
        conn_map: Dict[str, Optional[GoogleConnection]] = {s: None for s in VALID_SERVICES}
        for conn in connections:
            if conn.service in conn_map:
                conn_map[conn.service] = conn
        return conn_map

    @classmethod
    async def get_connection_for_org(
        cls,
        organization_id: int,
        db: AsyncSession,
        service: Optional[str] = None
    ) -> Optional[GoogleConnection]:
        """
        Legacy fallback helper. Defaults to business_profile if service not provided.
        """
        target_service = service or "business_profile"
        return await cls.get_connection_for_service(organization_id, target_service, db)

    @classmethod
    async def save_connection_tokens(
        cls,
        organization_id: int,
        user_id: int,
        token_data: Dict[str, Any],
        db: AsyncSession,
        service: str = "business_profile",
        project_id: Optional[int] = None
    ) -> GoogleConnection:
        """
        Saves or updates the service-specific Google OAuth connection with encrypted tokens.
        Strictly isolated per service (business_profile, google_ads, search_console, analytics).
        """
        if service not in VALID_SERVICES:
            raise ValueError(f"Invalid service '{service}' for connection persistence.")

        existing = await cls.get_connection_for_service(organization_id, service, db)
        email = token_data.get("account_email") or token_data.get("email") or "connected-user@gmail.com"
        scopes = token_data.get("scopes", [])
        raw_access_token = token_data.get("access_token")
        raw_refresh_token = token_data.get("refresh_token")
        token_expiry = token_data.get("token_expiry")

        # Encrypt tokens before storing in database
        enc_access_token = encrypt_token(raw_access_token)
        enc_refresh_token = encrypt_token(raw_refresh_token)

        if existing:
            existing.account_email = email
            existing.access_token = enc_access_token
            if raw_refresh_token:
                existing.refresh_token = enc_refresh_token
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
                service=service,
                account_email=email,
                access_token=enc_access_token,
                refresh_token=enc_refresh_token,
                token_expiry=token_expiry,
                scopes=scopes,
                status="connected",
                last_sync_at=datetime.now(timezone.utc)
            )
            db.add(conn)

        await db.flush()

        # Sync project GoogleAccount relation for business_profile service
        if service == "business_profile" and project_id:
            acc_res = await db.execute(
                select(GoogleAccount).where(GoogleAccount.project_id == project_id)
            )
            g_acc = acc_res.scalars().first()
            if g_acc:
                g_acc.account_email = email
                g_acc.access_token = enc_access_token
                if raw_refresh_token:
                    g_acc.refresh_token = enc_refresh_token
                g_acc.token_expiry = token_expiry
                g_acc.scopes = scopes
                g_acc.is_connected = True
            else:
                db.add(GoogleAccount(
                    project_id=project_id,
                    account_email=email,
                    access_token=enc_access_token,
                    refresh_token=enc_refresh_token,
                    token_expiry=token_expiry,
                    scopes=scopes,
                    is_connected=True
                ))

        await db.commit()
        logger.info(f"[OAUTH] service={service} stage=connection_saved org_id={organization_id} email={email}")
        return conn

    @classmethod
    async def get_services_status_summary(
        cls,
        organization_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Returns structured connection status for all 4 Google services independently.
        Never reports connected unless credentials exist and status is connected.
        """
        conn_map = await cls.get_all_connections_for_org(organization_id, db)

        summary: Dict[str, Any] = {}
        for s in VALID_SERVICES:
            conn = conn_map.get(s)
            is_conn = bool(conn and conn.status == "connected" and conn.access_token)
            
            res_count = 0
            if conn:
                if s == "google_ads":
                    res_count = len(conn.ads_accounts or [])
                elif s == "search_console":
                    res_count = len(conn.search_console_properties or [])
                elif s == "analytics":
                    res_count = len(conn.analytics_properties or [])
                elif s == "business_profile":
                    res_count = 0  # Dynamic location count

            summary[s] = {
                "connected": is_conn,
                "status": conn.status if conn else "disconnected",
                "google_email": conn.account_email if (is_conn and conn) else None,
                "last_sync_at": conn.last_sync_at.isoformat() if (conn and conn.last_sync_at) else None,
                "last_error": conn.sync_error if conn else None,
                "scopes": conn.scopes if (is_conn and conn) else [],
                "resource_count": res_count
            }

        return summary

    @classmethod
    async def get_valid_access_token(
        cls,
        connection: GoogleConnection,
        db: AsyncSession
    ) -> str:
        """
        Validates token freshness, automatically refreshing expired tokens using the stored refresh token.
        Persists newly encrypted access tokens and returns the active plaintext access token.
        Raises ValueError with user-friendly error message if token cannot be refreshed or connection is invalid.
        """
        if not connection:
            raise ValueError("Google connection not found.")

        plain_access = None
        if connection.access_token:
            try:
                plain_access = decrypt_token(connection.access_token)
            except Exception:
                plain_access = None

        plain_refresh = None
        if connection.refresh_token:
            try:
                plain_refresh = decrypt_token(connection.refresh_token)
            except Exception:
                plain_refresh = None

        now = datetime.now(timezone.utc)
        is_expired = False
        if connection.token_expiry:
            expiry_dt = connection.token_expiry
            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
            if expiry_dt <= now + timedelta(minutes=3):
                is_expired = True

        # If access token is valid and unexpired, return it (and re-encrypt in DB if stored unencrypted)
        if not is_expired and plain_access:
            if is_plaintext_token(connection.access_token):
                connection.access_token = encrypt_token(plain_access)
                await db.commit()
            return plain_access

        # Access token is expired, corrupted, or missing; attempt refresh if refresh token is available
        if not plain_refresh:
            connection.status = "expired"
            connection.sync_error = "Your saved Google connection could not be securely read or has expired. Reconnect your Google account to restore access."
            await db.commit()
            raise ValueError(connection.sync_error)

        try:
            refresh_res = await GoogleOAuthCore.refresh_access_token(plain_refresh)
            new_access_token = refresh_res.get("access_token")
            new_expiry = refresh_res.get("token_expiry")

            if not new_access_token:
                raise ValueError("Token refresh endpoint returned no access token.")

            connection.access_token = encrypt_token(new_access_token)
            if is_plaintext_token(connection.refresh_token):
                connection.refresh_token = encrypt_token(plain_refresh)
            connection.token_expiry = new_expiry
            connection.status = "connected"
            connection.sync_error = None
            await db.commit()
            logger.info(f"[OAUTH_REFRESH] Successfully refreshed access token for service={connection.service} connection_id={connection.id}")
            return new_access_token
        except Exception as e:
            logger.warning(f"[OAUTH_REFRESH] Failed to refresh Google token for connection {connection.id}: {e}")
            connection.status = "expired"
            connection.sync_error = f"Google connection expired or revoked ({str(e)}). Reconnect Google to continue syncing."
            await db.commit()
            raise ValueError(connection.sync_error)

    @classmethod
    async def discover_and_sync_all_resources(
        cls,
        connection: GoogleConnection,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Discovers accessible Google service resources based on the specific service connection:
        1. Google Business Profile locations
        2. Google Search Console verified sites
        3. Google Ads accounts (API v18)
        4. Google Analytics 4 properties
        """
        if not connection.access_token or connection.status not in ("connected", "expired"):
            return {"error": "No valid access token available for synchronization."}

        try:
            plain_access_token = await cls.get_valid_access_token(connection, db)
        except Exception as e:
            logger.warning(f"[SERVICE_DISCOVERY] Token resolution failed: {e}")
            return {"error": str(e), "status": connection.status}

        plain_refresh_token = None
        if connection.refresh_token:
            try:
                plain_refresh_token = decrypt_token(connection.refresh_token)
            except Exception:
                plain_refresh_token = None
        expiry = connection.token_expiry
        granted_scopes = connection.scopes or []
        service = connection.service

        discovered_gbp: List[Dict[str, Any]] = []
        discovered_gsc: List[Dict[str, Any]] = []
        discovered_ads: List[Dict[str, Any]] = []
        discovered_ga4: List[Dict[str, Any]] = []
        discovery_errors: List[str] = []

        # 1. Discover GBP Locations (if service == business_profile or has scope)
        if service == "business_profile" or any("business.manage" in s for s in granted_scopes):
            gbp_client = GoogleBusinessProfileClient(plain_access_token, plain_refresh_token, expiry)
            try:
                acc_res = await gbp_client.list_accounts()
                accounts = acc_res.get("accounts", []) if isinstance(acc_res, dict) else acc_res
                for acc in accounts:
                    acc_name = acc.get("name")
                    if not acc_name:
                        continue
                    locs_res = await gbp_client.list_locations(acc_name)
                    locs = locs_res.get("locations", []) if isinstance(locs_res, dict) else locs_res
                    for l in locs:
                        raw_addr = l.get("storefrontAddress", {})
                        addr_lines = raw_addr.get("addressLines", [])
                        city = raw_addr.get("locality", "")
                        state = raw_addr.get("administrativeArea", "")
                        postal_code = raw_addr.get("postalCode", "")
                        country = raw_addr.get("regionCode", "")
                        full_addr = ", ".join(addr_lines + ([city] if city else []) + ([state] if state else []))
                        
                        cat = l.get("categories", {}).get("primaryCategory", {}).get("displayName", "Local Business")
                        web = l.get("websiteUri")
                        phone = l.get("phoneNumbers", {}).get("primaryPhone")
                        lat_lng = l.get("latlng", {})
                        meta = l.get("metadata", {})
                        
                        discovered_gbp.append({
                            "account_id": acc_name,
                            "account_resource_name": acc_name,
                            "location_id": l.get("name", ""),
                            "location_resource_name": l.get("name", ""),
                            "business_name": l.get("title") or "Unnamed Location",
                            "primary_category": CategoryTaxonomy.normalize_category_name(cat),
                            "additional_categories": [c.get("displayName") for c in l.get("categories", {}).get("additionalCategories", []) if c.get("displayName")],
                            "address": full_addr or None,
                            "address_lines": addr_lines,
                            "city": city or None,
                            "state": state or None,
                            "postal_code": postal_code or None,
                            "country": country or None,
                            "phone": phone or None,
                            "website_url": web or None,
                            "latitude": lat_lng.get("latitude"),
                            "longitude": lat_lng.get("longitude"),
                            "place_id": meta.get("placeId"),
                            "maps_uri": meta.get("mapsUri"),
                            "regular_hours": l.get("regularHours", {}),
                            "special_hours": l.get("specialHours", {}).get("specialHourPeriods", []),
                            "is_verified": l.get("profile", {}).get("isVerified", True)
                        })
            except Exception as e:
                err_text = f"Google Business Profile discovery error: {e}"
                logger.warning(f"[SERVICE_DISCOVERY] {err_text}")
                discovery_errors.append(err_text)

        # 2. Discover Google Search Console Properties (if service == search_console or has scope)
        if service == "search_console" or any("webmasters" in s for s in granted_scopes):
            try:
                headers = {"Authorization": f"Bearer {plain_access_token}"}
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
                    else:
                        err_text = f"Search Console discovery error: HTTP {gsc_resp.status_code}"
                        logger.warning(f"[SERVICE_DISCOVERY] {err_text} - {gsc_resp.text[:200]}")
                        discovery_errors.append(err_text)
            except Exception as e:
                err_text = f"Search Console discovery error: {e}"
                logger.warning(f"[SERVICE_DISCOVERY] {err_text}")
                discovery_errors.append(err_text)

        # 3. Discover Google Ads Accounts (if service == google_ads or has scope)
        if (service == "google_ads" or any("adwords" in s for s in granted_scopes)) and settings.GOOGLE_ADS_DEVELOPER_TOKEN:
            try:
                headers = {
                    "Authorization": f"Bearer {plain_access_token}",
                    "developer-token": settings.GOOGLE_ADS_DEVELOPER_TOKEN
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    ads_resp = await client.get(
                        "https://googleads.googleapis.com/v18/customers:listAccessibleCustomers",
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
                    else:
                        err_text = f"Google Ads discovery error: HTTP {ads_resp.status_code}"
                        logger.warning(f"[SERVICE_DISCOVERY] {err_text}")
                        discovery_errors.append(err_text)
            except Exception as e:
                err_text = f"Google Ads discovery error: {e}"
                logger.warning(f"[SERVICE_DISCOVERY] {err_text}")
                discovery_errors.append(err_text)

        # 4. Discover GA4 Properties (if service == analytics or has scope)
        if service == "analytics" or any("analytics" in s for s in granted_scopes):
            try:
                headers = {"Authorization": f"Bearer {plain_access_token}"}
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
                    else:
                        err_text = f"Google Analytics discovery error: HTTP {ga_resp.status_code}"
                        logger.warning(f"[SERVICE_DISCOVERY] {err_text} - {ga_resp.text[:200]}")
                        discovery_errors.append(err_text)
            except Exception as e:
                err_text = f"Google Analytics discovery error: {e}"
                logger.warning(f"[SERVICE_DISCOVERY] {err_text}")
                discovery_errors.append(err_text)

        # Idempotent persistence of discovered properties
        if discovered_gsc:
            gsc_res = await db.execute(
                select(GoogleSearchConsoleProperty).where(GoogleSearchConsoleProperty.connection_id == connection.id)
            )
            existing_gsc = {p.site_url: p for p in gsc_res.scalars().all()}
            for s in discovered_gsc:
                if s["site_url"] not in existing_gsc:
                    db.add(GoogleSearchConsoleProperty(
                        connection_id=connection.id,
                        site_url=s["site_url"],
                        permission_level=s["permission_level"],
                        is_linked=True
                    ))

        if discovered_ads:
            ads_res = await db.execute(
                select(GoogleAdsAccount).where(GoogleAdsAccount.connection_id == connection.id)
            )
            existing_ads = {a.customer_id: a for a in ads_res.scalars().all()}
            for a in discovered_ads:
                if a["customer_id"] not in existing_ads:
                    db.add(GoogleAdsAccount(
                        connection_id=connection.id,
                        customer_id=a["customer_id"],
                        name=a["name"],
                        status=a["status"],
                        is_linked=True
                    ))

        if discovered_ga4:
            ga4_res = await db.execute(
                select(GoogleAnalyticsProperty).where(GoogleAnalyticsProperty.connection_id == connection.id)
            )
            existing_ga4 = {g.property_id: g for g in ga4_res.scalars().all()}
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
        if discovery_errors:
            connection.sync_error = "; ".join(discovery_errors)
            connection.status = "error"
        else:
            connection.sync_error = None
            connection.status = "connected"
        await db.commit()

        return {
            "gbp_locations": discovered_gbp,
            "search_console": discovered_gsc,
            "ads_accounts": discovered_ads,
            "analytics_properties": discovered_ga4
        }

    @classmethod
    async def discover_gbp_locations_with_linkage(
        cls,
        organization_id: int,
        db: AsyncSession,
        project_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Discovers all accessible GBP locations for the organization across all accounts and pages.
        Annotates existing project bindings and performs NAP match evaluation if project_id is provided.
        """
        conn = await cls.get_connection_for_service(organization_id, "business_profile", db)
        if not conn or not conn.access_token or conn.status not in ("connected", "expired"):
            return {
                "status": "DISCONNECTED" if not conn else conn.status.upper(),
                "connected": False,
                "error": "Google Business Profile is not connected.",
                "locations": [],
                "nap_match_summary": "NO_MATCH"
            }

        try:
            plain_access_token = await cls.get_valid_access_token(conn, db)
        except Exception as e:
            return {
                "status": "AUTH_EXPIRED",
                "connected": False,
                "error": str(e),
                "locations": [],
                "nap_match_summary": "NO_MATCH"
            }

        plain_refresh_token = None
        if conn.refresh_token:
            try:
                plain_refresh_token = decrypt_token(conn.refresh_token)
            except Exception:
                plain_refresh_token = None

        gbp_client = GoogleBusinessProfileClient(plain_access_token, plain_refresh_token, conn.token_expiry)

        # 1. List all accounts with pagination
        acc_res = await gbp_client.list_accounts()
        if acc_res.get("status") not in ("CONNECTED", None):
            return {
                "status": acc_res.get("status", "ERROR"),
                "connected": True,
                "error": acc_res.get("error"),
                "locations": [],
                "nap_match_summary": "NO_MATCH"
            }

        accounts = acc_res.get("accounts", [])
        if not accounts:
            return {
                "status": "NO_BUSINESS_PROFILES",
                "connected": True,
                "error": "No Google Business Profile accounts found for this authorized Google account.",
                "locations": [],
                "nap_match_summary": "NO_MATCH"
            }

        # 2. Query all existing GBP bindings in DB across this org to determine linkage status
        all_gbp_bindings_res = await db.execute(
            select(GoogleBusinessProfile, Project)
            .join(Project, GoogleBusinessProfile.project_id == Project.id, isouter=True)
            .where(Project.organization_id == organization_id)
        )
        existing_bindings = {}
        for row in all_gbp_bindings_res.all():
            gbp_p, prj = row[0], row[1]
            if gbp_p.location_resource_name:
                existing_bindings[gbp_p.location_resource_name] = prj
            if gbp_p.location_name:
                existing_bindings[gbp_p.location_name] = prj
            if gbp_p.place_id:
                existing_bindings[gbp_p.place_id] = prj

        # 3. Discover all locations across accounts
        all_discovered: List[Dict[str, Any]] = []
        location_errors: List[Dict[str, Any]] = []
        for acc in accounts:
            acc_name = acc.get("name")
            if not acc_name:
                continue
            locs_res = await gbp_client.list_locations(acc_name)
            if isinstance(locs_res, dict) and locs_res.get("status") not in ("CONNECTED", "NO_LOCATIONS", None):
                location_errors.append(locs_res)
            locs = locs_res.get("locations", []) if isinstance(locs_res, dict) else locs_res
            for l in locs:
                loc_res_name = l.get("name", "")
                raw_addr = l.get("storefrontAddress", {})
                addr_lines = raw_addr.get("addressLines", [])
                city = raw_addr.get("locality", "")
                state = raw_addr.get("administrativeArea", "")
                postal_code = raw_addr.get("postalCode", "")
                country = raw_addr.get("regionCode", "")
                full_addr = ", ".join(addr_lines + ([city] if city else []) + ([state] if state else []))
                
                cat = l.get("categories", {}).get("primaryCategory", {}).get("displayName", "Local Business")
                web = l.get("websiteUri")
                phone = l.get("phoneNumbers", {}).get("primaryPhone")
                lat_lng = l.get("latlng", {})
                meta = l.get("metadata", {})
                place_id = meta.get("placeId")
                maps_uri = meta.get("mapsUri")
                
                # Check linkage status
                linked_proj = existing_bindings.get(loc_res_name) or (existing_bindings.get(place_id) if place_id else None)
                already_linked_id = linked_proj.id if linked_proj else None
                already_linked_name = linked_proj.name if linked_proj else None
                is_linked_to_current = bool(project_id and already_linked_id == project_id)

                all_discovered.append({
                    "account_id": acc_name,
                    "account_resource_name": acc_name,
                    "location_id": loc_res_name,
                    "location_resource_name": loc_res_name,
                    "business_name": l.get("title") or "Unnamed Location",
                    "primary_category": CategoryTaxonomy.normalize_category_name(cat),
                    "additional_categories": [c.get("displayName") for c in l.get("categories", {}).get("additionalCategories", []) if c.get("displayName")],
                    "address": full_addr or None,
                    "address_lines": addr_lines,
                    "city": city or None,
                    "state": state or None,
                    "postal_code": postal_code or None,
                    "country": country or None,
                    "phone": phone or None,
                    "website_url": web or None,
                    "latitude": lat_lng.get("latitude"),
                    "longitude": lat_lng.get("longitude"),
                    "place_id": place_id,
                    "maps_uri": maps_uri,
                    "regular_hours": l.get("regularHours", {}),
                    "special_hours": l.get("specialHours", {}).get("specialHourPeriods", []),
                    "service_areas": l.get("serviceArea", {}),
                    "is_verified": l.get("profile", {}).get("isVerified", True),
                    "already_linked_to_project_id": already_linked_id,
                    "already_linked_project_name": already_linked_name,
                    "already_linked_to_current_project": is_linked_to_current
                })

        if not all_discovered:
            if location_errors:
                first_err = location_errors[0]
                return {
                    "status": first_err.get("status", "API_ACCESS_NOT_GRANTED"),
                    "connected": True,
                    "error": first_err.get("error", "Google Business Profile location discovery failed."),
                    "locations": [],
                    "nap_match_summary": "NO_MATCH"
                }
            return {
                "status": "NO_LOCATIONS",
                "connected": True,
                "error": "No business locations found under your Google Business Profile accounts.",
                "locations": [],
                "nap_match_summary": "NO_MATCH"
            }

        # 4. If project_id is provided (Workflow A), evaluate NAP matching
        nap_summary = "NO_MATCH"
        if project_id:
            proj_res = await db.execute(select(Project).where(Project.id == project_id))
            target_proj = proj_res.scalars().first()
            if target_proj:
                loc_res = await db.execute(select(Location).where(Location.project_id == target_proj.id))
                p_loc = loc_res.scalars().first()
                proj_data = {
                    "name": target_proj.name,
                    "domain": target_proj.domain,
                    "address": p_loc.address if p_loc else None,
                    "phone": p_loc.phone if p_loc else None
                }
                nap_summary, all_discovered = NAPMatcher.classify_candidates(proj_data, all_discovered)

        return {
            "status": "CONNECTED",
            "connected": True,
            "error": None,
            "locations_count": len(all_discovered),
            "locations": all_discovered,
            "nap_match_summary": nap_summary
        }

    @classmethod
    async def bind_gbp_location_to_project(
        cls,
        project_id: int,
        organization_id: Optional[int] = None,
        location_payload: Optional[Any] = None,
        db: Optional[AsyncSession] = None,
        force_relink: bool = False,
        org_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Workflow A: Binds an existing LocalLift project directly to a specific GBP location.
        Enforces 1:1 binding and duplicate protection.
        """
        eff_org_id = organization_id or org_id or kwargs.get("org_id")
        proj_res = await db.execute(select(Project).where(Project.id == project_id, Project.organization_id == eff_org_id))
        proj = proj_res.scalars().first()
        if not proj:
            raise ValueError("Target project not found or access denied.")

        loc_data = location_payload.model_dump() if hasattr(location_payload, "model_dump") else (location_payload.dict() if hasattr(location_payload, "dict") else dict(location_payload or {}))
        loc_res_name = loc_data.get("location_resource_name") or loc_data.get("location_id")
        if not loc_res_name:
            raise ValueError("Location resource name is required for binding.")

        # Check if already bound to another project
        existing_binding_res = await db.execute(
            select(GoogleBusinessProfile, Project)
            .join(Project, GoogleBusinessProfile.project_id == Project.id)
            .where(
                (GoogleBusinessProfile.location_resource_name == loc_res_name) |
                (GoogleBusinessProfile.location_name == loc_res_name)
            )
        )
        existing_row = existing_binding_res.first()
        if existing_row:
            existing_gbp, existing_proj = existing_row[0], existing_row[1]
            if existing_proj.id != project_id:
                if not force_relink:
                    raise ValueError(f"This GBP location is already linked to Project '{existing_proj.name}' (ID: {existing_proj.id}). Relinking requires explicit confirmation.")
                else:
                    # Unbind from old project
                    existing_gbp.project_id = None
                    await db.flush()

        gbp_conn = await cls.get_connection_for_service(organization_id, "business_profile", db)
        conn_id = gbp_conn.id if gbp_conn else None

        # Fetch or create GoogleBusinessProfile for target project
        prof_res = await db.execute(select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id))
        profile = prof_res.scalars().first()

        biz_name = loc_data.get("business_name") or loc_data.get("location_name") or proj.name
        primary_cat = CategoryTaxonomy.normalize_category_name(loc_data.get("primary_category") or loc_data.get("category"))
        addr = loc_data.get("address")
        city = loc_data.get("city")
        state = loc_data.get("state")
        postal_code = loc_data.get("postal_code")
        country = loc_data.get("country") or proj.country
        phone = loc_data.get("phone")
        web = loc_data.get("website_url") or f"https://{proj.domain}"
        lat = loc_data.get("latitude")
        lng = loc_data.get("longitude")
        place_id = loc_data.get("place_id")
        maps_uri = loc_data.get("maps_uri")
        hours = loc_data.get("regular_hours") or {}
        special_hours = loc_data.get("special_hours") or []

        if not profile:
            profile = GoogleBusinessProfile(
                project_id=project_id,
                google_connection_id=conn_id,
                account_resource_name=loc_data.get("account_resource_name") or loc_data.get("account_id"),
                location_resource_name=loc_res_name,
                location_name=loc_res_name,
                business_name=biz_name,
                primary_category=primary_cat,
                additional_categories=loc_data.get("additional_categories") or [],
                address=addr,
                address_lines=loc_data.get("address_lines") or [],
                city=city,
                state=state,
                postal_code=postal_code,
                country=country,
                phone=phone,
                website_url=web,
                latitude=lat,
                longitude=lng,
                place_id=place_id,
                maps_uri=maps_uri,
                regular_hours=hours,
                opening_hours=hours,
                special_hours=special_hours,
                completeness_score=90,
                is_verified=loc_data.get("is_verified", True),
                status="CONNECTED",
                sync_status="idle",
                last_synced_at=datetime.now(timezone.utc)
            )
            db.add(profile)
        else:
            profile.google_connection_id = conn_id
            profile.account_resource_name = loc_data.get("account_resource_name") or loc_data.get("account_id")
            profile.location_resource_name = loc_res_name
            profile.location_name = loc_res_name
            profile.business_name = biz_name
            profile.primary_category = primary_cat
            profile.additional_categories = loc_data.get("additional_categories") or profile.additional_categories
            profile.address = addr or profile.address
            profile.address_lines = loc_data.get("address_lines") or profile.address_lines
            profile.city = city or profile.city
            profile.state = state or profile.state
            profile.postal_code = postal_code or profile.postal_code
            profile.country = country or profile.country
            profile.phone = phone or profile.phone
            profile.website_url = web or profile.website_url
            profile.latitude = lat if lat is not None else profile.latitude
            profile.longitude = lng if lng is not None else profile.longitude
            profile.place_id = place_id or profile.place_id
            profile.maps_uri = maps_uri or profile.maps_uri
            profile.regular_hours = hours or profile.regular_hours
            profile.opening_hours = hours or profile.opening_hours
            profile.special_hours = special_hours or profile.special_hours
            profile.is_verified = loc_data.get("is_verified", True)
            profile.status = "CONNECTED"
            profile.sync_status = "idle"
            profile.last_synced_at = datetime.now(timezone.utc)

        # Update Project Location with exact GBP address details
        loc_res = await db.execute(select(Location).where(Location.project_id == project_id))
        loc = loc_res.scalars().first()
        if loc:
            if addr: loc.address = addr
            if city: loc.city = city
            if state: loc.state = state
            if postal_code: loc.postal_code = postal_code
            if country: loc.country = country
            if phone: loc.phone = phone
            if lat is not None: loc.latitude = lat
            if lng is not None: loc.longitude = lng
            if place_id: loc.place_id = place_id
        else:
            loc = Location(
                project_id=project_id,
                name=biz_name,
                address=addr,
                city=city,
                state=state,
                postal_code=postal_code,
                country=country,
                phone=phone,
                latitude=lat,
                longitude=lng,
                place_id=place_id
            )
            db.add(loc)

        if country:
            proj.country = country

        await db.commit()
        await db.refresh(profile)
        logger.info(f"[GBP_BIND] Successfully bound Project {project_id} to GBP Location {loc_res_name}")

        return {
            "success": True,
            "project_id": project_id,
            "location_resource_name": loc_res_name,
            "business_name": biz_name,
            "message": f"Successfully bound Google Business Profile '{biz_name}' to {proj.name}."
        }

    @classmethod
    async def create_projects_from_gbp_locations(
        cls,
        organization_id: Optional[int] = None,
        user_id: Optional[int] = None,
        locations_payload: Optional[List[Any]] = None,
        db: Optional[AsyncSession] = None,
        org_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Workflow B: Creates 1 LocalLift project per selected GBP location without requiring existing NAP match.
        Populates complete business info, hours, coordinates, and strong GBP binding.
        """
        eff_org_id = organization_id or org_id or kwargs.get("org_id")
        if not eff_org_id:
            raise ValueError("organization_id is required.")
        if not locations_payload:
            raise ValueError("No GBP locations provided for project creation.")

        gbp_conn = await cls.get_connection_for_service(eff_org_id, "business_profile", db)
        conn_id = gbp_conn.id if gbp_conn else None

        created_projects: List[Dict[str, Any]] = []
        skipped_locations: List[Dict[str, Any]] = []

        for item in locations_payload:
            loc_data = item.model_dump() if hasattr(item, "model_dump") else (item.dict() if hasattr(item, "dict") else dict(item))
            loc_res_name = loc_data.get("location_resource_name") or loc_data.get("location_id")
            biz_name = loc_data.get("business_name") or loc_data.get("location_name") or loc_data.get("title") or "Imported Business"

            # Duplicate protection: verify this GBP location isn't already bound to a project in the org
            if loc_res_name:
                existing_res = await db.execute(
                    select(GoogleBusinessProfile, Project)
                    .join(Project, GoogleBusinessProfile.project_id == Project.id)
                    .where(
                        (GoogleBusinessProfile.location_resource_name == loc_res_name) |
                        (GoogleBusinessProfile.location_name == loc_res_name)
                    )
                )
                existing_row = existing_res.first()
                if existing_row:
                    skipped_locations.append({
                        "location_id": loc_res_name,
                        "business_name": biz_name,
                        "reason": f"Already linked to Project '{existing_row[1].name}' (ID: {existing_row[1].id})"
                    })
                    continue

            # Generate domain
            raw_url = loc_data.get("website_url") or loc_data.get("websiteUri") or ""
            domain = raw_url.replace("https://", "").replace("http://", "").rstrip("/").split("/")[0]
            if not domain:
                clean_slug = re.sub(r'[^a-zA-Z0-9-]', '', biz_name.lower().replace(' ', '-'))
                domain = f"{clean_slug[:35] or 'biz'}-{uuid.uuid4().hex[:4]}.local"

            cat = CategoryTaxonomy.normalize_category_name(loc_data.get("primary_category"))
            country = loc_data.get("country") or None

            # Create Project
            new_proj = Project(
                organization_id=eff_org_id,
                name=biz_name,
                domain=domain,
                primary_category=cat,
                additional_categories=loc_data.get("additional_categories") or [],
                country=country,
                health_score=None
            )
            db.add(new_proj)
            await db.flush()

            # Create Website
            db.add(Website(
                project_id=new_proj.id,
                url=raw_url if raw_url.startswith("http") else (f"https://{domain}" if domain else "https://example.com"),
                status="ready"
            ))

            # Create Location
            db.add(Location(
                project_id=new_proj.id,
                name=biz_name,
                address=loc_data.get("address"),
                city=loc_data.get("city"),
                state=loc_data.get("state"),
                postal_code=loc_data.get("postal_code"),
                country=country,
                phone=loc_data.get("phone"),
                latitude=loc_data.get("latitude"),
                longitude=loc_data.get("longitude"),
                place_id=loc_data.get("place_id")
            ))

            # Create GoogleBusinessProfile with strong explicit binding
            hours = loc_data.get("regular_hours") or loc_data.get("regularHours") or {}
            special_hours = loc_data.get("special_hours") or []

            gbp_profile = GoogleBusinessProfile(
                project_id=new_proj.id,
                google_connection_id=conn_id,
                account_resource_name=loc_data.get("account_resource_name") or loc_data.get("account_id"),
                location_resource_name=loc_res_name,
                location_name=loc_res_name,
                business_name=biz_name,
                primary_category=cat,
                additional_categories=loc_data.get("additional_categories") or [],
                address=loc_data.get("address"),
                address_lines=loc_data.get("address_lines") or [],
                city=loc_data.get("city"),
                state=loc_data.get("state"),
                postal_code=loc_data.get("postal_code"),
                country=country,
                phone=loc_data.get("phone"),
                website_url=raw_url or None,
                latitude=loc_data.get("latitude"),
                longitude=loc_data.get("longitude"),
                place_id=loc_data.get("place_id"),
                maps_uri=loc_data.get("maps_uri"),
                regular_hours=hours,
                opening_hours=hours,
                special_hours=special_hours,
                completeness_score=90,
                is_verified=loc_data.get("is_verified", True),
                status="CONNECTED",
                sync_status="idle",
                last_synced_at=datetime.now(timezone.utc)
            )
            db.add(gbp_profile)

            created_projects.append({
                "project_id": new_proj.id,
                "project_name": new_proj.name,
                "domain": new_proj.domain,
                "location_resource_name": loc_res_name
            })

        await db.commit()
        return {
            "success": True,
            "created_projects_count": len(created_projects),
            "created_projects": created_projects,
            "skipped_locations_count": len(skipped_locations),
            "skipped_locations": skipped_locations,
            "message": f"Successfully created {len(created_projects)} LocalLift project(s) from selected Google Business Profiles."
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
        Maintains backward compatibility with older import payloads while using strong GBP bindings.
        """
        created_projects = 0
        imported_locations = 0
        imported_websites = 0

        # Import GBP Locations
        if selected_gbp:
            res = await cls.create_projects_from_gbp_locations(
                organization_id=organization_id,
                user_id=1,
                locations_payload=selected_gbp,
                db=db
            )
            created_projects += res.get("created_projects_count", 0)
            imported_locations += res.get("created_projects_count", 0)

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
                    country=None,
                    health_score=None
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
        db: AsyncSession,
        service: Optional[str] = None
    ) -> bool:
        """
        Safely disconnects a specific Google service integration for the organization.
        Disconnecting one service MUST NOT disconnect or clear credentials for other services.
        """
        target_service = service or "business_profile"
        conn = await cls.get_connection_for_service(organization_id, target_service, db)
        if not conn:
            return False

        conn.status = "disconnected"
        conn.access_token = None
        conn.refresh_token = None
        conn.sync_error = None
        conn.last_sync_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(f"[OAUTH] service={target_service} stage=connection_disconnected org_id={organization_id}")
        return True
