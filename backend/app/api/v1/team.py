from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access, verify_project_permission, get_user_organization_ids
from app.models.user import User, OrganizationMember, OrgRole
from app.models.project import Project
from app.models.team import ProjectMembership, ProjectInvitation
from app.schemas.team import (
    ProjectTeamSummary,
    TeamInviteCreate,
    TeamMemberUpdate,
    TeamMemberOut,
    TeamInvitationOut,
    UserPendingInvitationOut,
    TeamDirectoryMember
)
from app.services.team_service import TeamService

router = APIRouter(tags=["Team & Invitations"])

# 1. Project Team Management Endpoints
@router.get("/projects/{project_id}/team", response_model=ProjectTeamSummary)
async def get_project_team(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the project team composition, member permissions, pending invitations, and available seats.
    """
    await verify_project_access(project_id, current_user, db)
    return await TeamService.get_project_team(project_id, current_user, db)

@router.post("/projects/{project_id}/team/invite", response_model=TeamInvitationOut)
async def invite_team_member(
    project_id: int,
    invite_in: TeamInviteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Invites a team member by email to a specific project.
    Strictly enforces maximum 3 team members limit per project.
    """
    await verify_project_access(project_id, current_user, db)
    invitation = await TeamService.invite_member(
        project_id=project_id,
        email=invite_in.email,
        role=invite_in.role or "Member",
        permissions=invite_in.permissions,
        current_user=current_user,
        db=db
    )
    
    # Fetch project name for response
    proj_res = await db.execute(select(Project.name).where(Project.id == project_id))
    proj_name = proj_res.scalar() or "Project"
    
    return {
        "id": invitation.id,
        "project_id": invitation.project_id,
        "project_name": proj_name,
        "email": invitation.email,
        "role": invitation.role,
        "permissions": invitation.permissions,
        "status": invitation.status,
        "invited_by_name": current_user.full_name or current_user.email.split("@")[0],
        "created_at": invitation.created_at,
        "expires_at": invitation.expires_at
    }

@router.patch("/projects/{project_id}/team/members/{member_id}", response_model=TeamMemberOut)
async def update_team_member(
    project_id: int,
    member_id: int,
    update_in: TeamMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates role and granular permissions for a project team member.
    """
    await verify_project_access(project_id, current_user, db)
    updated = await TeamService.update_member(
        project_id=project_id,
        membership_id=member_id,
        role=update_in.role,
        permissions=update_in.permissions,
        current_user=current_user,
        db=db
    )
    
    user_res = await db.execute(select(User).where(User.id == updated.user_id))
    member_user = user_res.scalars().first()
    
    return {
        "id": updated.id,
        "user_id": updated.user_id,
        "name": member_user.full_name if member_user else "Member",
        "email": member_user.email if member_user else "",
        "role": updated.role,
        "permissions": updated.permissions,
        "status": updated.status,
        "created_at": updated.created_at
    }

@router.delete("/projects/{project_id}/team/members/{member_id}")
async def remove_team_member(
    project_id: int,
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Removes a team member from a project without deleting their user account.
    """
    await verify_project_access(project_id, current_user, db)
    success = await TeamService.remove_member(
        project_id=project_id,
        membership_id=member_id,
        current_user=current_user,
        db=db
    )
    return {"success": success, "message": "Team member removed from project."}

@router.post("/projects/{project_id}/team/invitations/{invitation_id}/resend", response_model=TeamInvitationOut)
async def resend_invitation(
    project_id: int,
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Refreshes expiration and resends project invitation.
    """
    await verify_project_access(project_id, current_user, db)
    invitation = await TeamService.resend_invitation(
        project_id=project_id,
        invitation_id=invitation_id,
        current_user=current_user,
        db=db
    )
    proj_res = await db.execute(select(Project.name).where(Project.id == project_id))
    proj_name = proj_res.scalar() or "Project"
    
    return {
        "id": invitation.id,
        "project_id": invitation.project_id,
        "project_name": proj_name,
        "email": invitation.email,
        "role": invitation.role,
        "permissions": invitation.permissions,
        "status": invitation.status,
        "invited_by_name": current_user.full_name or current_user.email.split("@")[0],
        "created_at": invitation.created_at,
        "expires_at": invitation.expires_at
    }

@router.delete("/projects/{project_id}/team/invitations/{invitation_id}")
async def cancel_invitation(
    project_id: int,
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancels a pending project invitation.
    """
    await verify_project_access(project_id, current_user, db)
    success = await TeamService.cancel_invitation(
        project_id=project_id,
        invitation_id=invitation_id,
        current_user=current_user,
        db=db
    )
    return {"success": success, "message": "Invitation cancelled."}


# 2. User Pending Invitations & Accept/Decline Endpoints
@router.get("/invitations/pending", response_model=List[UserPendingInvitationOut])
async def get_my_pending_invitations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns pending invitations matching the authenticated user's email address.
    """
    return await TeamService.get_user_pending_invitations(current_user, db)

@router.post("/invitations/{invitation_id}/accept")
async def accept_project_invitation(
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Explicitly accepts a project invitation after verifying user email match and available seats.
    """
    return await TeamService.accept_invitation(invitation_id, current_user, db)

@router.post("/invitations/{invitation_id}/decline")
async def decline_project_invitation(
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Declines a project invitation.
    """
    return await TeamService.decline_invitation(invitation_id, current_user, db)


# 3. Organization Team Directory Endpoints
@router.get("/team", response_model=List[TeamDirectoryMember])
async def get_team_directory(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns directory of all team members across the organization's projects.
    """
    org_ids = await get_user_organization_ids(current_user.id, db)
    if not org_ids:
        return []
    return await TeamService.get_organization_team_directory(org_ids[0], current_user, db)

@router.get("/team/{user_id}", response_model=TeamDirectoryMember)
async def get_team_member_detail(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns details and project assignments for a specific team member.
    """
    org_ids = await get_user_organization_ids(current_user.id, db)
    if not org_ids:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    directory = await TeamService.get_organization_team_directory(org_ids[0], current_user, db)
    for m in directory:
        if m["user_id"] == user_id:
            return m
    raise HTTPException(status_code=404, detail="Team member not found in organization")
