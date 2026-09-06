from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)  # gbp, local_seo, schema, review_response, local_content, location_page, service_location, task, reporting
    template_type = Column(String(50), nullable=False)  # schema_jsonld, content_markdown, review_reply, gbp_post, task_blueprint, report_summary
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    
    # Dynamic variables definition: [{"name": "business_name", "label": "Business Name", "required": True, "source": "project.name"}]
    variables = Column(JSON, default=list)
    required_fields = Column(JSON, default=list)
    
    is_system = Column(Boolean, default=False, index=True)
    standard_type = Column(String(100), default="Local SEO Standard")  # Schema.org / JSON-LD, Google-Compatible Local Content, Review Response Standard
    version = Column(Integer, default=1)
    usage_count = Column(Integer, default=0)
    created_by = Column(String(100), default="System")
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    usages = relationship("TemplateUsage", back_populates="template", cascade="all, delete-orphan")


class TemplateUsage(Base):
    __tablename__ = "template_usages"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("templates.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    applied_by = Column(String(100), default="User")
    rendered_content = Column(Text, nullable=False)
    applied_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    template = relationship("Template", back_populates="usages")
