"""
LocalLift — Development Demo Data Cleanup Tool

Safely removes development demo user (demo@locallift.io) and its associated
demo projects, audits, keywords, reviews, citations, tasks, and GBP profiles.
Leaves all real customer accounts and user-created data completely untouched.
"""

import asyncio
import sys
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.user import User, Organization, OrganizationMember, Client
from app.models.project import Project, Location, Website
from app.models.audit import SEOAudit, SEOIssue, SEOTask, WebsitePage
from app.models.gbp import GoogleAccount, GoogleBusinessProfile, GBPChange
from app.models.ranking import Keyword, KeywordRanking, GeoGridScan
from app.models.local_seo import Review, Citation, NAPRecord, Competitor, SchemaRecord
from app.models.analytics import GSCMetric, GA4Metric, Report

async def cleanup_demo_data(dry_run: bool = False):
    print("==================================================")
    print("LocalLift — Development Demo Data Cleanup")
    print("==================================================")
    print(f"Mode: {'DRY RUN (no deletions)' if dry_run else 'LIVE PURGE'}")

    async with AsyncSessionLocal() as session:
        # Find demo user
        user_res = await session.execute(
            select(User).where(User.email == "demo@locallift.io")
        )
        demo_user = user_res.scalars().first()

        if not demo_user:
            print("[INFO] No demo account (demo@locallift.io) found in the database.")
            return

        print(f"[FOUND] Demo user: ID={demo_user.id}, Email={demo_user.email}")

        # Find orgs owned by demo user
        mem_res = await session.execute(
            select(OrganizationMember).where(OrganizationMember.user_id == demo_user.id)
        )
        memberships = mem_res.scalars().all()
        org_ids = [m.organization_id for m in memberships]

        # Find demo projects
        demo_projects = []
        if org_ids:
            proj_res = await session.execute(
                select(Project).where(Project.organization_id.in_(org_ids))
            )
            demo_projects = proj_res.scalars().all()

        project_ids = [p.id for p in demo_projects]
        print(f"[FOUND] Demo projects: {len(demo_projects)} (IDs: {project_ids})")

        if project_ids:
            # Count child records
            kw_res = await session.execute(select(Keyword).where(Keyword.project_id.in_(project_ids)))
            keywords = kw_res.scalars().all()

            audit_res = await session.execute(select(SEOAudit).where(SEOAudit.project_id.in_(project_ids)))
            audits = audit_res.scalars().all()

            rev_res = await session.execute(select(Review).where(Review.project_id.in_(project_ids)))
            reviews = rev_res.scalars().all()

            cit_res = await session.execute(select(Citation).where(Citation.project_id.in_(project_ids)))
            citations = cit_res.scalars().all()

            print(f"  - Keywords to remove: {len(keywords)}")
            print(f"  - Audits to remove: {len(audits)}")
            print(f"  - Reviews to remove: {len(reviews)}")
            print(f"  - Citations to remove: {len(citations)}")

        if not dry_run:
            # Delete demo projects (cascades or manual child cleanup)
            for proj in demo_projects:
                await session.delete(proj)

            # Delete demo clients & orgs
            if org_ids:
                client_res = await session.execute(
                    select(Client).where(Client.organization_id.in_(org_ids))
                )
                for c in client_res.scalars().all():
                    await session.delete(c)

                org_res = await session.execute(
                    select(Organization).where(Organization.id.in_(org_ids))
                )
                for o in org_res.scalars().all():
                    await session.delete(o)

            # Delete demo user
            await session.delete(demo_user)
            await session.commit()
            print("\n[SUCCESS] All demo records safely removed from the database.")
        else:
            print("\n[DRY RUN] Complete. No records were deleted.")

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(cleanup_demo_data(dry_run=dry_run))
