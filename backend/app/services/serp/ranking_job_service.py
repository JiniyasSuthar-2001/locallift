import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import AsyncSessionLocal
from app.config import settings
from app.models.scan_job import ScanJob, JobStatus, JobType
from app.models.ranking import Keyword
from app.services.serp.ranking_service import KeywordRankingService
from app.services.provider_usage_service import ProviderUsageService

logger = logging.getLogger("locallift.services.ranking_job")


class KeywordRankingJobService:
    """
    Asynchronous queue processor for multi-keyword ranking scans.
    Supports 30–40 keywords with bounded concurrency, 5-minute timeout ceiling,
    cooperative project-isolated cancellation, and atomic point accounting.
    """

    _active_tasks: Dict[int, asyncio.Task] = {}

    @classmethod
    async def create_keyword_job(
        cls,
        db: AsyncSession,
        project_id: int,
        organization_id: int,
        user_id: Optional[int] = None,
        keyword_ids: Optional[List[int]] = None
    ) -> ScanJob:
        """
        Initializes and persists a new ScanJob for keyword rank tracking.
        """
        query = select(Keyword).where(Keyword.project_id == project_id)
        if keyword_ids:
            query = query.where(Keyword.id.in_(keyword_ids))

        res = await db.execute(query)
        keywords = res.scalars().all()

        max_runtime = getattr(settings, "SCAN_MAX_RUNTIME_SECONDS", 300)
        now = datetime.now(timezone.utc)

        job = ScanJob(
            organization_id=organization_id,
            project_id=project_id,
            user_id=user_id,
            job_type=JobType.KEYWORD_RANK.value,
            status=JobStatus.QUEUED.value,
            current_stage="Job queued for execution",
            total_items=len(keywords),
            processed_items=0,
            successful_items=0,
            failed_items=0,
            not_found_items=0,
            error_count=0,
            point_usage=0,
            progress_pct=0.0,
            parameters={
                "keyword_ids": [k.id for k in keywords],
                "count": len(keywords)
            },
            results_summary={},
            created_at=now,
            expires_at=now + timedelta(seconds=max_runtime)
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @classmethod
    def start_background_job(cls, job_id: int, project_id: int, organization_id: int):
        """
        Dispatches background asyncio task for job execution.
        """
        loop = asyncio.get_event_loop()
        task = loop.create_task(
            cls._execute_keyword_job(
                job_id=job_id,
                project_id=project_id,
                organization_id=organization_id
            )
        )
        cls._active_tasks[job_id] = task

        def _cleanup(_):
            cls._active_tasks.pop(job_id, None)

        task.add_done_callback(_cleanup)

    @classmethod
    async def cancel_job(
        cls,
        db: AsyncSession,
        job_id: int,
        project_id: int,
        reason: str = "Cancelled by user"
    ) -> Optional[ScanJob]:
        """
        Cancels an active or queued job. Stops pending worker tasks immediately.
        """
        res = await db.execute(
            select(ScanJob).where(
                ScanJob.id == job_id,
                ScanJob.project_id == project_id
            )
        )
        job = res.scalars().first()
        if not job:
            return None

        # Cancel active background asyncio task if running
        task = cls._active_tasks.get(job_id)
        if task and not task.done():
            task.cancel()

        if job.status in (JobStatus.QUEUED.value, JobStatus.RUNNING.value, JobStatus.CANCEL_REQUESTED.value):
            job.status = JobStatus.CANCELLED.value
            job.current_stage = f"Scan cancelled ({reason})"
            job.cancelled_at = datetime.now(timezone.utc)
            job.error_message = reason
            await db.commit()
            await db.refresh(job)

        return job

    @classmethod
    async def _execute_keyword_job(
        cls,
        job_id: int,
        project_id: int,
        organization_id: int
    ):
        """
        Worker function executing keyword checks in bounded batches with cooperative cancellation.
        """
        start_mono = time.monotonic()
        max_runtime = getattr(settings, "SCAN_MAX_RUNTIME_SECONDS", 300)

        async with AsyncSessionLocal() as session:
            res = await session.execute(select(ScanJob).where(ScanJob.id == job_id))
            job = res.scalars().first()
            if not job:
                logger.error(f"[KEYWORD_JOB] Job #{job_id} not found.")
                return

            if job.status == JobStatus.CANCELLED.value:
                logger.info(f"[KEYWORD_JOB] Job #{job_id} was cancelled before starting.")
                return

            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.now(timezone.utc)
            job.current_stage = f"Scanning {job.total_items} keywords..."
            await session.commit()

            # Load target keywords
            kw_ids = job.parameters.get("keyword_ids", [])
            kw_res = await session.execute(
                select(Keyword).where(
                    Keyword.project_id == project_id,
                    Keyword.id.in_(kw_ids) if kw_ids else True
                )
            )
            keywords = kw_res.scalars().all()

        processed_count = 0
        successful_count = 0
        not_found_count = 0
        error_count = 0
        organic_found_count = 0
        local_pack_found_count = 0
        results_list: List[Dict[str, Any]] = []
        concurrency_limit = 3
        semaphore = asyncio.Semaphore(concurrency_limit)
        provider_name = "serpapi"

        async def _check_kw_task(kw_item: Keyword) -> Optional[Dict[str, Any]]:
            nonlocal processed_count, successful_count, not_found_count, error_count
            nonlocal organic_found_count, local_pack_found_count, provider_name

            # Check 5-minute timeout ceiling
            if time.monotonic() - start_mono > max_runtime:
                return None

            async with semaphore:
                async with AsyncSessionLocal() as kw_sess:
                    # Check cancellation in DB
                    chk_res = await kw_sess.execute(
                        select(ScanJob.status).where(ScanJob.id == job_id)
                    )
                    curr_st = chk_res.scalar_one_or_none()
                    if curr_st in (JobStatus.CANCEL_REQUESTED.value, JobStatus.CANCELLED.value):
                        return None

                    try:
                        k_res = await KeywordRankingService.check_keyword(
                            db=kw_sess,
                            keyword_id=kw_item.id,
                            project_id=project_id,
                            organization_id=organization_id
                        )
                        p_name = k_res.get("provider") or provider_name
                        provider_name = p_name

                        # Atomic provider usage recording
                        await ProviderUsageService.record_usage(
                            db=kw_sess,
                            organization_id=organization_id,
                            project_id=project_id,
                            job_id=job_id,
                            provider=p_name,
                            operation="keyword_serp_search",
                            units_consumed=1,
                            status="success" if k_res.get("status") in ("checked", "not_in_top_100") else "failed",
                            details=f"Keyword '{kw_item.keyword}' (id={kw_item.id})"
                        )

                        # Counter updates
                        processed_count += 1
                        if k_res.get("status") == "checked":
                            successful_count += 1
                            if k_res.get("organic_rank") is not None:
                                organic_found_count += 1
                            if k_res.get("local_pack_rank") is not None:
                                local_pack_found_count += 1
                        elif k_res.get("status") == "not_in_top_100":
                            not_found_count += 1
                        else:
                            error_count += 1

                        results_list.append(k_res)

                        # Progressive persistence to Job in DB
                        s_res = await kw_sess.execute(select(ScanJob).where(ScanJob.id == job_id))
                        active_j = s_res.scalars().first()
                        if active_j:
                            active_j.processed_items = processed_count
                            active_j.successful_items = successful_count
                            active_j.not_found_items = not_found_count
                            active_j.error_count = error_count
                            active_j.point_usage = processed_count
                            active_j.progress_pct = round((processed_count / max(1, active_j.total_items)) * 100, 1)
                            active_j.current_stage = f"Checked {processed_count}/{active_j.total_items} keywords"
                            await kw_sess.commit()

                        return k_res

                    except asyncio.CancelledError:
                        logger.info(f"[KEYWORD_JOB] Query for keyword {kw_item.id} cancelled.")
                        raise
                    except Exception as exc:
                        logger.warning(f"[KEYWORD_JOB] Query failed for keyword {kw_item.id}: {exc}")
                        processed_count += 1
                        error_count += 1
                        return {
                            "keyword_id": kw_item.id,
                            "keyword": kw_item.keyword,
                            "status": "error",
                            "error_message": str(exc)[:120]
                        }

        # Process in batches of 3
        batch_size = concurrency_limit
        is_interrupted = False

        for i in range(0, len(keywords), batch_size):
            # Check 5-minute timeout ceiling
            if time.monotonic() - start_mono > max_runtime:
                logger.warning(f"[KEYWORD_JOB] Job #{job_id} exceeded {max_runtime}s limit. Halting scan.")
                is_interrupted = True
                break

            # Check DB cancellation
            async with AsyncSessionLocal() as chk_sess:
                chk_res = await chk_sess.execute(select(ScanJob.status).where(ScanJob.id == job_id))
                curr_st = chk_res.scalar_one_or_none()
                if curr_st in (JobStatus.CANCEL_REQUESTED.value, JobStatus.CANCELLED.value):
                    logger.info(f"[KEYWORD_JOB] Job #{job_id} cancelled during execution. Halting queue.")
                    is_interrupted = True
                    break

            batch = keywords[i:i + batch_size]
            try:
                await asyncio.gather(*(_check_kw_task(kw) for kw in batch))
            except asyncio.CancelledError:
                is_interrupted = True
                break

        # Final Job State Resolution
        async with AsyncSessionLocal() as final_sess:
            res = await final_sess.execute(select(ScanJob).where(ScanJob.id == job_id))
            final_job = res.scalars().first()
            if not final_job:
                return

            final_job.processed_items = processed_count
            final_job.successful_items = successful_count
            final_job.not_found_items = not_found_count
            final_job.error_count = error_count
            final_job.point_usage = processed_count
            final_job.provider = provider_name
            final_job.completed_at = datetime.now(timezone.utc)

            is_timeout_expired = (time.monotonic() - start_mono > max_runtime) and (processed_count < len(keywords))

            if final_job.status == JobStatus.CANCELLED.value or is_interrupted and final_job.status in (JobStatus.CANCEL_REQUESTED.value, JobStatus.CANCELLED.value):
                final_job.status = JobStatus.CANCELLED.value
                final_job.current_stage = "Scan cancelled"
                final_job.cancelled_at = datetime.now(timezone.utc)
            elif is_timeout_expired:
                final_job.status = JobStatus.EXPIRED.value
                final_job.current_stage = f"Scan execution expired at 5-minute limit ({processed_count}/{final_job.total_items} completed)"
                final_job.error_message = f"Scan exceeded maximum runtime of {max_runtime} seconds."
            elif error_count > 0 and (successful_count > 0 or not_found_count > 0):
                final_job.status = JobStatus.COMPLETED_WITH_ERRORS.value
                final_job.progress_pct = 100.0
                final_job.current_stage = f"Scan completed with warnings: {successful_count} ranked, {not_found_count} not in Top 100, {error_count} errors"
            elif error_count > 0 and successful_count == 0 and not_found_count == 0:
                final_job.status = JobStatus.FAILED.value
                final_job.current_stage = f"Scan failed to complete ({error_count} provider errors)"
            else:
                final_job.status = JobStatus.COMPLETED.value
                final_job.progress_pct = 100.0
                final_job.current_stage = f"Scan complete: {successful_count} ranked, {not_found_count} not in Top 100"

            final_job.results_summary = {
                "total_scanned": processed_count,
                "checked_count": successful_count,
                "not_found_count": not_found_count,
                "error_count": error_count,
                "organic_count": organic_found_count,
                "local_pack_count": local_pack_found_count,
                "provider": provider_name,
                "results": results_list[:50]
            }

            await final_sess.commit()
            logger.info(
                f"[KEYWORD_JOB] Job #{job_id} terminal state='{final_job.status}' | "
                f"Processed={processed_count}/{final_job.total_items} | "
                f"Ranked={successful_count} | NotFound={not_found_count} | Errors={error_count}"
            )
