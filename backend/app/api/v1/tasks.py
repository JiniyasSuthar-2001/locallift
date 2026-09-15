from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.core.deps import get_current_user, verify_project_access, get_user_organization_ids
from app.core.audit_logger import log_user_action
from app.models.user import User, OrganizationMember
from app.models.audit import SEOIssue, SEOTask, TaskStatus, TaskPriority, IssueStatus
from app.models.team import ProjectMembership
from app.schemas.tasks import TaskCreate, TaskUpdate, TaskOut, ConvertIssueToTaskRequest

router = APIRouter(prefix="/tasks", tags=["SEO Tasks"])

async def _verify_assigned_user(assigned_to_id: int, project_id: int, db: AsyncSession):
    """Verify that an assigned user exists and has valid organization or project access."""
    # Check if assigned user has project membership
    mem_res = await db.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == assigned_to_id,
            ProjectMembership.status == "active"
        )
    )
    if mem_res.scalars().first():
        return

    # Check if assigned user is an org member
    from app.models.project import Project
    proj_res = await db.execute(select(Project.organization_id).where(Project.id == project_id))
    org_id = proj_res.scalar()
    if org_id:
        org_mem_res = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == assigned_to_id
            )
        )
        if org_mem_res.scalars().first():
            return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid assigned_to_id: User is not a collaborator on this project or organization."
    )


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
    if status_filter and status_filter.lower() != "all":
        try:
            query = query.where(SEOTask.status == TaskStatus(status_filter.lower()))
        except ValueError:
            pass
    if priority and priority.lower() != "all":
        try:
            query = query.where(SEOTask.priority == TaskPriority(priority.lower()))
        except ValueError:
            pass

    result = await db.execute(query.order_by(SEOTask.id.desc()))
    return result.scalars().all()


@router.post("", response_model=TaskOut)
async def create_task(
    request: Request,
    task_in: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project = await verify_project_access(task_in.project_id, current_user, db)

    # Validate issue_id belongs to the same project
    if task_in.issue_id:
        iss_res = await db.execute(
            select(SEOIssue).where(
                SEOIssue.id == task_in.issue_id,
                SEOIssue.project_id == task_in.project_id
            )
        )
        if not iss_res.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid issue_id: Issue does not exist or does not belong to this project."
            )

    # Validate assigned user
    if task_in.assigned_to_id:
        await _verify_assigned_user(task_in.assigned_to_id, task_in.project_id, db)

    task = SEOTask(
        project_id=task_in.project_id,
        issue_id=task_in.issue_id,
        assigned_to_id=task_in.assigned_to_id or current_user.id,
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

    log_user_action(
        request, "CREATE_TASK",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=task.project_id,
        task_id=task.id,
        title=task.title
    )
    return task


@router.post("/convert-issue/{issue_id}", response_model=TaskOut)
async def convert_issue_to_task(
    request: Request,
    issue_id: int,
    req: Optional[ConvertIssueToTaskRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    req = req or ConvertIssueToTaskRequest()
    iss_res = await db.execute(select(SEOIssue).where(SEOIssue.id == issue_id))
    issue = iss_res.scalars().first()
    if not issue:
        raise HTTPException(status_code=404, detail="SEO Issue not found")

    project = await verify_project_access(issue.project_id, current_user, db)

    # Validate assignee if provided
    assigned_user_id = req.assigned_to_id or current_user.id
    if req.assigned_to_id:
        await _verify_assigned_user(req.assigned_to_id, issue.project_id, db)

    # Check if a task already exists for this issue (idempotent conversion)
    existing_task_res = await db.execute(
        select(SEOTask).where(
            SEOTask.project_id == issue.project_id,
            SEOTask.issue_id == issue.id
        )
    )
    existing_task = existing_task_res.scalars().first()
    if existing_task:
        issue.status = IssueStatus.IN_TASK
        await db.commit()
        await db.refresh(existing_task)
        return existing_task

    # Update Issue status
    issue.status = IssueStatus.IN_TASK

    task = SEOTask(
        project_id=issue.project_id,
        issue_id=issue.id,
        assigned_to_id=assigned_user_id,
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

    log_user_action(
        request, "CONVERT_ISSUE_TO_TASK",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=project.id,
        issue_id=issue_id,
        task_id=task.id
    )
    return task


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    request: Request,
    task_id: int,
    task_in: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(SEOTask).where(SEOTask.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    project = await verify_project_access(task.project_id, current_user, db)

    if task_in.assigned_to_id is not None:
        await _verify_assigned_user(task_in.assigned_to_id, task.project_id, db)
        task.assigned_to_id = task_in.assigned_to_id

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

    await db.commit()
    await db.refresh(task)

    log_user_action(
        request, "UPDATE_TASK",
        user_id=current_user.id,
        organization_id=project.organization_id,
        project_id=task.project_id,
        task_id=task_id,
        status=task.status.value if hasattr(task.status, 'value') else str(task.status)
    )
    return task


@router.delete("/{task_id}")
async def delete_task(
    request: Request,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(SEOTask).where(SEOTask.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    project = await verify_project_access(task.project_id, current_user, db)
    org_id = project.organization_id
    proj_id = task.project_id

    await db.delete(task)
    await db.commit()

    log_user_action(
        request, "DELETE_TASK",
        user_id=current_user.id,
        organization_id=org_id,
        project_id=proj_id,
        task_id=task_id
    )
    return {"message": "Task deleted successfully"}


@router.get("/scheduled/{project_id}")
async def list_scheduled_jobs(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists all scheduled background jobs for a project.
    Auto-initializes standard jobs (crawl, rank_check, gbp_sync, review_sync, gsc_sync, ga4_sync) if not present.
    """
    await verify_project_access(project_id, current_user, db)
    from app.services.scheduler import JobSchedulerService
    jobs = await JobSchedulerService.get_or_create_project_jobs(project_id, db)
    return [
        {
            "id": j.id,
            "project_id": j.project_id,
            "job_type": j.job_type,
            "frequency": j.frequency,
            "status": j.status,
            "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
            "next_run_at": j.next_run_at.isoformat() if j.next_run_at else None,
            "last_result_summary": j.last_result_summary
        }
        for j in jobs
    ]


@router.post("/scheduled/{job_id}/run")
async def run_scheduled_job_now(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually triggers execution of a scheduled job, running the real background service.
    """
    from app.models.analytics import ScheduledJob
    from app.services.scheduler import JobSchedulerService

    res = await db.execute(select(ScheduledJob).where(ScheduledJob.id == job_id))
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found.")

    await verify_project_access(job.project_id, current_user, db)

    try:
        outcome = await JobSchedulerService.execute_job(job_id, db)
        return {"success": True, "result": outcome}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Job execution failed: {str(e)}")

