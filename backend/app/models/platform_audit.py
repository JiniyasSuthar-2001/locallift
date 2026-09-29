from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from app.database import Base


class PlatformAuditLog(Base):
    """
    Authoritative audit log of all administrative actions in MasterPlace.
    Records operational, configuration, security, and financial lifecycle events.
    Never stores sensitive raw secrets or credentials.
    """
    __tablename__ = "platform_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_email = Column(String(255), nullable=True)

    action = Column(String(100), nullable=False, index=True)  # e.g. CUSTOMER_SUSPENDED, AI_KILL_SWITCH, JOB_CANCELLED
    target_type = Column(String(100), nullable=True, index=True)  # e.g. customer, job, ai_system, provider, setting
    target_id = Column(String(100), nullable=True)

    organization_id = Column(Integer, nullable=True, index=True)
    project_id = Column(Integer, nullable=True, index=True)

    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    status = Column(String(50), default="SUCCESS", nullable=False)  # SUCCESS, FAILED, WARNING
