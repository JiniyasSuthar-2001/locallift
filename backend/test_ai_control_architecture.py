import sys
import os
import asyncio
import unittest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

# Ensure backend directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database import Base
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project
from app.models.ai_control import SystemSetting, OrganizationAIConfig, AIUsageLog
from app.services.ai_consumption_service import AIConsumptionService
from app.services.ai import set_ai_provider, AIProvider
from app.api.v1.ai import analyze_project_query, generate_review_response
from app.schemas.ai import AIChatRequest
from fastapi import HTTPException

# Tracking Mock AI Provider to verify call counts
class MockCallTrackerProvider(AIProvider):
    def __init__(self):
        self.call_count = 0

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def model_name(self) -> str:
        return "mock-tracker-model"

    async def analyze_project_query(self, query: str, context: dict) -> dict:
        self.call_count += 1
        return {
            "summary": "Mock analysis succeeded",
            "likely_causes": [{"category": "Technical", "description": "Mock cause", "confidence": "Confirmed"}],
            "evidence_points": ["Point 1"],
            "recommended_actions": ["Action 1"],
            "actionable_tasks": ["Task 1"]
        }

    async def draft_review_response(self, author_name: str, rating: int, review_text: str, business_name: str, business_category: str = None) -> str:
        self.call_count += 1
        return f"Dear {author_name}, thank you for your feedback!"

    async def generate_content_opportunities(self, context: dict) -> list:
        self.call_count += 1
        return [{"topic": "Mock Topic", "page_type": "Service Page"}]

class FailingMockProvider(AIProvider):
    @property
    def is_configured(self) -> bool:
        return True

    @property
    def model_name(self) -> str:
        return "failing-mock-model"

    async def analyze_project_query(self, query: str, context: dict) -> dict:
        raise RuntimeError("AI Provider connection dropped")

    async def draft_review_response(self, author_name: str, rating: int, review_text: str, business_name: str, business_category: str = None) -> str:
        raise RuntimeError("AI Provider connection dropped")

    async def generate_content_opportunities(self, context: dict) -> list:
        raise RuntimeError("AI Provider connection dropped")


