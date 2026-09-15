import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import AsyncSessionLocal
from app.models.analytics import ScheduledJob
from app.models.project import Project, Website
from app.models.gbp import GoogleAccount

logger = logging.getLogger("locallift.scheduler")

SUPPORTED_JOB_TYPES = ["crawl", "rank_check", "gbp_sync", "review_sync", "gsc_sync", "ga4_sync"]

class JobSchedulerService:
    """
    Genuine job execution service for LocalLift.
    Executes actual background routines:
    - crawl: WebsiteCrawler & SEOAuditor
    - rank_check: Keyword SERP verification
    - gbp_sync: GBPSyncService
    - review_sync: GBP review sync
    - gsc_sync: GoogleSearchConsoleClient.sync_project_gsc_metrics
    - ga4_sync: GoogleAnalytics4Client.sync_project_ga4_metrics
    """

    @classmethod
    async def get_or_create_project_jobs(cls, project_id: int, db: AsyncSession) -> List[ScheduledJob]:
        """
        Ensures a project has the standard scheduled jobs configured.
        """
        res = await db.execute(
            select(ScheduledJob).where(ScheduledJob.project_id == project_id)
        )
        existing = res.scalars().all()
        existing_types = {j.job_type for j in existing}

        now = datetime.now(timezone.utc)
        jobs_to_create = [
            ("crawl", "weekly", now + timedelta(days=7)),
            ("rank_check", "daily", now + timedelta(days=1)),
            ("gbp_sync", "daily", now + timedelta(days=1)),
            ("review_sync", "daily", now + timedelta(days=1)),
            ("gsc_sync", "daily", now + timedelta(days=1)),
            ("ga4_sync", "daily", now + timedelta(days=1)),
        ]

        created = False
        for j_type, freq, next_run in jobs_to_create:
            if j_type not in existing_types:
                db.add(ScheduledJob(
                    project_id=project_id,
                    job_type=j_type,
                    frequency=freq,
                    status="idle",
                    next_run_at=next_run,
                    last_result_summary=f"Initialized {freq} scheduled {j_type} job."
                ))
                created = True

        if created:
            await db.commit()
            res = await db.execute(
                select(ScheduledJob).where(ScheduledJob.project_id == project_id).order_by(ScheduledJob.id.asc())
            )
            return res.scalars().all()

        return existing

    @classmethod
    async def execute_job(cls, job_id: int, db: AsyncSession) -> Dict[str, Any]:
        """
        Executes a scheduled job by running the genuine service logic.
        Updates job status, execution timestamps, and outcome summary.
        """
        res = await db.execute(select(ScheduledJob).where(ScheduledJob.id == job_id))
        job = res.scalars().first()
        if not job:
            raise ValueError(f"ScheduledJob #{job_id} not found.")

        proj_res = await db.execute(select(Project).where(Project.id == job.project_id))
        proj = proj_res.scalars().first()
        if not proj:
            raise ValueError(f"Project #{job.project_id} not found for ScheduledJob #{job_id}.")

        job.status = "running"
        job.last_run_at = datetime.now(timezone.utc)
        await db.commit()

        summary_msg = ""
        success = False

        try:
            if job.job_type == "crawl":
                from app.api.v1.audits import run_crawler_and_audit_task
                start_url = f"https://{proj.domain}"
                await run_crawler_and_audit_task(job.project_id, start_url=start_url, max_pages=15)
                summary_msg = f"Crawled up to 15 pages for https://{proj.domain} and updated SEO audit score."
                success = True

            elif job.job_type == "rank_check":
                from app.models.ranking import Keyword
                from app.services.serp import get_organization_serp_provider, DomainMatcher
                kw_res = await db.execute(select(Keyword).where(Keyword.project_id == job.project_id))
                kws = kw_res.scalars().all()
                if not kws:
                    summary_msg = "No keywords configured for rank tracking."
                else:
                    provider = await get_organization_serp_provider(db, proj.organization_id)
                    checked = 0
                    for k in kws[:10]:
                        try:
                            serp_res = await provider.search_keyword(
                                keyword=k.keyword,
                                location=k.target_location
                            )
                            if serp_res and serp_res.success:
                                rank = DomainMatcher.find_domain_rank(serp_res.organic_results, proj.domain)
                                if rank is not None:
                                    k.previous_rank = k.current_rank
                                    k.current_rank = rank
                                k.last_checked_at = datetime.now(timezone.utc)
                                checked += 1
                        except Exception as serp_err:
                            logger.warning(f"[SCHEDULER_SERP] Keyword '{k.keyword}' check: {serp_err}")
                    summary_msg = f"Checked rankings for {checked} of {len(kws)} tracked keywords via {provider.__class__.__name__}."
                success = True

            elif job.job_type == "gbp_sync":
                from app.models.gbp import GoogleAccount
                from app.services.google.sync import GBPSyncService
                acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == job.project_id))
                g_acc = acc_res.scalars().first()
                if not g_acc:
                    summary_msg = "Google Business Profile is not connected for this project."
                else:
                    sync_res = await GBPSyncService.sync_google_account(g_acc, db)
                    summary_msg = f"GBP sync completed: {sync_res.get('profiles_synced', 0)} profiles, {sync_res.get('changes_detected', 0)} changes."
                success = True

            elif job.job_type == "review_sync":
                from app.models.local_seo import Review
                from app.models.gbp import GoogleBusinessProfile
                from app.services.google.gbp_client import GoogleBusinessProfileClient
                from app.services.google.connections_service import GoogleConnectionsService
                from app.core.security import decrypt_token

                gbp_conn = await GoogleConnectionsService.get_connection_for_service(proj.organization_id, "business_profile", db)
                acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == job.project_id))
                g_acc = acc_res.scalars().first()

                if not gbp_conn and not g_acc:
                    summary_msg = "GBP account not connected. Review sync skipped."
                else:
                    if gbp_conn and gbp_conn.status in ("connected", "expired") and gbp_conn.access_token:
                        token = await GoogleConnectionsService.get_valid_access_token(gbp_conn, db)
                        ref_tok = decrypt_token(gbp_conn.refresh_token) if gbp_conn.refresh_token else None
                        exp = gbp_conn.token_expiry
                    else:
                        token = decrypt_token(g_acc.access_token)
                        ref_tok = decrypt_token(g_acc.refresh_token) if g_acc.refresh_token else None
                        exp = g_acc.token_expiry

                    client = GoogleBusinessProfileClient(token, ref_tok, exp)
                    prof_res = await db.execute(
                        select(GoogleBusinessProfile).where(
                            (GoogleBusinessProfile.google_account_id == (g_acc.id if g_acc else -1)) |
                            (GoogleBusinessProfile.business_name.ilike(f"%{proj.name}%"))
                        )
                    )
                    profile = prof_res.scalars().first()
                    account_id = profile.account_id if profile and profile.account_id else "accounts/default"
                    location_name = profile.location_name if profile and profile.location_name else "locations/default"

                    reviews_data = await client.fetch_location_reviews(account_id, location_name)
                    new_c = 0
                    for rev in reviews_data:
                        existing_res = await db.execute(
                            select(Review).where(
                                Review.project_id == job.project_id,
                                Review.author_name == rev["author_name"],
                                Review.source == "Google"
                            )
                        )
                        if not existing_res.scalars().first():
                            db.add(Review(
                                project_id=job.project_id,
                                source="Google",
                                author_name=rev["author_name"],
                                author_photo_url=rev.get("author_photo_url"),
                                rating=rev["rating"],
                                review_text=rev.get("review_text"),
                                review_date=rev.get("review_date", datetime.now(timezone.utc)),
                                response_text=rev.get("response_text"),
                                response_status=rev.get("response_status", "unanswered"),
                                sentiment="positive" if rev["rating"] >= 4 else ("neutral" if rev["rating"] == 3 else "negative")
                            ))
                            new_c += 1
                    summary_msg = f"Synced {len(reviews_data)} Google reviews ({new_c} new)."
                success = True

            elif job.job_type == "gsc_sync":
                from app.models.connections import GoogleConnection, GoogleSearchConsoleProperty
                from app.services.google.connections_service import GoogleConnectionsService
                from app.services.google.gsc_client import GoogleSearchConsoleClient

                gsc_conn = await GoogleConnectionsService.get_connection_for_service(proj.organization_id, "search_console", db)
                prop_res = await db.execute(
                    select(GoogleSearchConsoleProperty).where(GoogleSearchConsoleProperty.project_id == job.project_id)
                )
                prop = prop_res.scalars().first()

                if not gsc_conn or gsc_conn.status not in ("connected", "expired"):
                    summary_msg = "Google Search Console is not connected."
                elif not prop:
                    summary_msg = "No Search Console property mapped to this project."
                else:
                    token = await GoogleConnectionsService.get_valid_access_token(gsc_conn, db)
                    res_gsc = await GoogleSearchConsoleClient.sync_project_gsc_metrics(
                        project_id=job.project_id,
                        access_token=token,
                        site_url=prop.site_url,
                        db=db
                    )
                    summary_msg = f"GSC metrics synchronized: {res_gsc.get('synced_records', 0)} daily records."
                success = True

            elif job.job_type == "ga4_sync":
                from app.models.connections import GoogleConnection, GoogleAnalyticsProperty
                from app.services.google.connections_service import GoogleConnectionsService
                from app.services.google.ga4_client import GoogleAnalytics4Client

                ga_conn = await GoogleConnectionsService.get_connection_for_service(proj.organization_id, "analytics", db)
                prop_res = await db.execute(
                    select(GoogleAnalyticsProperty).where(GoogleAnalyticsProperty.project_id == job.project_id)
                )
                prop = prop_res.scalars().first()

                if not ga_conn or ga_conn.status not in ("connected", "expired"):
                    summary_msg = "Google Analytics 4 is not connected."
                elif not prop:
                    summary_msg = "No GA4 property mapped to this project."
                else:
                    token = await GoogleConnectionsService.get_valid_access_token(ga_conn, db)
                    res_ga4 = await GoogleAnalytics4Client.sync_project_ga4_metrics(
                        project_id=job.project_id,
                        access_token=token,
                        property_id=prop.property_id,
                        db=db
                    )
                    summary_msg = f"GA4 metrics synchronized: {res_ga4.get('synced_records', 0)} daily records."
                success = True

            else:
                summary_msg = f"Unknown job type '{job.job_type}'."
                success = False

        except Exception as e:
            logger.error(f"[JOB_EXECUTION] Job #{job_id} ({job.job_type}) failed: {e}", exc_info=True)
            summary_msg = f"Execution error: {str(e)[:300]}"
            success = False

        job.status = "completed" if success else "failed"
        job.last_result_summary = summary_msg

        # Compute next run time
        delta = timedelta(days=1)
        if job.frequency == "weekly":
            delta = timedelta(days=7)
        elif job.frequency == "monthly":
            delta = timedelta(days=30)
        job.next_run_at = datetime.now(timezone.utc) + delta

        await db.commit()
        await db.refresh(job)

        return {
            "job_id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "last_result_summary": job.last_result_summary,
            "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
            "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None
        }

    @classmethod
    async def process_due_jobs(cls) -> int:
        from app.database import AsyncSessionLocal
        now = datetime.now(timezone.utc)
        due_job_ids = []

        async with AsyncSessionLocal() as db:
            stmt = select(ScheduledJob.id).where(
                ScheduledJob.status != "running",
                (ScheduledJob.next_run_at <= now) | (ScheduledJob.next_run_at == None)
            ).limit(10)
            res = await db.execute(stmt)
            due_job_ids = list(res.scalars().all())

        processed = 0
        for jid in due_job_ids:
            try:
                async with AsyncSessionLocal() as db:
                    await cls.execute_job(jid, db)
                processed += 1
            except Exception as e:
                logger.error(f"[SCHEDULER] Failed to process due job #{jid}: {e}")

        return processed


_scheduler_task = None
_is_running = False


async def _scheduler_loop():
    logger.info("[SCHEDULER] ScheduledJob background runner cycle initiated.")
    while _is_running:
        try:
            await JobSchedulerService.process_due_jobs()
        except Exception as e:
            logger.error(f"[SCHEDULER] Error during scheduled job cycle: {e}")

        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
    logger.info("[SCHEDULER] ScheduledJob background runner stopped.")


def start_scheduler():
    global _scheduler_task, _is_running
    if not _is_running:
        _is_running = True
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("[SCHEDULER] Started background scheduler worker.")


def stop_scheduler():
    global _scheduler_task, _is_running
    if _is_running:
        _is_running = False
        if _scheduler_task and not _scheduler_task.done():
            _scheduler_task.cancel()
        logger.info("[SCHEDULER] Stopped background scheduler worker.")
