from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class SystemSetting(Base):
    """
    Global system key-value configurations (e.g., global_ai_enabled).
    """
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class OrganizationAIConfig(Base):
    """
    Per-Organization AI Controls, Limits, and Credit Wallet.
    """
    __tablename__ = "organization_ai_configs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    ai_enabled = Column(Boolean, default=True, nullable=False)
    ai_daily_limit = Column(Integer, default=100, nullable=False)
    ai_monthly_limit = Column(Integer, default=3000, nullable=False)
    ai_per_request_limit = Column(Integer, default=5, nullable=False)
    ai_credits_balance = Column(Float, default=1000.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="ai_config")

class AIUsageLog(Base):
    """
    Authoritative audit record of AI access attempts, provider usage, token counts, and credit deductions.
    """
    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    task_type = Column(String(100), nullable=False)  # e.g., 'diagnostic', 'review_response', 'content_opportunities'
    provider = Column(String(50), nullable=False)   # e.g., 'gemini', 'mock', 'unconfigured'
    model = Column(String(100), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    actual_cost = Column(Float, nullable=True)
    credits_charged = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), nullable=False)     # 'success', 'failed', 'rejected'
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
