import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Callable, Dict, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.models.user import User, OrganizationMember
from app.models.project import Project
from app.models.ai_control import SystemSetting, OrganizationAIConfig, AIUsageLog
from app.services.ai import get_ai_provider

logger = logging.getLogger("locallift.services.ai_consumption")

class AIConsumptionService:
    @staticmethod
    async def get_or_create_org_config(db: AsyncSession, organization_id: int) -> OrganizationAIConfig:
        """Retrieves or initializes the AI configuration & credit wallet for an organization."""
        res = await db.execute(
            select(OrganizationAIConfig).where(OrganizationAIConfig.organization_id == organization_id)
        )
        config = res.scalars().first()
        if not config:
            config = OrganizationAIConfig(
                organization_id=organization_id,
                ai_enabled=True,
                ai_daily_limit=100,
                ai_monthly_limit=3000,
                ai_per_request_limit=5,
                ai_credits_balance=1000.0
            )
            db.add(config)
            await db.flush()
        return config

    @staticmethod
    async def get_global_ai_enabled(db: AsyncSession) -> bool:
        """Returns True if global AI kill switch is ON (enabled), False if OFF (disabled)."""
        res = await db.execute(
            select(SystemSetting).where(SystemSetting.key == "global_ai_enabled")
        )
        setting = res.scalars().first()
        if setting:
            return setting.value.strip().lower() == "true"
        return True  # Default enabled

    @staticmethod
    async def set_global_ai_enabled(db: AsyncSession, enabled: bool):
        """Updates the global AI kill switch setting."""
        res = await db.execute(
            select(SystemSetting).where(SystemSetting.key == "global_ai_enabled")
        )
        setting = res.scalars().first()
        if not setting:
            setting = SystemSetting(key="global_ai_enabled", value="true" if enabled else "false")
            db.add(setting)
        else:
            setting.value = "true" if enabled else "false"
        await db.commit()

    @staticmethod
    async def get_usage_status(db: AsyncSession, organization_id: int) -> Dict[str, Any]:
        """Calculates current day and month usage counters alongside limits and credit balance."""
        config = await AIConsumptionService.get_or_create_org_config(db, organization_id)
        global_enabled = await AIConsumptionService.get_global_ai_enabled(db)

        now = datetime.now(timezone.utc)
        start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

        # Count daily successful usage
        daily_res = await db.execute(
            select(func.coalesce(func.sum(AIUsageLog.credits_charged), 0.0)).where(
                AIUsageLog.organization_id == organization_id,
                AIUsageLog.status == "success",
                AIUsageLog.created_at >= start_of_day
            )
        )
        daily_usage = float(daily_res.scalar() or 0.0)

        # Count monthly successful usage
        monthly_res = await db.execute(
            select(func.coalesce(func.sum(AIUsageLog.credits_charged), 0.0)).where(
                AIUsageLog.organization_id == organization_id,
                AIUsageLog.status == "success",
                AIUsageLog.created_at >= start_of_month
            )
        )
        monthly_usage = float(monthly_res.scalar() or 0.0)

        return {
            "global_ai_enabled": global_enabled,
            "ai_enabled": config.ai_enabled and global_enabled,
            "credits_balance": round(config.ai_credits_balance, 2),
            "daily_limit": config.ai_daily_limit,
            "daily_usage": round(daily_usage, 2),
            "monthly_limit": config.ai_monthly_limit,
            "monthly_usage": round(monthly_usage, 2),
            "per_request_limit": config.ai_per_request_limit
        }

    @staticmethod
    async def resolve_organization_id(db: AsyncSession, user: User, project_id: Optional[int]) -> int:
        """Resolves the authoritative organization ID for the user / project."""
        if project_id:
            proj_res = await db.execute(select(Project.organization_id).where(Project.id == project_id))
            org_id = proj_res.scalar()
            if org_id:
                return org_id

        # Fallback to user's organization membership
        mem_res = await db.execute(
            select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id)
        )
        org_id = mem_res.scalars().first()
        if org_id:
            return org_id
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine organization context for AI request."
        )

    @staticmethod
    async def execute_gated_request(
        db: AsyncSession,
        user: User,
        project_id: Optional[int],
        task_type: str,
        provider_fn: Callable[[], Any],
        requested_cost: float = 1.0
    ) -> Any:
        """
        CENTRAL AI ACCESS GATE:
        Validates account status, global switch, org toggle, daily limit, monthly limit,
        per-request limit, and reserves credits BEFORE invoking the AI provider.
        """
        # 1. Account Status Check
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is inactive or suspended. Please contact administrator."
            )

        # 2. Global AI Kill Switch Check
        global_enabled = await AIConsumptionService.get_global_ai_enabled(db)
        if not global_enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI services are temporarily unavailable."
            )

        org_id = await AIConsumptionService.resolve_organization_id(db, user, project_id)

        # 3. Customer AI Enable Check & Org Config Retrieval
        config = await AIConsumptionService.get_or_create_org_config(db, org_id)
        if not config.ai_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AI access is currently disabled for this account."
            )

        # 4. Per-Request Limit Check
        if requested_cost > config.ai_per_request_limit:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This AI request exceeds your allowed request limit."
            )

        # 5. Server-side UTC Period Limits Check
        now = datetime.now(timezone.utc)
        start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

        daily_res = await db.execute(
            select(func.coalesce(func.sum(AIUsageLog.credits_charged), 0.0)).where(
                AIUsageLog.organization_id == org_id,
                AIUsageLog.status == "success",
                AIUsageLog.created_at >= start_of_day
            )
        )
        current_daily = float(daily_res.scalar() or 0.0)
        if (current_daily + requested_cost) > config.ai_daily_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Your daily AI usage limit has been reached."
            )

        monthly_res = await db.execute(
            select(func.coalesce(func.sum(AIUsageLog.credits_charged), 0.0)).where(
                AIUsageLog.organization_id == org_id,
                AIUsageLog.status == "success",
                AIUsageLog.created_at >= start_of_month
            )
        )
        current_monthly = float(monthly_res.scalar() or 0.0)
        if (current_monthly + requested_cost) > config.ai_monthly_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Your monthly AI usage limit has been reached."
            )

        # 6. Credit Balance Check & Atomic Reservation
        if config.ai_credits_balance < requested_cost:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="You do not have enough AI credits to complete this request."
            )

        # Reserve credits in-memory & flush within active transaction
        config.ai_credits_balance -= requested_cost
        await db.flush()

        # 7. AI Provider Execution (ONLY CALLED AFTER ALL CHECKS PASS)
        provider = get_ai_provider()
        provider_name = getattr(provider, "__class__", {}).__name__ if hasattr(provider, "__class__") else "AIProvider"
        model_name = getattr(provider, "model_name", "default")

        try:
            result = await provider_fn()
            
            # Record successful usage log & finalize credit charge
            log_entry = AIUsageLog(
                user_id=user.id,
                organization_id=org_id,
                project_id=project_id,
                task_type=task_type,
                provider=provider_name,
                model=model_name,
                credits_charged=requested_cost,
                status="success"
            )
            db.add(log_entry)
            await db.commit()
            return result

        except HTTPException:
            # Re-raise standard HTTP exceptions without modification, refunding credit
            config.ai_credits_balance += requested_cost
            log_entry = AIUsageLog(
                user_id=user.id,
                organization_id=org_id,
                project_id=project_id,
                task_type=task_type,
                provider=provider_name,
                model=model_name,
                credits_charged=0.0,
                status="failed",
                error_message="HTTPException raised during execution"
            )
            db.add(log_entry)
            await db.commit()
            raise

        except Exception as e:
            # Refund reservation on provider failure (0 charge)
            config.ai_credits_balance += requested_cost
            err_str = str(e)
            log_entry = AIUsageLog(
                user_id=user.id,
                organization_id=org_id,
                project_id=project_id,
                task_type=task_type,
                provider=provider_name,
                model=model_name,
                credits_charged=0.0,
                status="failed",
                error_message=err_str[:200]
            )
            db.add(log_entry)
            await db.commit()

            # Sanitize and normalize business errors
            logger.error(f"AI Provider error during {task_type}: {err_str}")
            if "AI_NOT_CONFIGURED" in err_str:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="AI_NOT_CONFIGURED: AI_API_KEY is not configured in backend environment settings."
                )
            elif "AI_RATE_LIMIT" in err_str:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="AI_RATE_LIMIT: Rate limit exceeded on AI provider. Please retry in a few moments."
                )
            elif "AI_TIMEOUT" in err_str:
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="AI_TIMEOUT: AI request timed out. Please try again."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"AI generation failed: {err_str[:150]}"
                )
