from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, or_, and_, text

from app.models.user import User, Organization
from app.models.project import Project, Website
from app.models.scan_job import ScanJob, JobStatus, JobType
from app.models.provider_usage import ProviderUsageRecord
from app.models.ai_control import AIUsageLog
from app.models.platform_audit import PlatformAuditLog


class MasterPlaceAnalyticsService:
    @staticmethod
    def _compute_date_range(
        range_str: str,
        start_date_str: Optional[str] = None,
        end_date_str: Optional[str] = None
    ):
        now = datetime.now(timezone.utc)
        if range_str == "today":
            start_date = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
            end_date = now
            interval = "hour"
            buckets_count = 24
        elif range_str == "7d":
            start_date = now - timedelta(days=7)
            end_date = now
            interval = "day"
            buckets_count = 7
        elif range_str == "90d":
            start_date = now - timedelta(days=90)
            end_date = now
            interval = "day"
            buckets_count = 30
        elif range_str == "custom" and start_date_str and end_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            except Exception:
                start_date = now - timedelta(days=30)
                end_date = now
            interval = "day"
            buckets_count = max(1, (end_date - start_date).days)
        else:  # default 30d
            start_date = now - timedelta(days=30)
            end_date = now
            interval = "day"
            buckets_count = 30

        # Preceding equivalent period for delta calculation
        duration = end_date - start_date
        prev_start = start_date - duration
        prev_end = start_date

        return start_date, end_date, interval, buckets_count, prev_start, prev_end

    @classmethod
    async def get_analytics_overview(
        cls,
        db: AsyncSession,
        range_str: str = "30d",
        start_date_str: Optional[str] = None,
        end_date_str: Optional[str] = None,
        customer_id: Optional[int] = None,
        project_id: Optional[int] = None,
        provider: Optional[str] = None,
        job_type: Optional[str] = None,
        feature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculates authoritative platform-wide analytics over time.
        Strictly computes metrics from database records without any mock or fabricated numbers.
        """
        start_date, end_date, interval, buckets_count, prev_start, prev_end = cls._compute_date_range(
            range_str, start_date_str, end_date_str
        )

        # Generate bucket timestamps
        bucket_list = []
        if interval == "hour":
            curr = start_date
            for i in range(24):
                bucket_list.append({
                    "start": curr,
                    "end": curr + timedelta(hours=1),
                    "label": curr.strftime("%H:00"),
                    "date": curr.strftime("%Y-%m-%d %H:00")
                })
                curr += timedelta(hours=1)
        else:
            step_days = max(1, (end_date - start_date).days // buckets_count) if buckets_count > 0 else 1
            curr = start_date
            while curr < end_date:
                b_end = min(end_date, curr + timedelta(days=step_days))
                bucket_list.append({
                    "start": curr,
                    "end": b_end,
                    "label": curr.strftime("%b %d"),
                    "date": curr.strftime("%Y-%m-%d")
                })
                curr = b_end

        # 1. Fetch raw datasets for the active time window
        # 1a. Organizations
        org_filter = []
        if customer_id:
            org_filter.append(Organization.id == customer_id)
        orgs_res = await db.execute(select(Organization).where(*org_filter))
        all_orgs = orgs_res.scalars().all()

        # 1b. Projects & Websites
        proj_filter = []
        if customer_id:
            proj_filter.append(Project.organization_id == customer_id)
        if project_id:
            proj_filter.append(Project.id == project_id)
        projs_res = await db.execute(select(Project).where(*proj_filter))
        all_projs = projs_res.scalars().all()
        proj_ids = [p.id for p in all_projs]

        web_filter = []
        if proj_ids:
            web_filter.append(Website.project_id.in_(proj_ids))
        webs_res = await db.execute(select(Website).where(*web_filter))
        all_webs = webs_res.scalars().all()

        # 1c. Scan Jobs
        job_filter = [ScanJob.created_at >= start_date, ScanJob.created_at <= end_date]
        if customer_id:
            job_filter.append(ScanJob.organization_id == customer_id)
        if project_id:
            job_filter.append(ScanJob.project_id == project_id)
        if job_type:
            job_filter.append(ScanJob.job_type == job_type)
        jobs_res = await db.execute(select(ScanJob).where(and_(*job_filter)))
        jobs_in_window = jobs_res.scalars().all()

        # 1d. Provider Usage Records
        usage_filter = [ProviderUsageRecord.created_at >= start_date, ProviderUsageRecord.created_at <= end_date]
        if customer_id:
            usage_filter.append(ProviderUsageRecord.organization_id == customer_id)
        if project_id:
            usage_filter.append(ProviderUsageRecord.project_id == project_id)
        if provider:
            usage_filter.append(ProviderUsageRecord.provider == provider)
        usages_res = await db.execute(select(ProviderUsageRecord).where(and_(*usage_filter)))
        usages_in_window = usages_res.scalars().all()

        # 1e. AI Usage Logs
        ai_filter = [AIUsageLog.created_at >= start_date, AIUsageLog.created_at <= end_date]
        if customer_id:
            ai_filter.append(AIUsageLog.organization_id == customer_id)
        if project_id:
            ai_filter.append(AIUsageLog.project_id == project_id)
        if provider:
            ai_filter.append(AIUsageLog.provider == provider)
        if feature:
            ai_filter.append(AIUsageLog.task_type == feature)
        ai_res = await db.execute(select(AIUsageLog).where(and_(*ai_filter)))
        ai_logs_in_window = ai_res.scalars().all()

        # 1f. Platform Audit Logs
        audit_filter = [PlatformAuditLog.timestamp >= start_date, PlatformAuditLog.timestamp <= end_date]
        if customer_id:
            audit_filter.append(PlatformAuditLog.organization_id == customer_id)
        if project_id:
            audit_filter.append(PlatformAuditLog.project_id == project_id)
        audits_res = await db.execute(select(PlatformAuditLog).where(and_(*audit_filter)))
        audits_in_window = audits_res.scalars().all()

        # Build time-series bucket series
        customer_growth_series = []
        project_website_series = []
        scan_activity_series = []
        scan_health_series = []
        google_api_series = []
        google_error_series = []
        serp_usage_series = []
        serp_performance_series = []
        ai_token_series = []
        system_perf_series = []
        job_queue_series = []
        platform_error_series = []
        alert_series = []

        total_scans_in_period = len(jobs_in_window)
        total_serp_requests_in_period = 0
        total_ai_tokens_in_period = 0
        total_google_requests_in_period = 0
        total_api_errors_in_period = 0

        def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        for b in bucket_list:
            b_start = b["start"]
            b_end = b["end"]
            b_label = b["label"]
            b_date = b["date"]

            # Customer growth
            new_cust = sum(1 for o in all_orgs if o.created_at and b_start <= _to_utc(o.created_at) < b_end)
            active_cust = sum(1 for o in all_orgs if o.status == "active" and o.created_at and _to_utc(o.created_at) <= b_end)
            susp_cust = sum(1 for o in all_orgs if o.status == "suspended" and o.created_at and _to_utc(o.created_at) <= b_end)
            customer_growth_series.append({
                "date": b_date,
                "label": b_label,
                "new_customers": new_cust,
                "active_customers": active_cust,
                "suspended_customers": susp_cust
            })

            # Project & Website growth
            new_proj = sum(1 for p in all_projs if p.created_at and b_start <= _to_utc(p.created_at) < b_end)
            tot_proj = sum(1 for p in all_projs if p.created_at and _to_utc(p.created_at) <= b_end)
            new_web = sum(1 for w in all_webs if w.created_at and b_start <= _to_utc(w.created_at) < b_end)
            tot_web = sum(1 for w in all_webs if w.created_at and _to_utc(w.created_at) <= b_end)
            project_website_series.append({
                "date": b_date,
                "label": b_label,
                "new_projects": new_proj,
                "total_projects": tot_proj,
                "new_websites": new_web,
                "total_websites": tot_web
            })

            # Scan activity
            b_jobs = [j for j in jobs_in_window if j.created_at and b_start <= _to_utc(j.created_at) < b_end]
            kw_scans = sum(1 for j in b_jobs if j.job_type in ["keyword_rank", "keyword_tracker"])
            geo_scans = sum(1 for j in b_jobs if j.job_type in ["geo_grid", "geogrid"])
            web_audits = sum(1 for j in b_jobs if j.job_type in ["seo_audit", "website_audit"])
            loc_audits = sum(1 for j in b_jobs if j.job_type in ["local_audit", "citation_scan"])
            gbp_syncs = sum(1 for j in b_jobs if "gbp" in (j.job_type or ""))
            other_scans = len(b_jobs) - (kw_scans + geo_scans + web_audits + loc_audits + gbp_syncs)
            scan_activity_series.append({
                "date": b_date,
                "label": b_label,
                "keyword_scan": kw_scans,
                "geo_grid": geo_scans,
                "website_audit": web_audits,
                "local_audit": loc_audits,
                "gbp_sync": gbp_syncs,
                "other": max(0, other_scans),
                "total_scans": len(b_jobs)
            })

            # Scan Health
            completed_jobs = sum(1 for j in b_jobs if j.status in [JobStatus.COMPLETED.value, "completed"])
            failed_jobs = sum(1 for j in b_jobs if j.status in [JobStatus.FAILED.value, JobStatus.COMPLETED_WITH_ERRORS.value, "failed"])
            cancelled_jobs = sum(1 for j in b_jobs if j.status in [JobStatus.CANCELLED.value, "cancelled"])
            timed_out_jobs = sum(1 for j in b_jobs if j.status in [JobStatus.EXPIRED.value, "timeout", "timed_out", "expired"])
            running_jobs = sum(1 for j in b_jobs if j.status in [JobStatus.RUNNING.value, JobStatus.QUEUED.value, "running", "queued"])
            resolved_jobs = completed_jobs + failed_jobs + timed_out_jobs
            success_rate = round((completed_jobs / resolved_jobs) * 100, 1) if resolved_jobs > 0 else None
            failure_rate = round(((failed_jobs + timed_out_jobs) / resolved_jobs) * 100, 1) if resolved_jobs > 0 else None

            scan_health_series.append({
                "date": b_date,
                "label": b_label,
                "completed": completed_jobs,
                "failed": failed_jobs,
                "cancelled": cancelled_jobs,
                "timed_out": timed_out_jobs,
                "running": running_jobs,
                "success_rate": success_rate,
                "failure_rate": failure_rate
            })

            # Usages in bucket
            b_usages = [u for u in usages_in_window if u.created_at and b_start <= _to_utc(u.created_at) < b_end]

            # Google API usage
            b_google = [u for u in b_usages if "google" in (u.provider or "").lower() or (u.operation or "").startswith("gbp_")]
            gbp_reqs = sum(u.units_consumed for u in b_google if "gbp" in (u.operation or "") or "business" in (u.provider or ""))
            gsc_reqs = sum(u.units_consumed for u in b_google if "search_console" in (u.operation or "") or "gsc" in (u.provider or ""))
            ga4_reqs = sum(u.units_consumed for u in b_google if "analytics" in (u.operation or "") or "ga4" in (u.provider or ""))
            places_reqs = sum(u.units_consumed for u in b_google if "place" in (u.operation or "") or "places" in (u.provider or "") or "map" in (u.provider or ""))
            tot_google = sum(u.units_consumed for u in b_google)
            google_errs = sum(1 for u in b_google if u.status != "success")
            total_google_requests_in_period += tot_google

            google_api_series.append({
                "date": b_date,
                "label": b_label,
                "gbp_requests": gbp_reqs,
                "gsc_requests": gsc_reqs,
                "ga4_requests": ga4_reqs,
                "places_requests": places_reqs,
                "total_requests": tot_google,
                "errors": google_errs
            })

            # Google API error breakdown
            e401 = sum(1 for u in b_google if "401" in (u.details or ""))
            e403 = sum(1 for u in b_google if "403" in (u.details or "") or "permission" in (u.details or "").lower())
            e429 = sum(1 for u in b_google if "429" in (u.details or "") or "quota" in (u.details or "").lower() or "rate" in (u.details or "").lower())
            e5xx = sum(1 for u in b_google if any(c in (u.details or "") for c in ["500", "502", "503", "504"]))
            etimeout = sum(1 for u in b_google if "timeout" in (u.details or "").lower())
            eother = max(0, google_errs - (e401 + e403 + e429 + e5xx + etimeout))
            google_error_series.append({
                "date": b_date,
                "label": b_label,
                "e401": e401,
                "e403": e403,
                "e429": e429,
                "e5xx": e5xx,
                "timeout": etimeout,
                "other": eother,
                "total_errors": google_errs
            })

            # SERP provider usage
            b_serp = [u for u in b_usages if any(p in (u.provider or "").lower() for p in ["serp", "serpapi", "openserp", "dataforseo"])]
            serpapi_reqs = sum(u.units_consumed for u in b_serp if "serpapi" in (u.provider or "").lower())
            openserp_reqs = sum(u.units_consumed for u in b_serp if "openserp" in (u.provider or "").lower())
            other_serp_reqs = sum(u.units_consumed for u in b_serp if not any(p in (u.provider or "").lower() for p in ["serpapi", "openserp"]))
            tot_serp = sum(u.units_consumed for u in b_serp)
            serp_success = sum(u.units_consumed for u in b_serp if u.status == "success")
            serp_failed = sum(u.units_consumed for u in b_serp if u.status != "success")
            total_serp_requests_in_period += tot_serp

            serp_usage_series.append({
                "date": b_date,
                "label": b_label,
                "serpapi_requests": serpapi_reqs,
                "openserp_requests": openserp_reqs,
                "other_requests": other_serp_reqs,
                "total_requests": tot_serp,
                "successful": serp_success,
                "failed": serp_failed
            })

            serp_res_count = len(b_serp)
            serp_success_rate = round((serp_success / tot_serp) * 100, 1) if tot_serp > 0 else None
            serp_performance_series.append({
                "date": b_date,
                "label": b_label,
                "success_rate": serp_success_rate,
                "failure_rate": round((serp_failed / tot_serp) * 100, 1) if tot_serp > 0 else None,
                "total_queries": tot_serp
            })

            # AI Token Usage
            b_ai = [a for a in ai_logs_in_window if a.created_at and b_start <= _to_utc(a.created_at) < b_end]
            in_tokens = sum(a.input_tokens or 0 for a in b_ai)
            out_tokens = sum(a.output_tokens or 0 for a in b_ai)
            tot_tokens = sum(a.total_tokens or (in_tokens + out_tokens) for a in b_ai)
            tot_cost = round(sum(a.estimated_cost or a.actual_cost or 0.0 for a in b_ai), 4)
            total_ai_tokens_in_period += tot_tokens

            ai_token_series.append({
                "date": b_date,
                "label": b_label,
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "total_tokens": tot_tokens,
                "estimated_cost_usd": tot_cost,
                "requests_count": len(b_ai)
            })

            # System Performance (durations)
            durations = []
            for j in b_jobs:
                if getattr(j, "duration_seconds", None) is not None and j.duration_seconds > 0:
                    durations.append(j.duration_seconds)
                elif j.completed_at and j.started_at:
                    d = (j.completed_at - j.started_at).total_seconds()
                    if d > 0:
                        durations.append(d)
            avg_duration = round(sum(durations) / len(durations), 1) if durations else None
            system_perf_series.append({
                "date": b_date,
                "label": b_label,
                "avg_job_duration_sec": avg_duration,
                "total_jobs": len(b_jobs)
            })

            # Job queue trend
            job_queue_series.append({
                "date": b_date,
                "label": b_label,
                "queued_jobs": sum(1 for j in b_jobs if j.status == JobStatus.QUEUED.value),
                "running_jobs": sum(1 for j in b_jobs if j.status == JobStatus.RUNNING.value),
                "failed_jobs": sum(1 for j in b_jobs if j.status in [JobStatus.FAILED.value, JobStatus.COMPLETED_WITH_ERRORS.value])
            })

            # Platform errors
            b_audits = [a for a in audits_in_window if a.timestamp and b_start <= _to_utc(a.timestamp) < b_end]
            b_api_errs = sum(1 for a in b_audits if a.status in ["FAILED", "WARNING"] or "ERROR" in (a.action or ""))
            total_api_errors_in_period += b_api_errs + failed_jobs + serp_failed + google_errs
            platform_error_series.append({
                "date": b_date,
                "label": b_label,
                "api_errors": b_api_errs,
                "scan_failures": failed_jobs,
                "provider_errors": serp_failed + google_errs,
                "total_errors": b_api_errs + failed_jobs + serp_failed + google_errs
            })

            # Alerts
            crit_alerts = sum(1 for a in b_audits if (a.status == "FAILED" or "CRITICAL" in (a.action or "") or "KILL_SWITCH" in (a.action or "")))
            warn_alerts = sum(1 for a in b_audits if (a.status == "WARNING" or "SUSPEND" in (a.action or "")))
            info_alerts = max(0, len(b_audits) - (crit_alerts + warn_alerts))
            alert_series.append({
                "date": b_date,
                "label": b_label,
                "critical": crit_alerts,
                "warning": warn_alerts,
                "info": info_alerts,
                "total": len(b_audits)
            })

        # 2. AI Provider Comparison
        ai_providers_map = {}
        for a in ai_logs_in_window:
            p_name = a.provider or "unknown"
            if p_name not in ai_providers_map:
                ai_providers_map[p_name] = {
                    "provider": p_name,
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "errors": 0,
                    "estimated_cost_usd": 0.0
                }
            item = ai_providers_map[p_name]
            item["requests"] += 1
            in_t = a.input_tokens or 0
            out_t = a.output_tokens or 0
            item["input_tokens"] += in_t
            item["output_tokens"] += out_t
            item["total_tokens"] += (a.total_tokens or (in_t + out_t))
            if a.status != "success":
                item["errors"] += 1
            item["estimated_cost_usd"] += (a.estimated_cost or a.actual_cost or 0.0)

        ai_provider_comparison = [
            {**v, "estimated_cost_usd": round(v["estimated_cost_usd"], 4)}
            for v in ai_providers_map.values()
        ]

        # 3. Top Customers by Resource Usage
        cust_usage_map = {}
        for o in all_orgs:
            cust_usage_map[o.id] = {
                "id": o.id,
                "name": o.name,
                "status": o.status,
                "serp_requests": 0,
                "ai_tokens": 0,
                "google_requests": 0,
                "scan_jobs": 0,
                "total_cost_usd": 0.0
            }

        for u in usages_in_window:
            if u.organization_id in cust_usage_map:
                entry = cust_usage_map[u.organization_id]
                entry["total_cost_usd"] += (u.cost_estimate or 0.0)
                if any(p in (u.provider or "").lower() for p in ["serp", "openserp"]):
                    entry["serp_requests"] += u.units_consumed
                elif "google" in (u.provider or "").lower():
                    entry["google_requests"] += u.units_consumed

        for a in ai_logs_in_window:
            if a.organization_id in cust_usage_map:
                entry = cust_usage_map[a.organization_id]
                entry["ai_tokens"] += (a.total_tokens or ((a.input_tokens or 0) + (a.output_tokens or 0)))
                entry["total_cost_usd"] += (a.estimated_cost or a.actual_cost or 0.0)

        for j in jobs_in_window:
            if j.organization_id in cust_usage_map:
                cust_usage_map[j.organization_id]["scan_jobs"] += 1

        top_customers_usage = sorted(
            cust_usage_map.values(),
            key=lambda c: (c["serp_requests"] + c["google_requests"] + c["scan_jobs"] + (c["ai_tokens"] // 100)),
            reverse=True
        )[:15]
        for c in top_customers_usage:
            c["total_cost_usd"] = round(c["total_cost_usd"], 4)

        # 4. Top Websites by Resource Usage
        web_usage_map = {}
        proj_to_org = {p.id: p.organization_id for p in all_projs}
        proj_to_name = {p.id: p.name for p in all_projs}
        org_to_name = {o.id: o.name for o in all_orgs}

        for w in all_webs:
            web_domain = getattr(w, "url", getattr(w, "domain", "unknown"))
            web_usage_map[w.id] = {
                "id": w.id,
                "domain": web_domain,
                "project_id": w.project_id,
                "project_name": proj_to_name.get(w.project_id, "Unknown"),
                "org_name": org_to_name.get(proj_to_org.get(w.project_id), "Unknown"),
                "serp_requests": 0,
                "ai_tokens": 0,
                "google_requests": 0,
                "scan_jobs": 0
            }

        for u in usages_in_window:
            # Match project
            matched_webs = [w for w in all_webs if w.project_id == u.project_id]
            for w in matched_webs:
                entry = web_usage_map[w.id]
                if any(p in (u.provider or "").lower() for p in ["serp", "openserp"]):
                    entry["serp_requests"] += u.units_consumed
                elif "google" in (u.provider or "").lower():
                    entry["google_requests"] += u.units_consumed

        for a in ai_logs_in_window:
            matched_webs = [w for w in all_webs if w.project_id == a.project_id]
            for w in matched_webs:
                entry = web_usage_map[w.id]
                entry["ai_tokens"] += (a.total_tokens or ((a.input_tokens or 0) + (a.output_tokens or 0)))

        for j in jobs_in_window:
            matched_webs = [w for w in all_webs if w.project_id == j.project_id]
            for w in matched_webs:
                web_usage_map[w.id]["scan_jobs"] += 1

        top_websites_usage = sorted(
            web_usage_map.values(),
            key=lambda w: (w["serp_requests"] + w["google_requests"] + w["scan_jobs"] + (w["ai_tokens"] // 100)),
            reverse=True
        )[:15]

        # 5. Preceding period comparisons
        prev_jobs_res = await db.execute(
            select(func.count(ScanJob.id)).where(
                and_(ScanJob.created_at >= prev_start, ScanJob.created_at < prev_end)
            )
        )
        prev_jobs_count = prev_jobs_res.scalar() or 0

        prev_serp_res = await db.execute(
            select(func.sum(ProviderUsageRecord.units_consumed)).where(
                and_(
                    ProviderUsageRecord.created_at >= prev_start,
                    ProviderUsageRecord.created_at < prev_end,
                    or_(
                        ProviderUsageRecord.provider.like("%serp%"),
                        ProviderUsageRecord.provider.like("%openserp%")
                    )
                )
            )
        )
        prev_serp_count = prev_serp_res.scalar() or 0

        prev_ai_res = await db.execute(
            select(func.sum(AIUsageLog.total_tokens)).where(
                and_(AIUsageLog.created_at >= prev_start, AIUsageLog.created_at < prev_end)
            )
        )
        prev_ai_count = prev_ai_res.scalar() or 0

        def _calc_growth(curr: float, prev: float) -> Optional[float]:
            if prev <= 0:
                return None if curr == 0 else 100.0
            return round(((curr - prev) / prev) * 100, 1)

        return {
            "meta": {
                "range": range_str,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "interval": interval,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "filters_applied": {
                    "customer_id": customer_id,
                    "project_id": project_id,
                    "provider": provider,
                    "job_type": job_type,
                    "feature": feature
                }
            },
            "kpis": {
                "total_scans": total_scans_in_period,
                "scans_growth_pct": _calc_growth(total_scans_in_period, prev_jobs_count),
                "total_serp_requests": total_serp_requests_in_period,
                "serp_growth_pct": _calc_growth(total_serp_requests_in_period, prev_serp_count),
                "total_ai_tokens": total_ai_tokens_in_period,
                "ai_growth_pct": _calc_growth(total_ai_tokens_in_period, prev_ai_count),
                "total_google_requests": total_google_requests_in_period,
                "total_errors": total_api_errors_in_period
            },
            "time_series": {
                "customer_growth": customer_growth_series,
                "project_website_growth": project_website_series,
                "scan_activity": scan_activity_series,
                "scan_health": scan_health_series,
                "google_api_usage": google_api_series,
                "google_api_errors": google_error_series,
                "serp_usage": serp_usage_series,
                "serp_performance": serp_performance_series,
                "ai_token_usage": ai_token_series,
                "system_performance": system_perf_series,
                "job_queue_trend": job_queue_series,
                "platform_error_trend": platform_error_series,
                "alert_trend": alert_series
            },
            "ai_provider_comparison": ai_provider_comparison,
            "top_customers_usage": top_customers_usage,
            "top_websites_usage": top_websites_usage
        }
