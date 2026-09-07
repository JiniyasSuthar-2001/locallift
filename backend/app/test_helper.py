"""
LocalLift — Shared Test Database & Infrastructure Helper

Provides centralized, unified database setup and fixture management across all backend tests:
- Automatically initializes SQLite tables and executes schema synchronization
- Avoids ad-hoc startup_event calls or bypassed table creation
- Explicitly seeds test fixtures without weakening production security guards
- Avoids depending on accidental production defaults
"""

import sys
import uuid
from typing import AsyncGenerator, Optional, Tuple
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.database import engine, Base, AsyncSessionLocal
from app.main import _sync_sqlite_schema
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project, Location
from app.core.security import get_password_hash, create_access_token
from app.services.seeder import seed_initial_demo_data

async def init_test_db(seed_demo: bool = False, reset: bool = False) -> None:
    """
    Initializes the test database schema cleanly.
    
    1. Creates all tables registered in Base.metadata
    2. Runs SQLite schema migration/column sync
    3. If seed_demo=True, explicitly seeds the demo user & core test project
       (bypassing production environment gates safely in test context only).
    """
    async with engine.begin() as conn:
        if reset:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_sqlite_schema)

    if seed_demo:
        # Check if demo user already exists
        async with AsyncSessionLocal() as session:
            user_res = await session.execute(select(User).where(User.email == "demo@locallift.io"))
            existing_user = user_res.scalars().first()
            
            if not existing_user:
                # Safely execute seeder with force=True for test environment
                await seed_initial_demo_data(force=True)

@asynccontextmanager
async def get_test_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager providing a clean async database session for tests.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def create_test_tenant(
    org_name: str = "Test Tenant Organization",
    user_email: Optional[str] = None,
    project_name: str = "Test Project",
    primary_category: str = "Local Business"
) -> Tuple[User, Organization, Project, str]:
    """
    Helper to create an isolated test tenant (User + Org + Project) and returns
    (user, org, project, auth_token).
    """
    uid = uuid.uuid4().hex[:8]
    email = user_email or f"test_user_{uid}@locallift.test"

    async with AsyncSessionLocal() as session:
        org = Organization(
            name=f"{org_name} {uid}",
            slug=f"org-{uid}"
        )
        session.add(org)
        await session.flush()

        user = User(
            email=email,
            hashed_password=get_password_hash("TestPass123!"),
            full_name=f"Test User {uid}",
            is_active=True
        )
        session.add(user)
        await session.flush()

        member = OrganizationMember(
            user_id=user.id,
            organization_id=org.id,
            role=OrgRole.OWNER
        )
        session.add(member)
        await session.flush()

        project = Project(
            organization_id=org.id,
            name=f"{project_name} {uid}",
            domain=f"testproject-{uid}.com",
            primary_category=primary_category,
            health_score=0
        )
        session.add(project)
        await session.commit()
        await session.refresh(user)
        await session.refresh(org)
        await session.refresh(project)

        token = create_access_token(str(user.id))
        return user, org, project, token
