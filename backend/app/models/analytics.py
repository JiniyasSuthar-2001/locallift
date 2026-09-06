from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class GSCMetric(Base):
    __tablename__ = "gsc_metrics"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    clicks = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    ctr = Column(Float, default=0.0)
    average_position = Column(Float, default=0.0)
    
    top_queries = Column(JSON, default=list)
    top_pages = Column(JSON, default=list)
    devices = Column(JSON, default=dict)
    countries = Column(JSON, default=dict)

class GA4Metric(Base):
    __tablename__ = "ga4_metrics"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    organic_users = Column(Integer, default=0)
    sessions = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    conversions = Column(Integer, default=0)
    
    landing_pages = Column(JSON, default=list)
    traffic_sources = Column(JSON, default=list)
    user_locations = Column(JSON, default=list)



class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    report_type = Column(String(50), default="executive")  # executive, local_audit, monthly_seo, gbp
    period = Column(String(50), default="Last 30 Days")
    summary = Column(Text, nullable=True)
    report_data = Column(JSON, default=dict)
    generated_by = Column(String(100), default="System AI")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="reports")

class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    job_type = Column(String(50), nullable=False)  # crawl, rank_check, gbp_sync, review_sync, citation_check
    frequency = Column(String(50), default="daily")  # daily, weekly, monthly
    status = Column(String(50), default="idle")  # idle, queued, running, completed, failed
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    last_result_summary = Column(String(500), nullable=True)
