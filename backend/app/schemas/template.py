from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class TemplateVariableDef(BaseModel):
    name: str
    label: Optional[str] = None
    required: bool = False
    source: Optional[str] = None  # e.g. "project.name", "location.city", "gbp.phone"
    default_value: Optional[str] = None

class TemplateBase(BaseModel):
    name: str = Field(..., max_length=255)
    slug: Optional[str] = None
    category: str = Field(..., description="gbp, local_seo, schema, review_response, local_content, location_page, service_location, task, reporting")
    template_type: str = Field(..., description="schema_jsonld, content_markdown, review_reply, gbp_post, task_blueprint, report_summary")
    description: Optional[str] = None
    content: str
    variables: List[Dict[str, Any]] = []
    required_fields: List[str] = []
    standard_type: Optional[str] = "Local SEO Standard"

class TemplateCreate(TemplateBase):
    project_id: Optional[int] = None
    organization_id: Optional[int] = None

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    template_type: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    variables: Optional[List[Dict[str, Any]]] = None
    required_fields: Optional[List[str]] = None
    standard_type: Optional[str] = None

class TemplateOut(TemplateBase):
    id: int
    project_id: Optional[int] = None
    organization_id: Optional[int] = None
    slug: str
    is_system: bool
    version: int
    usage_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TemplateApplyRequest(BaseModel):
    project_id: int
    location_id: Optional[int] = None
    custom_variables: Optional[Dict[str, Any]] = None

class TemplateApplyResponse(BaseModel):
    template_id: int
    template_name: str
    rendered_content: str
    variables_used: Dict[str, Any]
    missing_variables: List[str]

class TemplateValidateRequest(BaseModel):
    content: str
    template_type: str
    category: Optional[str] = None
    variables: Optional[List[Dict[str, Any]]] = None

class TemplateValidateResponse(BaseModel):
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    detected_variables: List[str] = []

class TemplateImportRequest(BaseModel):
    file_content: str
    name: Optional[str] = None
    category: Optional[str] = None
    template_type: Optional[str] = None
    description: Optional[str] = None
