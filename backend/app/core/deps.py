from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.config import settings
from app.models.user import User, OrganizationMember
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

async def verify_project_access(
    project_id: int,
    current_user: User,
    db: AsyncSession
):
    """
    Enforce tenant boundary: Verify that the current user's organization has access
    to the given project_id. Returns the Project if authorized, raises 403 or 404 otherwise.
    """
    from app.models.project import Project

    if current_user.is_superuser:
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalars().first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    org_ids = await get_user_organization_ids(current_user.id, db)
    if not org_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: User does not belong to any organization"
        )

    proj_res = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id.in_(org_ids)
        )
    )
    project = proj_res.scalars().first()
    if not project:
        # Check if project exists for another org
        exist_res = await db.execute(select(Project.id).where(Project.id == project_id))
        if exist_res.scalar() is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to access this project"
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project

