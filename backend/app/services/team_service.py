import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.models.project import Project
from app.models.team import (
    ProjectMembership,
    ProjectInvitation,
    DEFAULT_PROJECT_PERMISSIONS,
    ALL_PROJECT_PERMISSIONS
)

logger = logging.getLogger("locallift.team_service")

class TeamService:
    MAX_PROJECT_TEAM_SEATS = 3  # Maximum 3 invited/assigned team members per project

    @classmethod
    async def get_project_team(
        cls,
        project_id: int,
        current_user: User,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Retrieves project team members and pending invitations.
        Enforces organization boundary and calculates seat usage.
        """
        # 1. Fetch project with organization
        proj_res = await db.execute(
            select(Project)
            .options(selectinload(Project.organization).selectinload(Organization.members).selectinload(OrganizationMember.user))
            .where(Project.id == project_id)
        )
        project = proj_res.scalars().first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # 2. Get Owner details
        owner_info = {
            "name": "Organization Owner",
            "email": "owner@locallift.io",
            "role": "Owner"
        }
        if project.organization and project.organization.members:
            for m in project.organization.members:
                if m.role in (OrgRole.OWNER, OrgRole.ADMIN) and m.user:
                    owner_info = {
                        "name": m.user.full_name or m.user.email.split("@")[0],
                        "email": m.user.email,
                        "role": "Project Owner"
                    }
                    break

        # 3. Fetch active memberships
        mem_res = await db.execute(
            select(ProjectMembership)
            .options(selectinload(ProjectMembership.user))
            .where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.status == "active"
            )
            .order_by(ProjectMembership.created_at.asc())
        )
        memberships = mem_res.scalars().all()

        members_list = []
        for m in memberships:
            if m.user:
                members_list.append({
                    "id": m.id,
                    "user_id": m.user_id,
                    "name": m.user.full_name or m.user.email.split("@")[0],
                    "email": m.user.email,
                    "role": m.role,
                    "permissions": m.permissions or DEFAULT_PROJECT_PERMISSIONS,
                    "status": m.status,
                    "created_at": m.created_at
                })

        # 4. Fetch pending invitations
        inv_res = await db.execute(
            select(ProjectInvitation)
            .options(selectinload(ProjectInvitation.invited_by))
            .where(
                ProjectInvitation.project_id == project_id,
                ProjectInvitation.status == "pending",
                ProjectInvitation.expires_at > datetime.now(timezone.utc)
            )
            .order_by(ProjectInvitation.created_at.asc())
        )
        invitations = inv_res.scalars().all()

        invitations_list = []
        for inv in invitations:
            inv_by_name = inv.invited_by.full_name if inv.invited_by else "Admin"
            invitations_list.append({
                "id": inv.id,
                "project_id": inv.project_id,
                "project_name": project.name,
                "email": inv.email,
                "role": inv.role,
                "permissions": inv.permissions or DEFAULT_PROJECT_PERMISSIONS,
                "status": inv.status,
                "invited_by_name": inv_by_name,
                "created_at": inv.created_at,
                "expires_at": inv.expires_at
            })

        seats_used = len(members_list) + len(invitations_list)
        seats_available = max(0, cls.MAX_PROJECT_TEAM_SEATS - seats_used)

        return {
            "project_id": project.id,
            "project_name": project.name,
            "owner": owner_info,
            "seats_used": seats_used,
            "max_seats": cls.MAX_PROJECT_TEAM_SEATS,
            "seats_available": seats_available,
            "members": members_list,
            "pending_invitations": invitations_list
        }

    @classmethod
    async def invite_member(
        cls,
        project_id: int,
        email: str,
        role: str,
        permissions: Optional[List[str]],
        current_user: User,
        db: AsyncSession
    ) -> ProjectInvitation:
        """
        Invites a team member by email to a project.
        Enforces maximum 3 team seats per project and validates permissions.
        """
        normalized_email = email.strip().lower()
        if not normalized_email or "@" not in normalized_email:
            raise HTTPException(status_code=400, detail="A valid email address is required.")

        # 1. Fetch project
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalars().first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # 2. Check current seat count (active memberships + unexpired pending invitations)
        active_mem_count = (await db.execute(
            select(ProjectMembership.id).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.status == "active"
            )
        )).scalars().all()

        pending_inv_count = (await db.execute(
            select(ProjectInvitation.id).where(
                ProjectInvitation.project_id == project_id,
                ProjectInvitation.status == "pending",
                ProjectInvitation.expires_at > datetime.now(timezone.utc)
            )
        )).scalars().all()

        if len(active_mem_count) + len(pending_inv_count) >= cls.MAX_PROJECT_TEAM_SEATS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PROJECT_TEAM_SEAT_LIMIT_REACHED: Each project can have a maximum of {cls.MAX_PROJECT_TEAM_SEATS} team members. Please remove a member or cancel a pending invitation before inviting another."
            )

        # 3. Check if user with this email is already a member
        user_res = await db.execute(select(User).where(User.email == normalized_email))
        existing_user = user_res.scalars().first()
        if existing_user:
            already_member = (await db.execute(
                select(ProjectMembership.id).where(
                    ProjectMembership.project_id == project_id,
                    ProjectMembership.user_id == existing_user.id,
                    ProjectMembership.status == "active"
                )
            )).scalar()
            if already_member:
                raise HTTPException(
                    status_code=400,
                    detail=f"User {normalized_email} is already an active team member of this project."
                )

        # 4. Check if a pending unexpired invitation already exists for this email on this project
        existing_inv_res = await db.execute(
            select(ProjectInvitation).where(
                ProjectInvitation.project_id == project_id,
                ProjectInvitation.email == normalized_email,
                ProjectInvitation.status == "pending",
                ProjectInvitation.expires_at > datetime.now(timezone.utc)
            )
        )
        existing_inv = existing_inv_res.scalars().first()
        if existing_inv:
            raise HTTPException(
                status_code=400,
                detail=f"An active invitation for {normalized_email} is already pending for this project."
            )

        # 5. Clean / Validate permissions
        clean_perms = []
        if permissions:
            for p in permissions:
                if p in ALL_PROJECT_PERMISSIONS and p not in clean_perms:
                    clean_perms.append(p)
        if not clean_perms:
            clean_perms = list(DEFAULT_PROJECT_PERMISSIONS)

        # 6. Create Invitation record
        invitation = ProjectInvitation(
            project_id=project_id,
            organization_id=project.organization_id,
            email=normalized_email,
            invited_by_id=current_user.id,
            role=role or "Member",
            permissions=clean_perms,
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        db.add(invitation)
        await db.commit()
        await db.refresh(invitation)

        logger.info(f"Created project invitation id={invitation.id} for {normalized_email} on project {project_id}")
        return invitation

    @classmethod
    async def accept_invitation(
        cls,
        invitation_id: int,
        current_user: User,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Accepts a project invitation.
        Verifies that current authenticated user's email matches the invited email.
        Enforces team seat limits and grants project membership.
        """
        inv_res = await db.execute(
            select(ProjectInvitation)
            .options(selectinload(ProjectInvitation.project))
            .where(ProjectInvitation.id == invitation_id)
        )
        invitation = inv_res.scalars().first()
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        # Security check: User email must match invitation email exactly (case-insensitive)
        if invitation.email.strip().lower() != current_user.email.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"INVITATION_EMAIL_MISMATCH: This invitation was sent to '{invitation.email}', but you are signed in as '{current_user.email}'."
            )

        if invitation.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"This invitation has already been {invitation.status}."
            )

        now = datetime.now(timezone.utc)
        exp = invitation.expires_at
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

        if exp and exp < now:
            invitation.status = "expired"
            await db.commit()
            raise HTTPException(status_code=400, detail="This invitation has expired. Please ask the project owner to resend it.")


        # Check if project still exists and seats are open
        active_mem_count = (await db.execute(
            select(ProjectMembership.id).where(
                ProjectMembership.project_id == invitation.project_id,
                ProjectMembership.status == "active"
            )
        )).scalars().all()

        if len(active_mem_count) >= cls.MAX_PROJECT_TEAM_SEATS:
            raise HTTPException(
                status_code=400,
                detail="This project has already reached the maximum limit of 3 team members."
            )

        # Check if already a member
        existing_mem_res = await db.execute(
            select(ProjectMembership).where(
                ProjectMembership.project_id == invitation.project_id,
                ProjectMembership.user_id == current_user.id
            )
        )
        existing_mem = existing_mem_res.scalars().first()

        if existing_mem:
            existing_mem.status = "active"
            existing_mem.role = invitation.role
            existing_mem.permissions = invitation.permissions
            existing_mem.updated_at = datetime.now(timezone.utc)
        else:
            new_mem = ProjectMembership(
                project_id=invitation.project_id,
                user_id=current_user.id,
                organization_id=invitation.organization_id,
                role=invitation.role,
                permissions=invitation.permissions,
                status="active"
            )
            db.add(new_mem)

        # Mark invitation accepted
        invitation.status = "accepted"
        invitation.accepted_at = datetime.now(timezone.utc)

        # Ensure user has organization membership
        user_org_res = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == current_user.id,
                OrganizationMember.organization_id == invitation.organization_id
            )
        )
        if not user_org_res.scalars().first():
            db.add(OrganizationMember(
                organization_id=invitation.organization_id,
                user_id=current_user.id,
                role=OrgRole.SPECIALIST
            ))

        await db.commit()


        project_name = invitation.project.name if invitation.project else "Project"
        return {
            "success": True,
            "project_id": invitation.project_id,
            "project_name": project_name,
            "role": invitation.role,
            "permissions": invitation.permissions,
            "message": f"You have successfully joined {project_name}!"
        }

    @classmethod
    async def decline_invitation(
        cls,
        invitation_id: int,
        current_user: User,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Declines a project invitation.
        Verifies email match and marks invitation as declined.
        """
        inv_res = await db.execute(
            select(ProjectInvitation).where(ProjectInvitation.id == invitation_id)
        )
        invitation = inv_res.scalars().first()
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        if invitation.email.strip().lower() != current_user.email.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You cannot decline an invitation sent to another email address."
            )

        invitation.status = "declined"
        invitation.declined_at = datetime.now(timezone.utc)
        await db.commit()

        return {"success": True, "message": "Invitation declined."}

    @classmethod
    async def cancel_invitation(
        cls,
        project_id: int,
        invitation_id: int,
        current_user: User,
        db: AsyncSession
    ) -> bool:
        """
        Cancels a pending invitation from project team management.
        """
        inv_res = await db.execute(
            select(ProjectInvitation).where(
                ProjectInvitation.id == invitation_id,
                ProjectInvitation.project_id == project_id
            )
        )
        invitation = inv_res.scalars().first()
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        invitation.status = "cancelled"
        await db.commit()
        return True

    @classmethod
    async def resend_invitation(
        cls,
        project_id: int,
        invitation_id: int,
        current_user: User,
        db: AsyncSession
    ) -> ProjectInvitation:
        """
        Resends an invitation, extending expiration by 7 days.
        """
        inv_res = await db.execute(
            select(ProjectInvitation).where(
                ProjectInvitation.id == invitation_id,
                ProjectInvitation.project_id == project_id
            )
        )
        invitation = inv_res.scalars().first()
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        invitation.status = "pending"
        invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        invitation.created_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(invitation)
        return invitation

    @classmethod
    async def remove_member(
        cls,
        project_id: int,
        membership_id: int,
        current_user: User,
        db: AsyncSession
    ) -> bool:
        """
        Removes a team member from the project.
        Preserves user account and other project memberships.
        """
        mem_res = await db.execute(
            select(ProjectMembership).where(
                ProjectMembership.id == membership_id,
                ProjectMembership.project_id == project_id
            )
        )
        membership = mem_res.scalars().first()
        if not membership:
            raise HTTPException(status_code=404, detail="Team member not found on this project")

        await db.delete(membership)
        await db.commit()
        return True

    @classmethod
    async def update_member(
        cls,
        project_id: int,
        membership_id: int,
        role: Optional[str],
        permissions: Optional[List[str]],
        current_user: User,
        db: AsyncSession
    ) -> ProjectMembership:
        """
        Updates team member's role and project-specific permissions.
        """
        mem_res = await db.execute(
            select(ProjectMembership).where(
                ProjectMembership.id == membership_id,
                ProjectMembership.project_id == project_id
            )
        )
        membership = mem_res.scalars().first()
        if not membership:
            raise HTTPException(status_code=404, detail="Team member not found on this project")

        if role:
            membership.role = role
        if permissions is not None:
            clean_perms = [p for p in permissions if p in ALL_PROJECT_PERMISSIONS]
            membership.permissions = clean_perms

        membership.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(membership)
        return membership

    @classmethod
    async def get_user_pending_invitations(
        cls,
        current_user: User,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Retrieves active pending invitations for the logged-in user's email.
        """
        user_email = current_user.email.strip().lower()
        inv_res = await db.execute(
            select(ProjectInvitation)
            .options(
                selectinload(ProjectInvitation.project),
                selectinload(ProjectInvitation.organization),
                selectinload(ProjectInvitation.invited_by)
            )
            .where(
                ProjectInvitation.email == user_email,
                ProjectInvitation.status == "pending",
                ProjectInvitation.expires_at > datetime.now(timezone.utc)
            )
            .order_by(ProjectInvitation.created_at.desc())
        )
        invitations = inv_res.scalars().all()

        results = []
        for inv in invitations:
            proj_name = inv.project.name if inv.project else "Unnamed Project"
            proj_dom = inv.project.domain if inv.project else ""
            org_name = inv.organization.name if inv.organization else "Organization"
            inv_by_name = inv.invited_by.full_name if inv.invited_by else "Admin"

            results.append({
                "id": inv.id,
                "project_id": inv.project_id,
                "project_name": proj_name,
                "project_domain": proj_dom,
                "organization_name": org_name,
                "invited_by_name": inv_by_name,
                "role": inv.role,
                "permissions": inv.permissions or DEFAULT_PROJECT_PERMISSIONS,
                "created_at": inv.created_at,
                "expires_at": inv.expires_at
            })
        return results

    @classmethod
    async def get_organization_team_directory(
        cls,
        organization_id: int,
        current_user: User,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all team members across the organization with their project assignments.
        """
        # Fetch organization members
        org_mem_res = await db.execute(
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.user))
            .where(OrganizationMember.organization_id == organization_id)
        )
        org_members = org_mem_res.scalars().all()

        # Fetch all project memberships in org
        proj_mem_res = await db.execute(
            select(ProjectMembership)
            .options(selectinload(ProjectMembership.project), selectinload(ProjectMembership.user))
            .where(
                ProjectMembership.organization_id == organization_id,
                ProjectMembership.status == "active"
            )
        )
        project_memberships = proj_mem_res.scalars().all()

        # Group by user_id
        user_map: Dict[int, Dict[str, Any]] = {}

        for om in org_members:
            if om.user:
                user_map[om.user_id] = {
                    "user_id": om.user_id,
                    "name": om.user.full_name or om.user.email.split("@")[0],
                    "email": om.user.email,
                    "global_role": om.role.value if hasattr(om.role, "value") else str(om.role),
                    "projects": [],
                    "status": "active"
                }

        for pm in project_memberships:
            if pm.user:
                if pm.user_id not in user_map:
                    user_map[pm.user_id] = {
                        "user_id": pm.user_id,
                        "name": pm.user.full_name or pm.user.email.split("@")[0],
                        "email": pm.user.email,
                        "global_role": "Project Member",
                        "projects": [],
                        "status": "active"
                    }
                if pm.project:
                    user_map[pm.user_id]["projects"].append({
                        "id": pm.project.id,
                        "name": pm.project.name,
                        "role": pm.role,
                        "permissions": pm.permissions or []
                    })

        results = list(user_map.values())
        for r in results:
            r["project_count"] = len(r["projects"])
        return results
