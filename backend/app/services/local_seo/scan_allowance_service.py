import logging
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import Settings
from app.models.analytics import OrganizationScanAllowance
from app.models.user import Organization
from app.models.connections import OrganizationSERPConfig

logger = logging.getLogger("locallift.scan_allowance")
_settings = Settings()


class ScanAllowanceService:
    """
    Manages organization-level monthly LocalLift audit allowances.
    Enforces configurable monthly scan limits while providing clear usage feedback.
    """

    @staticmethod
    def get_current_year_month() -> str:
        now = datetime.now(timezone.utc)
        return f"{now.year:04d}-{now.month:02d}"

    @classmethod
    async def get_or_create_allowance(
        cls,
        db: AsyncSession,
        organization_id: int,
        year_month: Optional[str] = None
    ) -> OrganizationScanAllowance:
        ym = year_month or cls.get_current_year_month()

        res = await db.execute(
            select(OrganizationScanAllowance).where(
                OrganizationScanAllowance.organization_id == organization_id,
                OrganizationScanAllowance.year_month == ym
            )
        )
        allowance = res.scalars().first()

        if not allowance:
            # Determine configured limit (fallback to default setting)
            allowed = _settings.LOCAL_AUDIT_MONTHLY_LIMIT
            org_res = await db.execute(select(Organization).where(Organization.id == organization_id))
            org = org_res.scalars().first()
            if org and org.plan:
                plan_lower = org.plan.lower()
                if "enterprise" in plan_lower:
                    allowed = max(allowed, 50)
                elif "agency" in plan_lower:
                    allowed = max(allowed, 20)
                elif "pro" in plan_lower:
                    allowed = max(allowed, 10)

            allowance = OrganizationScanAllowance(
                organization_id=organization_id,
                year_month=ym,
                used_scans=0,
                allowed_scans=allowed,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(allowance)
            await db.commit()
            await db.refresh(allowance)

        return allowance

    @classmethod
    async def check_allowance(
        cls,
        db: AsyncSession,
        organization_id: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Checks if the organization has remaining audit allowance for the current month.
        Returns: (is_allowed, status_dict)
        """
        allowance = await cls.get_or_create_allowance(db, organization_id)
        
        # Check if organization has BYO SerpApi configured
        serp_res = await db.execute(
            select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == organization_id)
        )
        serp_cfg = serp_res.scalars().first()
        is_byo = bool(serp_cfg and serp_cfg.api_key and serp_cfg.connection_status == "connected")

        remaining = max(0, allowance.allowed_scans - allowance.used_scans)
        has_credit = remaining > 0

        status_dict = {
            "organization_id": organization_id,
            "year_month": allowance.year_month,
            "used": allowance.used_scans,
            "allowed": allowance.allowed_scans,
            "remaining": remaining,
            "is_byo_serp": is_byo,
            "has_credit": has_credit,
            "reset_date": f"{allowance.year_month}-01 (Monthly reset)"
        }

        return (has_credit, status_dict)

    @classmethod
    async def consume_scan(
        cls,
        db: AsyncSession,
        organization_id: int,
        project_id: Optional[int] = None,
        scan_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Atomically increments the consumed scan count when external audit execution starts.
        """
        allowance = await cls.get_or_create_allowance(db, organization_id)
        allowance.used_scans += 1
        allowance.last_scan_at = datetime.now(timezone.utc)
        allowance.updated_at = datetime.now(timezone.utc)
        
        db.add(allowance)
        await db.commit()
        await db.refresh(allowance)

        logger.info(
            f"[SCAN_ALLOWANCE] Consumed 1 scan credit for Org #{organization_id} (Project #{project_id}, Scan #{scan_id}). "
            f"Usage: {allowance.used_scans}/{allowance.allowed_scans} ({allowance.year_month})"
        )

        return {
            "organization_id": organization_id,
            "year_month": allowance.year_month,
            "used": allowance.used_scans,
            "allowed": allowance.allowed_scans,
            "remaining": max(0, allowance.allowed_scans - allowance.used_scans)
        }
