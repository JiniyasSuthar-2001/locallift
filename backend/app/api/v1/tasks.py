from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access
from app.models.user import User
from app.models.audit import SEOIssue, SEOTask, TaskStatus, TaskPriority, IssueStatus
from app.schemas.tasks import TaskCreate, TaskUpdate, TaskOut, ConvertIssueToTaskRequest

router = APIRouter(prefix="/tasks", tags=["SEO Tasks"])

@router.get("/{project_id}", response_model=List[TaskOut])
async def list_project_tasks(
    project_id: int,
    status_filter: Optional[str] = None,
    priority: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(project_id, current_user, db)
    query = select(SEOTask).where(SEOTask.project_id == project_id)
    if status_filter:
        query = query.where(SEOTask.status == TaskStatus(status_filter))
    if priority:
        query = query.where(SEOTask.priority == TaskPriority(priority))

    result = await db.execute(query.order_by(SEOTask.id.desc()))
    return result.scalars().all()

@router.post("", response_model=TaskOut)
async def create_task(
    task_in: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_project_access(task_in.project_id, current_user, db)
    task = SEOTask(
        project_id=task_in.project_id,
        issue_id=task_in.issue_id,
        assigned_to_id=task_in.assigned_to_id,
        title=task_in.title,
        description=task_in.description,
        priority=TaskPriority(task_in.priority),
        category=task_in.category,
        status=TaskStatus(task_in.status),
        evidence=task_in.evidence,
        notes=task_in.notes,
        due_date=task_in.due_date
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task

@router.post("/convert-issue/{issue_id}", response_model=TaskOut)
async def convert_issue_to_task(
    issue_id: int,
    req: ConvertIssueToTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    iss_res = await db.execute(select(SEOIssue).where(SEOIssue.id == issue_id))
    issue = iss_res.scalars().first()
    if not issue:
        raise HTTPException(status_code=404, detail="SEO Issue not found")

    await verify_project_access(issue.project_id, current_user, db)

    # Update Issue status
    issue.status = IssueStatus.IN_TASK

    task = SEOTask(
        project_id=issue.project_id,
        issue_id=issue.id,
        assigned_to_id=req.assigned_to_id or current_user.id,
        title=f"Resolve: {issue.title}",
        description=f"**Recommended Solution**:\n{issue.recommended_solution}\n\n**Why It Matters**:\n{issue.why_it_matters}",
        priority=TaskPriority(req.priority) if req.priority else TaskPriority.MEDIUM,
        category=issue.category,
        status=TaskStatus.OPEN,
        evidence=issue.evidence,
        due_date=req.due_date
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task

@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: int,
    task_in: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(SEOTask).where(SEOTask.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await verify_project_access(task.project_id, current_user, db)

    if task_in.title is not None:
        task.title = task_in.title
    if task_in.description is not None:
        task.description = task_in.description
    if task_in.priority is not None:
        task.priority = TaskPriority(task_in.priority)
    if task_in.category is not None:
        task.category = task_in.category
    if task_in.status is not None:
        new_status = TaskStatus(task_in.status)
        task.status = new_status
        if new_status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now(timezone.utc)
            # If associated with an issue, update issue status
            if task.issue_id:
                iss_res = await db.execute(select(SEOIssue).where(SEOIssue.id == task.issue_id))
                issue = iss_res.scalars().first()
                if issue:
                    issue.status = IssueStatus.RESOLVED
                    issue.resolved_at = datetime.now(timezone.utc)
    if task_in.notes is not None:
        task.notes = task_in.notes
    if task_in.due_date is not None:
        task.due_date = task_in.due_date
    if task_in.assigned_to_id is not None:
        task.assigned_to_id = task_in.assigned_to_id

    await db.commit()
    await db.refresh(task)
    return task

@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(SEOTask).where(SEOTask.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await verify_project_access(task.project_id, current_user, db)

    await db.delete(task)
    await db.commit()
    return {"message": "Task deleted successfully"}
