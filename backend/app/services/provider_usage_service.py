import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_

from app.models.provider_usage import ProviderUsageRecord
from app.models.connections import OrganizationSERPConfig
from app.models.ai_control import AIUsageLog, OrganizationAIConfig
from app.core.security import decrypt_token
import httpx

logger = logging.getLogger("locallift.services.provider_usage")


class ProviderUsageService:
    """
    Authoritative service for recording and analyzing external provider resource consumption
    (SERP queries, Geo-Grid points, AI tokens, etc.) with strict project vs. organization separation.
    """

    @classmethod
    async def record_usage(
        cls,
        db: AsyncSession,
        organization_id: int,
        project_id: int,
        provider: str,
        operation: str,
        job_id: Optional[int] = None,
        units_consumed: int = 1,
        cost_estimate: float = 0.0,
        status: str = "success",
        details: Optional[str] = None
    ) -> ProviderUsageRecord:
        """
        Records an atomic provider point/token consumption event.
        Guarantees association with organization_id, project_id, and optional job_id.
        """
        record = ProviderUsageRecord(
            organization_id=organization_id,
            project_id=project_id,
            job_id=job_id,
            provider=provider.lower().strip(),
            operation=operation,
            units_consumed=max(0, units_consumed),
            cost_estimate=cost_estimate,
            status=status,
            details=details,
            created_at=datetime.now(timezone.utc)
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    record_operation = record_usage

    @classmethod
    async def get_project_usage_summary(
        cls,
        db: AsyncSession,
        project_id: int,
        days: int = 30,
        organization_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Retrieves usage metrics scoped strictly to a single project.
        Separates SERP searches, Geo-Grid points, and AI consumption.
        """
        since_date = datetime.now(timezone.utc) - timedelta(days=days)

        # 1. Query ProviderUsageRecords for this project
        stmt = (
            select(ProviderUsageRecord)
            .where(
                ProviderUsageRecord.project_id == project_id,
                ProviderUsageRecord.created_at >= since_date
            )
            .order_by(ProviderUsageRecord.created_at.asc())
        )
        res = await db.execute(stmt)
        records = res.scalars().all()

        serp_requests = 0
        geo_grid_points = 0
        citation_requests = 0
        total_points = 0
        by_provider: Dict[str, int] = {}
        daily_map: Dict[str, Dict[str, int]] = {}

        for r in records:
            day_str = r.created_at.strftime("%Y-%m-%d")
            if day_str not in daily_map:
                daily_map[day_str] = {"serp": 0, "points": 0, "ai_tokens": 0}

            total_points += r.units_consumed
            daily_map[day_str]["points"] += r.units_consumed

            prov_key = r.provider or "unknown"
            by_provider[prov_key] = by_provider.get(prov_key, 0) + r.units_consumed

            if "geo_grid" in r.operation:
                geo_grid_points += r.units_consumed
            elif "citation" in r.operation:
                citation_requests += r.units_consumed
            elif "ai" in r.operation or r.provider in ("openai", "gemini", "claude", "groq", "anthropic"):
                pass  # AI operation tracked in provider points
            else:
                serp_requests += r.units_consumed
                daily_map[day_str]["serp"] += r.units_consumed

        # 2. Query AIUsageLog for this project
        ai_stmt = (
            select(AIUsageLog)
            .where(
                AIUsageLog.project_id == project_id,
                AIUsageLog.created_at >= since_date
            )
        )
        ai_res = await db.execute(ai_stmt)
        ai_logs = ai_res.scalars().all()

        ai_tokens_total = 0
        ai_requests_total = len(ai_logs)
        for log in ai_logs:
            tokens = log.total_tokens or 0
            ai_tokens_total += tokens
            day_str = log.created_at.strftime("%Y-%m-%d")
            if day_str in daily_map:
                daily_map[day_str]["ai_tokens"] += tokens
            else:
                daily_map[day_str] = {"serp": 0, "points": 0, "ai_tokens": tokens}

        # Convert daily_map into sorted timeline list
        timeline: List[Dict[str, Any]] = [
            {
                "date": date_k,
                "serp_requests": vals["serp"],
                "points": vals["points"],
                "ai_tokens": vals["ai_tokens"]
            }
            for date_k, vals in sorted(daily_map.items())
        ]

        return {
            "project_id": project_id,
            "period_days": days,
            "total_points": total_points,
            "serp_requests": serp_requests,
            "geo_grid_points": geo_grid_points,
            "citation_requests": citation_requests,
            "ai_tokens": ai_tokens_total,
            "ai_requests": ai_requests_total,
            "by_provider": by_provider,
            "timeline": timeline
        }

    @classmethod
    async def get_organization_usage_summary(
        cls,
        db: AsyncSession,
        organization_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Retrieves organization-wide resource consumption totals.
        """
        since_date = datetime.now(timezone.utc) - timedelta(days=days)

        res = await db.execute(
            select(func.sum(ProviderUsageRecord.units_consumed))
            .where(
                ProviderUsageRecord.organization_id == organization_id,
                ProviderUsageRecord.created_at >= since_date
            )
        )
        total_points = res.scalar() or 0

        # AI consumption
        ai_res = await db.execute(
            select(func.sum(AIUsageLog.total_tokens))
            .where(
                AIUsageLog.organization_id == organization_id,
                AIUsageLog.created_at >= since_date
            )
        )
        total_ai_tokens = ai_res.scalar() or 0

        return {
            "organization_id": organization_id,
            "period_days": days,
            "total_points": total_points,
            "total_ai_tokens": total_ai_tokens
        }

    @classmethod
    async def get_provider_status_and_forecast(
        cls,
        db: AsyncSession,
        organization_id: int,
        project_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Computes real provider status, usage percentage, remaining credits, and warnings.
        Factual resource check: never manufactures fake forecasts.
        """
        # Load SERP config
        stmt = select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == organization_id)
        res = await db.execute(stmt)
        serp_config = res.scalars().first()

        provider_name = serp_config.provider if serp_config else "serpapi"
        connection_status = serp_config.connection_status if serp_config else "not_configured"

        # Check account & usage metadata from cached or adapter inspection
        account_quota_info: Optional[Dict[str, Any]] = None

        if serp_config and serp_config.enabled and serp_config.usage_info:
            u = serp_config.usage_info
            a = serp_config.account_info or {}
            account_quota_info = {
                "model": u.get("model"),
                "used": u.get("used"),
                "limit": u.get("limit"),
                "remaining": u.get("remaining"),
                "balance": u.get("balance"),
                "currency": u.get("currency"),
                "usage_pct": u.get("percentage_used"),
                "account_email": a.get("account_email"),
                "plan_name": a.get("plan_name")
            }
        elif serp_config and serp_config.connection_status == "connected":
            try:
                from app.services.serp.registry import SERPProviderRegistry
                adapter = SERPProviderRegistry.get_adapter(provider_name)
                creds = SERPProviderRegistry.unpack_credentials(serp_config)
                if creds:
                    u_norm = await adapter.get_usage(creds, serp_config.base_url)
                    a_norm = await adapter.get_account_info(creds, serp_config.base_url)
                    account_quota_info = {
                        "model": u_norm.model,
                        "used": u_norm.used,
                        "limit": u_norm.limit,
                        "remaining": u_norm.remaining,
                        "balance": u_norm.balance,
                        "currency": u_norm.currency,
                        "usage_pct": u_norm.percentage_used,
                        "account_email": a_norm.account_email,
                        "plan_name": a_norm.plan_name
                    }
            except Exception as e:
                logger.debug(f"Unable to fetch provider account info: {e}")

        # Fallback to local 30-day usage counts if external account query was unavailable
        if not account_quota_info:
            res_count = await db.execute(
                select(func.sum(ProviderUsageRecord.units_consumed))
                .where(ProviderUsageRecord.organization_id == organization_id)
            )
            local_used = res_count.scalar() or 0
            account_quota_info = {
                "model": "requests",
                "used": local_used,
                "limit": None,
                "remaining": None,
                "usage_pct": None,
                "account_email": None,
                "plan_name": None
            }

        # Warnings evaluation (dynamic from provider data)
        warnings: List[str] = []
        if connection_status == "not_configured":
            warnings.append(f"SERP provider is not configured. Connect your {provider_name} account in Settings to enable rank tracking.")
        elif connection_status == "quota_exceeded":
            warnings.append(f"SERP account search quota has been reached on your {provider_name} account. Upgrade your provider plan.")
        elif account_quota_info.get("usage_pct") and account_quota_info["usage_pct"] >= 80.0:
            warnings.append(f"High SERP usage ({account_quota_info['usage_pct']}% of monthly searches consumed on {provider_name}).")
        elif account_quota_info.get("balance") is not None and account_quota_info["balance"] < 5.0:
            warnings.append(f"Low {provider_name} account balance (${account_quota_info['balance']:.2f} {account_quota_info.get('currency', 'USD')}).")

        return {
            "provider": provider_name,
            "connection_status": connection_status,
            "quota": account_quota_info,
            "warnings": warnings,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
