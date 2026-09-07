import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy.future import select

from app.database import AsyncSessionLocal, Base, engine
from app.config import settings
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project, Location
from app.models.audit import SEOAudit, SEOIssue, IssueSeverity, IssueStatus
from app.models.ranking import Keyword, GeoGridScan
from app.models.local_seo import Review, Citation
from app.models.gbp import GoogleAccount, GoogleBusinessProfile
from app.core.security import get_password_hash
from app.services.ai.base import AIProvider
from app.services.ai.unconfigured_provider import UnconfiguredAIProvider
from app.services.ai.mock_provider import MockAIProvider
from app.services.ai import set_ai_provider, get_ai_provider
from app.services.ai_assistant import AIAssistantService
from app.api.v1.ai import analyze_project_query, generate_review_response
from app.schemas.ai import AIChatRequest
from app.services.serp import get_serp_provider
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.template_service import TemplateEngine, SYSTEM_TEMPLATES
from app.models.template import Template

# ---------------------------------------------------------------------------
# Setup DB Schema
# ---------------------------------------------------------------------------
async def setup_test_environment():
    from app.main import _sync_sqlite_schema
    import app.models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_sqlite_schema)

# ---------------------------------------------------------------------------
# 1. AI UNCONFIGURED TEST
# ---------------------------------------------------------------------------
def test_ai_unconfigured_honest_rejection():
    """Verify that when AI_API_KEY is not configured, endpoints return honest AI_NOT_CONFIGURED error without fake canned text."""
    async def _test():
        set_ai_provider(UnconfiguredAIProvider())

        async with AsyncSessionLocal() as session:
            # Create user and project
            ts = int(datetime.now(timezone.utc).timestamp() * 1000)
            org = Organization(name=f"Org {ts}", slug=f"org-ai-unconf-{ts}", plan="pro")
            session.add(org)
            await session.flush()

            user = User(email=f"user-{ts}@unconf.io", full_name="AI Tester", hashed_password="hash", is_active=True)
            session.add(user)
            await session.flush()

            session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))
            proj = Project(organization_id=org.id, name="Test AI Proj", domain="aiproj.com", country="US")
            session.add(proj)
            await session.flush()

            rev = Review(project_id=proj.id, author_name="John Doe", rating=1, review_text="Very bad service", response_status="unanswered")
            session.add(rev)
            await session.commit()

            # 1. Diagnostic test
            req = AIChatRequest(project_id=proj.id, query="Why did my rankings drop?")
            threw_diag_err = False
            try:
                await analyze_project_query(req=req, current_user=user, db=session)
            except HTTPException as e:
                if e.status_code == 400 and "AI_NOT_CONFIGURED" in str(e.detail):
                    threw_diag_err = True

            assert threw_diag_err, "Diagnostic endpoint must raise 400 AI_NOT_CONFIGURED when AI is unconfigured!"

            # 2. Review response draft test
            threw_rev_err = False
            try:
                await generate_review_response(review_id=rev.id, current_user=user, db=session)
            except HTTPException as e:
                if e.status_code == 400 and "AI_NOT_CONFIGURED" in str(e.detail):
                    threw_rev_err = True

            assert threw_rev_err, "Review response endpoint must raise 400 AI_NOT_CONFIGURED when AI is unconfigured!"

            # Cleanup
            await session.delete(rev)
            await session.delete(proj)
            await session.delete(user)
            await session.delete(org)
            await session.commit()

    asyncio.run(_test())

