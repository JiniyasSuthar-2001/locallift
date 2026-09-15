import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.analytics import GA4Metric

logger = logging.getLogger("locallift.google.ga4")


class GoogleAnalytics4Client:
    """
    Client for interacting with the Google Analytics 4 Data API (v1beta).
    Executes real runReport requests and stores verified metrics in GA4Metric.
    """
    BASE_URL = "https://analyticsdata.googleapis.com/v1beta"

    @classmethod
    async def fetch_ga4_report(
        cls,
        access_token: str,
        property_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Executes Google Analytics Data API runReport for:
        1. Daily active users, sessions, engagement rate, and conversions
        2. Top landing pages with session counts and engagement
        """
        # Ensure property_id doesn't have duplicate 'properties/' prefix
        clean_prop = property_id.replace("properties/", "")
        url = f"{cls.BASE_URL}/properties/{clean_prop}:runReport"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        daily_rows: List[Dict[str, Any]] = []
        landing_pages: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=20.0) as client:
            # 1. Fetch Daily Timeseries
            daily_body = {
                "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
                "dimensions": [{"name": "date"}],
                "metrics": [
                    {"name": "activeUsers"},
                    {"name": "sessions"},
                    {"name": "engagementRate"},
                    {"name": "conversions"}
                ],
                "orderBys": [
                    {"dimension": {"dimensionName": "date"}, "desc": False}
                ]
            }

            try:
                resp = await client.post(url, headers=headers, json=daily_body)
                if resp.status_code == 200:
                    data = resp.json()
                    for r in data.get("rows", []):
                        date_val = r.get("dimensionValues", [{}])[0].get("value", "")
                        metric_vals = r.get("metricValues", [])
                        if date_val and len(metric_vals) >= 4:
                            daily_rows.append({
                                "date": date_val,
                                "active_users": int(metric_vals[0].get("value", 0)),
                                "sessions": int(metric_vals[1].get("value", 0)),
                                "engagement_rate": round(float(metric_vals[2].get("value", 0.0)) * 100, 1),
                                "conversions": int(metric_vals[3].get("value", 0))
                            })
                else:
                    logger.warning(f"[GA4_API] Daily runReport HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                logger.error(f"[GA4_API] Daily runReport request failed: {e}")

            # 2. Fetch Top Landing Pages
            landing_body = {
                "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
                "dimensions": [{"name": "pagePath"}],
                "metrics": [
                    {"name": "sessions"},
                    {"name": "engagementRate"},
                    {"name": "conversions"}
                ],
                "limit": 15
            }

            try:
                resp = await client.post(url, headers=headers, json=landing_body)
                if resp.status_code == 200:
                    data = resp.json()
                    for r in data.get("rows", []):
                        path_val = r.get("dimensionValues", [{}])[0].get("value", "")
                        metric_vals = r.get("metricValues", [])
                        if path_val and len(metric_vals) >= 3:
                            landing_pages.append({
                                "path": path_val,
                                "sessions": int(metric_vals[0].get("value", 0)),
                                "engagement_rate": round(float(metric_vals[1].get("value", 0.0)) * 100, 1),
                                "conversions": int(metric_vals[2].get("value", 0))
                            })
                else:
                    logger.warning(f"[GA4_API] Landing pages runReport HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                logger.error(f"[GA4_API] Landing pages runReport request failed: {e}")

        return {
            "daily_rows": daily_rows,
            "landing_pages": landing_pages
        }

    @classmethod
    async def sync_project_ga4_metrics(
        cls,
        project_id: int,
        access_token: str,
        property_id: str,
        db: AsyncSession,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Synchronizes GA4 metrics for a project, upserting records in the GA4Metric table.
        """
        data = await cls.fetch_ga4_report(access_token, property_id, days=days)
        daily_rows = data.get("daily_rows", [])
        landing_pages = data.get("landing_pages", [])

        synced_count = 0

        for row in daily_rows:
            raw_date = row.get("date", "")
            if not raw_date:
                continue

            try:
                # GA4 date is in YYYYMMDD format
                row_date = datetime.strptime(raw_date, "%Y%m%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue

            users = row.get("active_users", 0)
            sessions = row.get("sessions", 0)
            eng_rate = row.get("engagement_rate", 0.0)
            conversions = row.get("conversions", 0)

            # Check for existing record
            existing_res = await db.execute(
                select(GA4Metric).where(
                    GA4Metric.project_id == project_id,
                    GA4Metric.date == row_date
                )
            )
            metric_record = existing_res.scalars().first()

            if metric_record:
                metric_record.organic_users = users
                metric_record.sessions = sessions
                metric_record.engagement_rate = eng_rate
                metric_record.conversions = conversions
                metric_record.landing_pages = landing_pages
            else:
                metric_record = GA4Metric(
                    project_id=project_id,
                    date=row_date,
                    organic_users=users,
                    sessions=sessions,
                    engagement_rate=eng_rate,
                    conversions=conversions,
                    landing_pages=landing_pages,
                    traffic_sources=[],
                    user_locations=[]
                )
                db.add(metric_record)

            synced_count += 1

        # If no daily rows returned, store fallback record with current date if landing pages exist
        if not daily_rows and landing_pages:
            today_dt = datetime.now(timezone.utc)
            existing_res = await db.execute(
                select(GA4Metric).where(GA4Metric.project_id == project_id)
            )
            metric_record = existing_res.scalars().first()
            if not metric_record:
                db.add(GA4Metric(
                    project_id=project_id,
                    date=today_dt,
                    organic_users=0,
                    sessions=0,
                    engagement_rate=0.0,
                    conversions=0,
                    landing_pages=landing_pages
                ))
                synced_count += 1

        await db.commit()
        logger.info(f"[GA4_SYNC] Synced {synced_count} GA4Metric records for project_id={project_id} property_id={property_id}")
        return {
            "success": True,
            "synced_records": synced_count,
            "landing_pages_count": len(landing_pages)
        }
