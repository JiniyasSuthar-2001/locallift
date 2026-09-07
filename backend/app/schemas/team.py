from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr

class TeamMemberBase(BaseModel):
    role: str = "Member"
    permissions: List[str] = []

class TeamInviteCreate(BaseModel):
    email: EmailStr
    role: Optional[str] = "Member"
    permissions: Optional[List[str]] = None

class TeamMemberUpdate(BaseModel):
    role: Optional[str] = None
    permissions: Optional[List[str]] = None

class TeamMemberOut(BaseModel):
    id: int
    user_id: int
    name: str
    email: str
    role: str
    permissions: List[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class TeamInvitationOut(BaseModel):
    id: int
    project_id: int
    project_name: str
    email: str
    role: str
    permissions: List[str]
    status: str
    invited_by_name: Optional[str] = None
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True

class ProjectTeamSummary(BaseModel):
    project_id: int
    project_name: str
    owner: Dict[str, Any]
    seats_used: int
    max_seats: int = 3
    seats_available: int
    members: List[TeamMemberOut]
    pending_invitations: List[TeamInvitationOut]

class UserPendingInvitationOut(BaseModel):
    id: int
    project_id: int
    project_name: str
    project_domain: str
    organization_name: str
    invited_by_name: str
    role: str
    permissions: List[str]
    created_at: datetime
    expires_at: datetime

class TeamDirectoryMember(BaseModel):
    user_id: int
    name: str
    email: str
    global_role: str
    project_count: int
    projects: List[Dict[str, Any]]
    status: str