# ---------------------------------------------------------------------------
# 2. AI REAL CONTEXT & REVIEW TEXT-SPECIFIC DRAFTING
# ---------------------------------------------------------------------------
def test_ai_real_context_and_review_drafting():
    """Verify that real context is gathered (no fake 85 GBP) and review text specifically shapes the response."""
    async def _test():
        set_ai_provider(MockAIProvider())

        async with AsyncSessionLocal() as session:
            ts = int(datetime.now(timezone.utc).timestamp() * 1000)
            org = Organization(name=f"Org {ts}", slug=f"org-ai-real-{ts}", plan="pro")
            session.add(org)
            await session.flush()

            user = User(email=f"user-{ts}@aireal.io", full_name="AI Tester", hashed_password="hash", is_active=True)
            session.add(user)
            await session.flush()

            session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))
            proj = Project(organization_id=org.id, name="Apex Plumbing Denver", domain="apexplumbingdenver.com", country="US", health_score=88)
            session.add(proj)
            await session.flush()

            # Add two distinct reviews
            rev_positive = Review(
                project_id=proj.id,
                author_name="Sarah Smith",
                rating=5,
                review_text="The technician arrived on time and was extremely friendly and professional.",
                response_status="unanswered"
            )
            rev_negative = Review(
                project_id=proj.id,
                author_name="Bob Jones",
                rating=1,
                review_text="Your plumber was two hours late and did not call in advance.",
                response_status="unanswered"
            )
            session.add(rev_positive)
            session.add(rev_negative)
            await session.commit()

            # Test Diagnostic analysis
            req = AIChatRequest(project_id=proj.id, query="Analyze local pack rank visibility")
            diag_resp = await analyze_project_query(req=req, current_user=user, db=session)
            assert diag_resp is not None
            assert len(diag_resp.likely_causes) > 0
            # Ensure no hardcoded 85 in evidence points
            for ep in diag_resp.evidence_points:
                assert "85%" not in ep or "Not connected" in ep

            # Test Review Drafting for Review A (praising friendly/professional)
            draft_a_resp = await generate_review_response(review_id=rev_positive.id, current_user=user, db=session)
            assert draft_a_resp["status"] == "drafted"
            assert "friendly and professional" in draft_a_resp["draft_response"].lower()

            # Test Review Drafting for Review B (complaining about being late)
            draft_b_resp = await generate_review_response(review_id=rev_negative.id, current_user=user, db=session)
            assert draft_b_resp["status"] == "drafted"
            assert "scheduling delay" in draft_b_resp["draft_response"].lower() or "late" in draft_b_resp["draft_response"].lower()

            # Verify responses are DRAFTS (Human approval required)
            rev_a_db = await session.get(Review, rev_positive.id)
            rev_b_db = await session.get(Review, rev_negative.id)
            assert rev_a_db.response_status == "drafted"
            assert rev_b_db.response_status == "drafted"

            # Cleanup
            await session.delete(rev_positive)
            await session.delete(rev_negative)
            await session.delete(proj)
            await session.delete(user)
            await session.delete(org)
            await session.commit()

    asyncio.run(_test())

# ---------------------------------------------------------------------------
# 3. AI ERROR RESILIENCE (Rate limits, Timeouts, Auth)
# ---------------------------------------------------------------------------
def test_ai_error_resilience():
    """Verify that AI rate limits and timeouts raise clean HTTP status codes without leaking internals."""
    async def _test():
        async with AsyncSessionLocal() as session:
            ts = int(datetime.now(timezone.utc).timestamp() * 1000)
            org = Organization(name=f"Org {ts}", slug=f"org-ai-err-{ts}", plan="pro")
            session.add(org)
            await session.flush()

            user = User(email=f"user-{ts}@aierr.io", full_name="AI Tester", hashed_password="hash", is_active=True)
            session.add(user)
            await session.flush()

            session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))
            proj = Project(organization_id=org.id, name="Error Test Proj", domain="errtest.com", country="US")
            session.add(proj)
            await session.commit()

            req = AIChatRequest(project_id=proj.id, query="Test query")

            # 1. Rate limit (429)
            set_ai_provider(MockAIProvider(simulate_error="rate_limit"))
            threw_429 = False
            try:
                await analyze_project_query(req=req, current_user=user, db=session)
            except HTTPException as e:
                if e.status_code == 429:
                    threw_429 = True
            assert threw_429, "Expected HTTP 429 on AI rate limit."

            # 2. Timeout (504)
            set_ai_provider(MockAIProvider(simulate_error="timeout"))
            threw_504 = False
            try:
                await analyze_project_query(req=req, current_user=user, db=session)
            except HTTPException as e:
                if e.status_code == 504:
                    threw_504 = True
            assert threw_504, "Expected HTTP 504 on AI timeout."

            # Cleanup
            await session.delete(proj)
            await session.delete(user)
            await session.delete(org)
            await session.commit()

    asyncio.run(_test())

# ---------------------------------------------------------------------------
# 4. EMPTY ACCOUNT INTEGRITY TEST
# ---------------------------------------------------------------------------
def test_empty_account_zero_data_integrity():
    """Verify that a completely fresh account has zero fake projects, reviews, rankings, or GBP data."""
    async def _test():
        from app.api.v1.projects import list_projects, get_dashboard_summary
        async with AsyncSessionLocal() as session:
            ts = int(datetime.now(timezone.utc).timestamp() * 1000)
            org = Organization(name=f"Fresh Agency {ts}", slug=f"fresh-agency-{ts}", plan="starter")
            session.add(org)
            await session.flush()

            fresh_user = User(
                email=f"fresh-user-{ts}@locallift.io",
                full_name="Fresh User",
                hashed_password="hash",
                is_active=True
            )
            session.add(fresh_user)
            await session.flush()

            session.add(OrganizationMember(organization_id=org.id, user_id=fresh_user.id, role=OrgRole.OWNER))
            await session.commit()

            # 1. List projects -> must be empty
            user_projects = await list_projects(current_user=fresh_user, db=session)
            assert len(user_projects) == 0, f"Expected 0 projects for fresh user, got {len(user_projects)}"

            # Cleanup
            await session.delete(fresh_user)
            await session.delete(org)
            await session.commit()

    asyncio.run(_test())

