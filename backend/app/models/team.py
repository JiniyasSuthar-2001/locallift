import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base

DEFAULT_PROJECT_PERMISSIONS = [
    "project_overview",
    "seo_audit",
    "local_seo",
    "gbp_monitoring",
    "reports",
    "tasks"
]

ALL_PROJECT_PERMISSIONS = [
    "project_overview",
    "seo_audit",
    "local_seo",
    "gbp_monitoring",
    "google_ads",
    "reports",
    "tasks",
    "templates",
    "settings",
    "team_management"
]

class ProjectMembership(Base):
    __tablename__ = "project_memberships"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    role = Column(String(100), default="Member", nullable=False)
    permissions = Column(JSON, default=lambda: list(DEFAULT_PROJECT_PERMISSIONS))
    status = Column(String(50), default="active")  # active, inactive, removed
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="team_memberships")
    user = relationship("User", back_populates="project_memberships")
    organization = relationship("Organization")

class ProjectInvitation(Base):
    __tablename__ = "project_invitations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    email = Column(String(255), nullable=False, index=True)
    invited_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    role = Column(String(100), default="Member", nullable=False)
    permissions = Column(JSON, default=lambda: list(DEFAULT_PROJECT_PERMISSIONS))
    status = Column(String(50), default="pending", index=True)  # pending, accepted, declined, expired, cancelled
    
    token = Column(String(100), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    expires_at = Column(DateTime, default=lambda: datetime.now(timezone.utc) + timedelta(days=7))
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    accepted_at = Column(DateTime, nullable=True)
    declined_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="invitations")
    organization = relationship("Organization")
    invited_by = relationship("User", foreign_keys=[invited_by_id])
