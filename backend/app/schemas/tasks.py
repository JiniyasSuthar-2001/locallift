from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"  # high, medium, low
    category: str = "General SEO"
    status: str = "open"  # open, in_progress, waiting, completed, ignored, recheck_required
    evidence: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[datetime] = None

class TaskCreate(TaskBase):
    project_id: int
    issue_id: Optional[int] = None
    assigned_to_id: Optional[int] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[datetime] = None
    assigned_to_id: Optional[int] = None

class TaskOut(TaskBase):
    id: int
    project_id: int
    issue_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ConvertIssueToTaskRequest(BaseModel):
    priority: Optional[str] = "medium"
    assigned_to_id: Optional[int] = None
    due_date: Optional[datetime] = None