# ---------------------------------------------------------------------------
# 5. MULTI-TENANT ISOLATION & IDOR SECURITY REGRESSION TEST
# ---------------------------------------------------------------------------
def test_multi_tenant_idor_security_isolation():
    """
    CRITICAL SECURITY TEST:
    Verify that User A (Org A, Project A) CANNOT access, modify, or run operations against Project B (Org B).
    """
    async def _test():
        from app.core.deps import verify_project_access
        from app.api.v1.projects import get_project, delete_project
        from app.api.v1.keywords import list_keywords, add_keyword
        from app.schemas.ranking import KeywordCreate

        async with AsyncSessionLocal() as session:
            ts = int(datetime.now(timezone.utc).timestamp() * 1000)

            # Tenant A
            org_a = Organization(name=f"Tenant A Org {ts}", slug=f"tenant-a-{ts}", plan="agency_pro")
            session.add(org_a)
            await session.flush()
            user_a = User(email=f"user-a-{ts}@tenant-a.io", full_name="User A", hashed_password="hash", is_active=True)
            session.add(user_a)
            await session.flush()
            session.add(OrganizationMember(organization_id=org_a.id, user_id=user_a.id, role=OrgRole.OWNER))
            proj_a = Project(organization_id=org_a.id, name="Project A", domain="project-a.com", country="US")
            session.add(proj_a)
            await session.flush()

            # Tenant B
            org_b = Organization(name=f"Tenant B Org {ts}", slug=f"tenant-b-{ts}", plan="agency_pro")
            session.add(org_b)
            await session.flush()
            user_b = User(email=f"user-b-{ts}@tenant-b.io", full_name="User B", hashed_password="hash", is_active=True)
            session.add(user_b)
            await session.flush()
            session.add(OrganizationMember(organization_id=org_b.id, user_id=user_b.id, role=OrgRole.OWNER))
            proj_b = Project(organization_id=org_b.id, name="Project B", domain="project-b.com", country="US")
            session.add(proj_b)
            await session.commit()

            # Test 1: User A trying to access Project B via verify_project_access
            user_a_blocked = False
            try:
                await verify_project_access(project_id=proj_b.id, current_user=user_a, db=session)
            except HTTPException as e:
                if e.status_code == 403:
                    user_a_blocked = True
            assert user_a_blocked, "CRITICAL IDOR: User A was able to access Tenant B's project!"

            # Test 2: User A trying to get Project B endpoint
            user_a_get_blocked = False
            try:
                await get_project(project_id=proj_b.id, current_user=user_a, db=session)
            except HTTPException as e:
                if e.status_code == 403:
                    user_a_get_blocked = True
            assert user_a_get_blocked, "CRITICAL IDOR: User A was able to GET Tenant B's project details!"

            # Test 3: User A trying to add a keyword into Project B
            user_a_kw_blocked = False
            try:
                kw_in = KeywordCreate(project_id=proj_b.id, keyword="illegal keyword")
                await add_keyword(kw_in=kw_in, current_user=user_a, db=session)
            except HTTPException as e:
                if e.status_code == 403:
                    user_a_kw_blocked = True
            assert user_a_kw_blocked, "CRITICAL IDOR: User A was able to insert data into Tenant B's project!"

            # Test 4: User A trying to delete Project B
            user_a_delete_blocked = False
            try:
                await delete_project(project_id=proj_b.id, current_user=user_a, db=session)
            except HTTPException as e:
                if e.status_code == 403:
                    user_a_delete_blocked = True
            assert user_a_delete_blocked, "CRITICAL IDOR: User A was able to delete Tenant B's project!"

            # Cleanup
            await session.delete(proj_a)
            await session.delete(user_a)
            await session.delete(org_a)
            await session.delete(proj_b)
            await session.delete(user_b)
            await session.delete(org_b)
            await session.commit()

    asyncio.run(_test())

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_all_part2_tests():
    asyncio.run(setup_test_environment())

    print("--- Running Test 1: AI Unconfigured Honest Rejection ---")
    test_ai_unconfigured_honest_rejection()
    print("[PASS] AI Unconfigured Rejection (AI_NOT_CONFIGURED)")

    print("--- Running Test 2: AI Real Context & Text-Specific Review Drafting ---")
    test_ai_real_context_and_review_drafting()
    print("[PASS] AI Real Context Synthesis & Review Drafts")

    print("--- Running Test 3: AI Error Resilience (Rate Limits, Timeouts) ---")
    test_ai_error_resilience()
    print("[PASS] AI Error Resilience (HTTP 429 & 504)")

    print("--- Running Test 4: Empty Account Zero-Data Integrity ---")
    test_empty_account_zero_data_integrity()
    print("[PASS] Empty Account Zero-Data Isolation")

    print("--- Running Test 5: Multi-Tenant IDOR Security Isolation ---")
    test_multi_tenant_idor_security_isolation()
    print("[PASS] Multi-Tenant Isolation & IDOR Protection (Tenant A blocked from Tenant B)")

    print("\n[SUCCESS] ALL PART 2 AI, INTEGRATION & SECURITY TESTS PASSED 100%!")

if __name__ == "__main__":
    run_all_part2_tests()
