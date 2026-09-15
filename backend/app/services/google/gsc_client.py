import logging
import urllib.parse
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.analytics import GSCMetric

logger = logging.getLogger("locallift.google.gsc")


class GoogleSearchConsoleClient:
    """
    Client for interacting with the Google Search Console Search Analytics API.
    Executes real searchanalytics.query requests and stores verified performance records in GSCMetric.
    """
    BASE_URL = "https://www.googleapis.com/webmasters/v3"

    @classmethod
    async def fetch_search_analytics(
        cls,
        access_token: str,
        site_url: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Queries Google Search Console Search Analytics API for:
        1. Daily aggregated clicks, impressions, CTR, average position
        2. Top queries
        3. Top pages
        """
        encoded_site = urllib.parse.quote_plus(site_url)
        url = f"{cls.BASE_URL}/sites/{encoded_site}/searchAnalytics/query"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        end_date = datetime.now(timezone.utc).date() - timedelta(days=2)  # GSC data usually has 2-day lag
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        daily_rows: List[Dict[str, Any]] = []
        top_queries: List[Dict[str, Any]] = []
        top_pages: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=20.0) as client:
            # 1. Fetch Daily Timeseries
            daily_payload = {
                "startDate": start_str,
                "endDate": end_str,
                "dimensions": ["date"],
                "rowLimit": 35
            }
            try:
                resp = await client.post(url, headers=headers, json=daily_payload)
                if resp.status_code == 200:
                    daily_rows = resp.json().get("rows", [])
                else:
                    logger.warning(f"[GSC_API] Daily query HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                logger.error(f"[GSC_API] Daily query request failed: {e}")

            # 2. Fetch Top Search Queries
            query_payload = {
                "startDate": start_str,
                "endDate": end_str,
                "dimensions": ["query"],
                "rowLimit": 20
            }
            try:
                resp = await client.post(url, headers=headers, json=query_payload)
                if resp.status_code == 200:
                    for r in resp.json().get("rows", []):
                        q_name = r.get("keys", [""])[0]
                        if q_name:
                            top_queries.append({
                                "query": q_name,
                                "clicks": int(r.get("clicks", 0)),
                                "impressions": int(r.get("impressions", 0)),
                                "ctr": f"{round(float(r.get('ctr', 0.0)) * 100, 1)}%",
                                "position": round(float(r.get("position", 0.0)), 1)
                            })
            except Exception as e:
                logger.error(f"[GSC_API] Queries query request failed: {e}")

            # 3. Fetch Top Landing Pages
            page_payload = {
                "startDate": start_str,
                "endDate": end_str,
                "dimensions": ["page"],
                "rowLimit": 20
            }
            try:
                resp = await client.post(url, headers=headers, json=page_payload)
                if resp.status_code == 200:
                    for r in resp.json().get("rows", []):
                        p_url = r.get("keys", [""])[0]
                        if p_url:
                            top_pages.append({
                                "page": p_url,
                                "clicks": int(r.get("clicks", 0)),
                                "impressions": int(r.get("impressions", 0)),
                                "ctr": f"{round(float(r.get('ctr', 0.0)) * 100, 1)}%",
                                "position": round(float(r.get("position", 0.0)), 1)
                            })
            except Exception as e:
                logger.error(f"[GSC_API] Pages query request failed: {e}")

        return {
            "daily_rows": daily_rows,
            "top_queries": top_queries,
            "top_pages": top_pages,
            "start_date": start_str,
            "end_date": end_str
        }

    @classmethod
    async def sync_project_gsc_metrics(
        cls,
        project_id: int,
        access_token: str,
        site_url: str,
        db: AsyncSession,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Synchronizes GSC metrics for a project, upserting records in the GSCMetric table.
        """
        data = await cls.fetch_search_analytics(access_token, site_url, days=days)
        daily_rows = data.get("daily_rows", [])
        top_queries = data.get("top_queries", [])
        top_pages = data.get("top_pages", [])

        synced_count = 0

        # Upsert daily metrics
        for row in daily_rows:
            date_str = row.get("keys", [""])[0]
            if not date_str:
                continue

            try:
                row_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue

            clicks = int(row.get("clicks", 0))
            impressions = int(row.get("impressions", 0))
            ctr = round(float(row.get("ctr", 0.0)) * 100, 2)
            avg_pos = round(float(row.get("position", 0.0)), 1)

            # Check for existing record for project & date
            existing_res = await db.execute(
                select(GSCMetric).where(
                    GSCMetric.project_id == project_id,
                    GSCMetric.date == row_date
                )
            )
            metric_record = existing_res.scalars().first()

            if metric_record:
                metric_record.clicks = clicks
                metric_record.impressions = impressions
                metric_record.ctr = ctr
                metric_record.average_position = avg_pos
                metric_record.top_queries = top_queries
                metric_record.top_pages = top_pages
            else:
                metric_record = GSCMetric(
                    project_id=project_id,
                    date=row_date,
                    clicks=clicks,
                    impressions=impressions,
                    ctr=ctr,
                    average_position=avg_pos,
                    top_queries=top_queries,
                    top_pages=top_pages,
                    devices={},
                    countries={}
                )
                db.add(metric_record)

            synced_count += 1

        # If no daily rows returned (e.g. brand new site with 0 traffic), store a placeholder current date record
        if not daily_rows and (top_queries or top_pages):
            today_dt = datetime.now(timezone.utc)
            existing_res = await db.execute(
                select(GSCMetric).where(GSCMetric.project_id == project_id)
            )
            metric_record = existing_res.scalars().first()
            if not metric_record:
                db.add(GSCMetric(
                    project_id=project_id,
                    date=today_dt,
                    clicks=0,
                    impressions=0,
                    ctr=0.0,
                    average_position=0.0,
                    top_queries=top_queries,
                    top_pages=top_pages
                ))
                synced_count += 1

        await db.commit()
        logger.info(f"[GSC_SYNC] Synced {synced_count} GSCMetric records for project_id={project_id} site_url={site_url}")
        return {
            "success": True,
            "synced_records": synced_count,
            "top_queries_count": len(top_queries),
            "top_pages_count": len(top_pages)
        }