class TestAIControlArchitecture(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create an in-memory SQLite database for testing
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Setup test data: Superuser, Normal User 1 (Org 1), Normal User 2 (Org 2)
        async with self.async_session() as db:
            self.super_user = User(email="master@locallift.test", hashed_password="pw", is_active=True, is_superuser=True)
            self.user1 = User(email="user1@org1.test", hashed_password="pw", is_active=True, is_superuser=False)
            self.user2 = User(email="user2@org2.test", hashed_password="pw", is_active=True, is_superuser=False)
            self.inactive_user = User(email="inactive@org1.test", hashed_password="pw", is_active=False, is_superuser=False)

            db.add_all([self.super_user, self.user1, self.user2, self.inactive_user])
            await db.flush()

            self.org1 = Organization(name="Org One", slug="org-one", plan="pro")
            self.org2 = Organization(name="Org Two", slug="org-two", plan="pro")
            db.add_all([self.org1, self.org2])
            await db.flush()

            db.add(OrganizationMember(organization_id=self.org1.id, user_id=self.user1.id, role=OrgRole.OWNER))
            db.add(OrganizationMember(organization_id=self.org1.id, user_id=self.inactive_user.id, role=OrgRole.MANAGER))
            db.add(OrganizationMember(organization_id=self.org2.id, user_id=self.user2.id, role=OrgRole.OWNER))
            await db.flush()

            self.proj1 = Project(organization_id=self.org1.id, name="Project 1", domain="p1.com", primary_category="Plumbing")
            self.proj2 = Project(organization_id=self.org2.id, name="Project 2", domain="p2.com", primary_category="HVAC")
            db.add_all([self.proj1, self.proj2])
            await db.commit()

        self.tracker = MockCallTrackerProvider()
        set_ai_provider(self.tracker)

    async def asyncTearDown(self):
        set_ai_provider(None)
        await self.engine.dispose()

    async def test_01_active_customer_ai_enabled_success(self):
        """Active customer with AI enabled, limits okay -> request succeeds & charges credits."""
        async with self.async_session() as db:
            req = AIChatRequest(project_id=self.proj1.id, query="Why did my rankings drop?")
            res = await analyze_project_query(req=req, current_user=self.user1, db=db)
            self.assertIsNotNone(res)
            self.assertEqual(self.tracker.call_count, 1)

            status_data = await AIConsumptionService.get_usage_status(db, self.org1.id)
            self.assertEqual(status_data["daily_usage"], 1.0)
            self.assertEqual(status_data["credits_balance"], 999.0)

    async def test_02_global_ai_disabled_zero_provider_calls(self):
        """When Global AI is disabled, request is rejected with 503 and provider call count is 0."""
        async with self.async_session() as db:
            await AIConsumptionService.set_global_ai_enabled(db, False)

            req = AIChatRequest(project_id=self.proj1.id, query="Why did my rankings drop?")
            with self.assertRaises(HTTPException) as ctx:
                await analyze_project_query(req=req, current_user=self.user1, db=db)
            
            self.assertEqual(ctx.exception.status_code, 503)
            self.assertIn("temporarily unavailable", ctx.exception.detail)
            self.assertEqual(self.tracker.call_count, 0)

    async def test_03_customer_ai_disabled_zero_provider_calls(self):
        """When customer AI is disabled, request is rejected with 403 and provider call count is 0."""
        async with self.async_session() as db:
            config = await AIConsumptionService.get_or_create_org_config(db, self.org1.id)
            config.ai_enabled = False
            await db.commit()

            req = AIChatRequest(project_id=self.proj1.id, query="Why did my rankings drop?")
            with self.assertRaises(HTTPException) as ctx:
                await analyze_project_query(req=req, current_user=self.user1, db=db)

            self.assertEqual(ctx.exception.status_code, 403)
            self.assertIn("disabled for this account", ctx.exception.detail)
            self.assertEqual(self.tracker.call_count, 0)

    async def test_04_customer_a_disabled_customer_b_unaffected(self):
        """Disabling Org 1 AI does NOT affect Org 2."""
        async with self.async_session() as db:
            config1 = await AIConsumptionService.get_or_create_org_config(db, self.org1.id)
            config1.ai_enabled = False
            await db.commit()

            req = AIChatRequest(project_id=self.proj2.id, query="How is HVAC performing?")
            res = await analyze_project_query(req=req, current_user=self.user2, db=db)
            self.assertIsNotNone(res)
            self.assertEqual(self.tracker.call_count, 1)

    async def test_05_daily_limit_reached_rejected(self):
        """When daily limit is reached, subsequent request is rejected with 429 and provider call count is 0."""
        async with self.async_session() as db:
            config = await AIConsumptionService.get_or_create_org_config(db, self.org1.id)
            config.ai_daily_limit = 1
            await db.commit()

            # First request succeeds
            req = AIChatRequest(project_id=self.proj1.id, query="Request 1")
            await analyze_project_query(req=req, current_user=self.user1, db=db)
            self.assertEqual(self.tracker.call_count, 1)

            # Second request fails
            with self.assertRaises(HTTPException) as ctx:
                await analyze_project_query(req=req, current_user=self.user1, db=db)

            self.assertEqual(ctx.exception.status_code, 429)
            self.assertIn("daily AI usage limit", ctx.exception.detail)
            self.assertEqual(self.tracker.call_count, 1)  # Stays 1, no second provider call!

    async def test_06_monthly_limit_reached_rejected(self):
        """When monthly limit is reached, request is rejected with 429 and provider call count is 0."""
        async with self.async_session() as db:
            config = await AIConsumptionService.get_or_create_org_config(db, self.org1.id)
            config.ai_monthly_limit = 0
            await db.commit()

            req = AIChatRequest(project_id=self.proj1.id, query="Request 1")
            with self.assertRaises(HTTPException) as ctx:
                await analyze_project_query(req=req, current_user=self.user1, db=db)

            self.assertEqual(ctx.exception.status_code, 429)
            self.assertIn("monthly AI usage limit", ctx.exception.detail)
            self.assertEqual(self.tracker.call_count, 0)

    async def test_07_per_request_limit_exceeded_rejected(self):
        """When request cost exceeds per-request limit, request is rejected with 422 and provider call count is 0."""
        async with self.async_session() as db:
            config = await AIConsumptionService.get_or_create_org_config(db, self.org1.id)
            config.ai_per_request_limit = 0
            await db.commit()

            req = AIChatRequest(project_id=self.proj1.id, query="Request 1")
            with self.assertRaises(HTTPException) as ctx:
                await analyze_project_query(req=req, current_user=self.user1, db=db)

            self.assertEqual(ctx.exception.status_code, 422)
            self.assertIn("exceeds your allowed request limit", ctx.exception.detail)
            self.assertEqual(self.tracker.call_count, 0)

    async def test_08_insufficient_credits_rejected(self):
        """When credit balance is 0, request is rejected with 402 and provider call count is 0."""
        async with self.async_session() as db:
            config = await AIConsumptionService.get_or_create_org_config(db, self.org1.id)
            config.ai_credits_balance = 0.0
            await db.commit()

            req = AIChatRequest(project_id=self.proj1.id, query="Request 1")
            with self.assertRaises(HTTPException) as ctx:
                await analyze_project_query(req=req, current_user=self.user1, db=db)

            self.assertEqual(ctx.exception.status_code, 402)
            self.assertIn("enough AI credits", ctx.exception.detail)
            self.assertEqual(self.tracker.call_count, 0)

    async def test_09_provider_failure_refunds_credits(self):
        """If AI provider raises an error, reserved credits are refunded (0 net charge)."""
        set_ai_provider(FailingMockProvider())
        async with self.async_session() as db:
            req = AIChatRequest(project_id=self.proj1.id, query="Request 1")
            with self.assertRaises(HTTPException) as ctx:
                await analyze_project_query(req=req, current_user=self.user1, db=db)

            self.assertEqual(ctx.exception.status_code, 500)
            status_data = await AIConsumptionService.get_usage_status(db, self.org1.id)
            self.assertEqual(status_data["credits_balance"], 1000.0)
            self.assertEqual(status_data["daily_usage"], 0.0)

    async def test_10_unauthorized_project_access_rejected(self):
        """User 1 cannot invoke AI on User 2's Project (IDOR protection)."""
        async with self.async_session() as db:
            req = AIChatRequest(project_id=self.proj2.id, query="Attempting cross-tenant AI call")
            with self.assertRaises(HTTPException) as ctx:
                await analyze_project_query(req=req, current_user=self.user1, db=db)

            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(self.tracker.call_count, 0)

    async def test_11_inactive_user_account_status_rejected(self):
        """Inactive/suspended user is rejected before AI gate or provider execution."""
        async with self.async_session() as db:
            req = AIChatRequest(project_id=self.proj1.id, query="Inactive user attempt")
            with self.assertRaises(HTTPException) as ctx:
                await analyze_project_query(req=req, current_user=self.inactive_user, db=db)

            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(self.tracker.call_count, 0)


if __name__ == "__main__":
    unittest.main()
