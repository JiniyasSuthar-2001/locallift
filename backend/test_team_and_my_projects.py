import asyncio
import os
import sys
import time

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from app.database import AsyncSessionLocal, engine, Base
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project, Location
from app.models.team import ProjectMembership, ProjectInvitation
from app.services.team_service import TeamService
from app.core.security import get_password_hash
from app.core.deps import verify_project_access, verify_project_permission
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def run_tests():
    print("==================================================")
    print("STARTING 'MY PROJECTS' & TEAM MANAGEMENT TEST SUITE")
    print("==================================================")

    # 1. DB Schema initialization
    print("\n[TEST 1] Testing DB schema creation for Team & Project extensions...")
    from app.main import _sync_sqlite_schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_sqlite_schema)
    print("  [PASS] Tables registered & auto-migrated successfully.")


    t_id = int(time.time())

    async with AsyncSessionLocal() as db:
        # Seed Org A (Owner) and Org B (Tenant B)
        org_a = Organization(name=f"Agency Alpha {t_id}", slug=f"agency-alpha-{t_id}")
        org_b = Organization(name=f"Agency Beta {t_id}", slug=f"agency-beta-{t_id}")
        db.add_all([org_a, org_b])
        await db.commit()
        await db.refresh(org_a)
        await db.refresh(org_b)

        owner_user = User(
            email=f"owner_{t_id}@example.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Alpha Owner",
            is_active=True
        )
        tenant_b_user = User(
            email=f"tenant_b_{t_id}@example.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Beta User",
            is_active=True
        )
        db.add_all([owner_user, tenant_b_user])
        await db.commit()
        await db.refresh(owner_user)
        await db.refresh(tenant_b_user)

        db.add(OrganizationMember(organization_id=org_a.id, user_id=owner_user.id, role=OrgRole.OWNER))
        db.add(OrganizationMember(organization_id=org_b.id, user_id=tenant_b_user.id, role=OrgRole.OWNER))
        await db.commit()


        # 2. Test Project Creation & CRUD
        print("\n[TEST 2] Testing Project CRUD & Archiving...")
        proj_a = Project(
            organization_id=org_a.id,
            name=f"Alpha Dental {t_id}",
            domain=f"alphadental{t_id}.com",
            primary_category="Dentist",
            country="United States",
            health_score=82,
            status="active",
            is_archived=False
        )
        db.add(proj_a)
        await db.commit()
        await db.refresh(proj_a)

        # Verify Project Access
        verified = await verify_project_access(proj_a.id, owner_user, db)
        assert verified.id == proj_a.id
        print("  [PASS] Owner verified for Project A.")

        # Test Tenant B cannot access Project A (Tenant Isolation)
        tenant_b_blocked = False
        try:
            await verify_project_access(proj_a.id, tenant_b_user, db)
        except HTTPException as e:
            if e.status_code in (403, 404):
                tenant_b_blocked = True
                print(f"  [PASS] Tenant B successfully blocked with HTTP {e.status_code}: {e.detail}")
        assert tenant_b_blocked, "FAIL: Tenant B should have been blocked from accessing Project A"

        # 3. Test Team Member Invitations and Strict 3-Seat Limit
        print("\n[TEST 3] Testing Project Team 3-Seat Limit...")
        team_data_initial = await TeamService.get_project_team(proj_a.id, owner_user, db)
        assert team_data_initial["seats_used"] == 0
        assert team_data_initial["max_seats"] == 3
        assert team_data_initial["seats_available"] == 3
        print("  [PASS] Initial team state: 0/3 seats used.")

        # Invite Member 1 (Seat 1/3)
        inv_1 = await TeamService.invite_member(
            project_id=proj_a.id,
            email=f"member1_{t_id}@example.com",
            role="SEO Specialist",
            permissions=["project_overview", "seo_audit", "local_seo"],
            current_user=owner_user,
            db=db
        )
        assert inv_1.id is not None
        print(f"  [PASS] Invited Member 1 (id={inv_1.id}, email={inv_1.email}).")

        # Invite Member 2 (Seat 2/3) - Test Case-Insensitive Email
        inv_2 = await TeamService.invite_member(
            project_id=proj_a.id,
            email=f"MEMBER2_{t_id}@Example.COM",
            role="Local SEO Manager",
            permissions=["project_overview", "local_seo", "gbp_monitoring"],
            current_user=owner_user,
            db=db
        )
        assert inv_2.email == f"member2_{t_id}@example.com"
        print("  [PASS] Invited Member 2 with normalized email.")

        # Invite Member 3 (Seat 3/3)
        inv_3 = await TeamService.invite_member(
            project_id=proj_a.id,
            email=f"member3_{t_id}@example.com",
            role="Content Specialist",
            permissions=["project_overview", "templates", "tasks"],
            current_user=owner_user,
            db=db
        )
        assert inv_3.id is not None
        print("  [PASS] Invited Member 3. Team is now 3/3 full.")

        # Invite Member 4 -> MUST BE REJECTED with 400
        seat_limit_rejected = False
        try:
            await TeamService.invite_member(
                project_id=proj_a.id,
                email=f"member4_{t_id}@example.com",
                role="Extra Member",
                permissions=["project_overview"],
                current_user=owner_user,
                db=db
            )
        except HTTPException as e:
            if e.status_code == 400 and "PROJECT_TEAM_SEAT_LIMIT_REACHED" in str(e.detail):
                seat_limit_rejected = True
                print(f"  [PASS] 4th Member strictly rejected: {e.detail}")
        assert seat_limit_rejected, "FAIL: 4th member invitation must be rejected by backend"

        # 4. Test Email Mismatch Protection & User Acceptance
        print("\n[TEST 4] Testing Invitation Acceptance & Email Verification...")

        # Create actual user for Member 1
        member1_user = User(
            email=f"member1_{t_id}@example.com",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Member One",
            is_active=True
        )
        db.add(member1_user)
        await db.commit()
        await db.refresh(member1_user)

        # A) Hacker tries to accept Member 1's invitation -> REJECTED
        hacker_rejected = False
        try:
            await TeamService.accept_invitation(inv_1.id, tenant_b_user, db)
        except HTTPException as e:
            if e.status_code == 403 and "INVITATION_EMAIL_MISMATCH" in str(e.detail):
                hacker_rejected = True
                print(f"  [PASS] Unauthorized user rejected from accepting invite: {e.detail}")
        assert hacker_rejected, "FAIL: Unrelated user must not be able to accept another email's invitation"

        # B) Member 1 accepts their invitation -> SUCCESS
        accept_result = await TeamService.accept_invitation(inv_1.id, member1_user, db)
        assert accept_result["success"] is True
        print(f"  [PASS] Member 1 successfully accepted invitation into {accept_result['project_name']}.")

        # Verify Member 1 can now access Project A
        mem1_access = await verify_project_access(proj_a.id, member1_user, db)
        assert mem1_access.id == proj_a.id
        print("  [PASS] Member 1 now has authorized access to Project A.")

        # Verify Member 1 has 'seo_audit' permission, but NOT 'settings'
        await verify_project_permission(proj_a.id, "seo_audit", member1_user, db)
        print("  [PASS] Member 1 verified for assigned 'seo_audit' permission.")

        perm_blocked = False
        try:
            await verify_project_permission(proj_a.id, "settings", member1_user, db)
        except HTTPException as e:
            if e.status_code == 403:
                perm_blocked = True
                print(f"  [PASS] Member 1 blocked from unassigned 'settings' permission: {e.detail}")
        assert perm_blocked, "FAIL: Member 1 should be blocked from unassigned permissions"

        # 5. Test Member Removal and Account Preservation
        print("\n[TEST 5] Testing Member Removal...")
        # Find membership record
        mem_rec_res = await db.execute(
            select(ProjectMembership).where(
                ProjectMembership.project_id == proj_a.id,
                ProjectMembership.user_id == member1_user.id
            )
        )
        mem_rec = mem_rec_res.scalars().first()
        assert mem_rec is not None

        remove_success = await TeamService.remove_member(proj_a.id, mem_rec.id, owner_user, db)
        assert remove_success is True
        print("  [PASS] Successfully removed Member 1 from Project A.")

        # Verify Member 1 account STILL EXISTS
        user_check = await db.execute(select(User).where(User.id == member1_user.id))
        assert user_check.scalars().first() is not None
        print("  [PASS] Verified Member 1 user account was NOT deleted.")

        # Verify seat was freed
        updated_team = await TeamService.get_project_team(proj_a.id, owner_user, db)
        assert updated_team["seats_used"] == 2  # inv_2 and inv_3 are pending
        assert updated_team["seats_available"] == 1
        print("  [PASS] Team seat immediately became available (2/3 used).")

    print("\n==================================================")
    print("ALL 'MY PROJECTS' & TEAM TESTS PASSED! (5/5)")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
