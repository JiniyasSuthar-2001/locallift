from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.config import settings
from app.models.user import User, OrganizationMember, OrgRole
from app.schemas.auth import TokenPayload


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        token_data = TokenPayload(sub=user_id_str)
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == int(token_data.sub)))
    user = result.scalars().first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user

async def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user

async def get_user_organization_ids(
    user_id: int,
    db: AsyncSession
) -> list[int]:
    """Retrieve all organization IDs the user belongs to."""
    result = await db.execute(
        select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user_id)
    )
    return list(result.scalars().all())

async def verify_organization_membership(
    organization_id: int,
    current_user: User,
    db: AsyncSession,
    required_roles: Optional[list[OrgRole]] = None
) -> OrganizationMember:
    """Verifies that the current user belongs to the requested organization with sufficient role."""
    if current_user.is_superuser:
        mem_res = await db.execute(
            select(OrganizationMember).where(OrganizationMember.organization_id == organization_id)
        )
        mem = mem_res.scalars().first()
        if mem:
            return mem
        return OrganizationMember(organization_id=organization_id, user_id=current_user.id, role=OrgRole.OWNER)

    stmt = select(OrganizationMember).where(
        OrganizationMember.organization_id == organization_id,
        OrganizationMember.user_id == current_user.id
    )
    result = await db.execute(stmt)
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not belong to this organization."
        )

    if required_roles and membership.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Requires role in {[r.value for r in required_roles]}."
        )
    return membership

async def verify_client_access(
    client_id: int,
    organization_id: int,
    db: AsyncSession
):
    """Verifies that a client belongs to the specified organization."""
    from app.models.user import Client
    res = await db.execute(select(Client).where(Client.id == client_id, Client.organization_id == organization_id))
    client = res.scalars().first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client_id: Client does not exist or does not belong to this organization."
        )
    return client


async def verify_project_access(
    project_id: int,
    current_user: User,
    db: AsyncSession
):
    """
    Enforce tenant and team boundary:
    1. Superuser has access to everything.
    2. Organization owners/admins/managers have access to all projects in their org.
    3. Assigned project team members have access to projects they are members of.
    """
    from app.models.project import Project
    from app.models.team import ProjectMembership

    if current_user.is_superuser:
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalars().first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    # 1. Check organization membership
    org_ids = await get_user_organization_ids(current_user.id, db)
    if org_ids:
        proj_res = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id.in_(org_ids)
            )
        )
        project = proj_res.scalars().first()
        if project:
            return project

    # 2. Check project-specific team membership
    mem_res = await db.execute(
        select(ProjectMembership)
        .where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == current_user.id,
            ProjectMembership.status == "active"
        )
    )
    membership = mem_res.scalars().first()
    if membership:
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalars().first()
        if project:
            return project

    # 3. If neither, check if project exists at all for security error reporting
    exist_res = await db.execute(select(Project.id).where(Project.id == project_id))
    if exist_res.scalar() is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to access this project"
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

async def verify_project_permission(
    project_id: int,
    permission_name: str,
    current_user: User,
    db: AsyncSession
):
    """
    Verifies that the current user has a specific granular permission on the project.
    Org Owners / Admins have all permissions by default.
    Project team members must have the permission in their ProjectMembership.
    """
    from app.models.project import Project
    from app.models.team import ProjectMembership, ALL_PROJECT_PERMISSIONS

    project = await verify_project_access(project_id, current_user, db)

    if current_user.is_superuser:
        return project

    # Check if user is Org Owner/Admin
    org_ids = await get_user_organization_ids(current_user.id, db)
    if project.organization_id in org_ids:
        org_mem_res = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == project.organization_id,
                OrganizationMember.user_id == current_user.id
            )
        )
        org_mem = org_mem_res.scalars().first()
        if org_mem and org_mem.role in (OrgRole.OWNER, OrgRole.ADMIN, OrgRole.MANAGER):
            return project

    # Check project-specific permissions for team member
    mem_res = await db.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == current_user.id,
            ProjectMembership.status == "active"
        )
    )
    membership = mem_res.scalars().first()
    if membership:
        perms = membership.permissions or []
        if permission_name in perms:
            return project

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Access denied: You do not have the required '{permission_name}' permission for this project."
    )


