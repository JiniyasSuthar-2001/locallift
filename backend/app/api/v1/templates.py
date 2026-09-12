import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from app.database import get_db
from app.core.deps import get_current_user, get_user_organization_ids, verify_project_access, verify_organization_membership
from app.models.user import User, OrganizationMember
from app.models.template import Template, TemplateUsage
from app.schemas.template import (
    TemplateOut,
    TemplateCreate,
    TemplateUpdate,
    TemplateApplyRequest,
    TemplateApplyResponse,
    TemplateValidateRequest,
    TemplateValidateResponse,
    TemplateImportRequest
)
from app.services.template_service import TemplateEngine

router = APIRouter(prefix="/templates", tags=["Templates"])

async def _get_user_primary_org_id(user: User, db: AsyncSession, requested_org_id: Optional[int] = None) -> int:
    """Helper to resolve and validate a user's target organization ID."""
    org_ids = await get_user_organization_ids(user.id, db)
    if not org_ids and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no associated organization."
        )

    if requested_org_id:
        if not user.is_superuser and requested_org_id not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not belong to the requested organization."
            )
        return requested_org_id

    if org_ids:
        return org_ids[0]
    return 1


@router.get("", response_model=List[TemplateOut])
async def list_templates(
    category: Optional[str] = None,
    template_type: Optional[str] = None,
    is_system: Optional[bool] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List templates with multi-tenant isolation: returns system templates + current user's organization templates."""
    # Ensure system templates are seeded
    await TemplateEngine.seed_system_templates(db)

    query = select(Template)
    conditions = []

    # Tenant scoping
    if not current_user.is_superuser:
        org_ids = await get_user_organization_ids(current_user.id, db)
        tenant_filter = or_(
            Template.is_system == True,
            Template.organization_id.in_(org_ids)
        )
        conditions.append(tenant_filter)

    if category and category != "all":
        conditions.append(Template.category == category)
    if template_type and template_type != "all":
        conditions.append(Template.template_type == template_type)
    if is_system is not None:
        conditions.append(Template.is_system == is_system)
    if search:
        search_filter = f"%{search.strip()}%"
        conditions.append(
            or_(
                Template.name.ilike(search_filter),
                Template.description.ilike(search_filter),
                Template.content.ilike(search_filter)
            )
        )

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Template.is_system.desc(), Template.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve single template by ID with tenant access verification."""
    stmt = select(Template).where(Template.id == template_id)
    res = await db.execute(stmt)
    template = res.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if not template.is_system and not current_user.is_superuser:
        org_ids = await get_user_organization_ids(current_user.id, db)
        if template.organization_id not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to view this template."
            )

    return template


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new custom user template with tenant validation."""
    # Resolve organization ID
    if data.project_id:
        proj = await verify_project_access(data.project_id, current_user, db)
        org_id = proj.organization_id
    else:
        org_id = await _get_user_primary_org_id(current_user, db, data.organization_id)

    # Validate content syntax
    is_valid, errors, warnings, detected_vars = TemplateEngine.validate_template(
        data.content, data.template_type, data.required_fields
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail={"message": "Validation failed", "errors": errors})

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", data.name.lower()).strip("-")
    
    vars_list = data.variables or []
    if not vars_list:
        vars_list = [{"name": v, "label": v.replace("_", " ").title(), "required": False} for v in detected_vars]

    template = Template(
        name=data.name,
        slug=slug,
        category=data.category,
        template_type=data.template_type,
        standard_type=data.standard_type or "Local SEO Standard",
        description=data.description,
        content=data.content,
        variables=vars_list,
        required_fields=data.required_fields or [],
        is_system=False,
        project_id=data.project_id,
        organization_id=org_id,
        created_by=current_user.full_name or current_user.email,
        version=1,
        usage_count=0
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.put("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: int,
    data: TemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update custom user template with tenant verification."""
    stmt = select(Template).where(Template.id == template_id)
    res = await db.execute(stmt)
    template = res.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System templates are read-only to preserve standards compliance. Please duplicate the template to customize it."
        )

    if not current_user.is_superuser:
        org_ids = await get_user_organization_ids(current_user.id, db)
        if template.organization_id not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to modify this template."
            )

    # Validate if content changed
    if data.content is not None:
        ttype = data.template_type or template.template_type
        is_valid, errors, _, _ = TemplateEngine.validate_template(data.content, ttype)
        if not is_valid:
            raise HTTPException(status_code=400, detail={"message": "Validation failed", "errors": errors})
        template.content = data.content

    if data.name is not None:
        template.name = data.name
        template.slug = re.sub(r"[^a-zA-Z0-9]+", "-", data.name.lower()).strip("-")
    if data.category is not None:
        template.category = data.category
    if data.template_type is not None:
        template.template_type = data.template_type
    if data.description is not None:
        template.description = data.description
    if data.variables is not None:
        template.variables = data.variables
    if data.required_fields is not None:
        template.required_fields = data.required_fields
    if data.standard_type is not None:
        template.standard_type = data.standard_type

    template.version += 1
    await db.commit()
    await db.refresh(template)
    return template


@router.post("/{template_id}/duplicate", response_model=TemplateOut)
async def duplicate_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Duplicate a template into the user's organization."""
    stmt = select(Template).where(Template.id == template_id)
    res = await db.execute(stmt)
    original = res.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="Template not found")

    if not original.is_system and not current_user.is_superuser:
        org_ids = await get_user_organization_ids(current_user.id, db)
        if original.organization_id not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to duplicate this template."
            )

    user_org_id = await _get_user_primary_org_id(current_user, db)
    copy_name = f"{original.name} (Copy)"
    copy_slug = f"{original.slug}-copy-{int(original.id)}"

    duplicate = Template(
        name=copy_name,
        slug=copy_slug,
        category=original.category,
        template_type=original.template_type,
        standard_type=original.standard_type,
        description=f"Customized copy of {original.name}",
        content=original.content,
        variables=original.variables,
        required_fields=original.required_fields,
        is_system=False,
        organization_id=user_org_id,
        created_by=current_user.full_name or current_user.email,
        version=1,
        usage_count=0
    )
    db.add(duplicate)
    await db.commit()
    await db.refresh(duplicate)
    return duplicate


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user-created template within tenant boundaries."""
    stmt = select(Template).where(Template.id == template_id)
    res = await db.execute(stmt)
    template = res.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.is_system:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="System templates cannot be deleted.")

    if not current_user.is_superuser:
        org_ids = await get_user_organization_ids(current_user.id, db)
        if template.organization_id not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to delete this template."
            )

    await db.delete(template)
    await db.commit()
    return None


@router.post("/{template_id}/apply", response_model=TemplateApplyResponse)
async def apply_template(
    template_id: int,
    data: TemplateApplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Apply and render a template after validating project and template access."""
    # Verify project access for target project
    await verify_project_access(data.project_id, current_user, db)

    stmt = select(Template).where(Template.id == template_id)
    res = await db.execute(stmt)
    template = res.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if not template.is_system and not current_user.is_superuser:
        org_ids = await get_user_organization_ids(current_user.id, db)
        if template.organization_id not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to use this template."
            )

    rendered, used_vars, missing_vars = await TemplateEngine.render_template(
        db=db,
        template=template,
        project_id=data.project_id,
        location_id=data.location_id,
        custom_variables=data.custom_variables
    )

    # Record usage
    template.usage_count += 1
    usage = TemplateUsage(
        template_id=template.id,
        project_id=data.project_id,
        applied_by=current_user.full_name or current_user.email,
        rendered_content=rendered
    )
    db.add(usage)
    await db.commit()

    return TemplateApplyResponse(
        template_id=template.id,
        template_name=template.name,
        rendered_content=rendered,
        variables_used=used_vars,
        missing_variables=missing_vars
    )


@router.post("/validate", response_model=TemplateValidateResponse)
async def validate_template_syntax(
    data: TemplateValidateRequest,
    current_user: User = Depends(get_current_user)
):
    """Validate template syntax, variables, and JSON structure without saving."""
    req_fields = [v.get("name") for v in (data.variables or []) if v.get("required")]
    is_valid, errors, warnings, detected_vars = TemplateEngine.validate_template(
        data.content, data.template_type, req_fields
    )
    return TemplateValidateResponse(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        detected_variables=detected_vars
    )


@router.post("/import", response_model=TemplateOut)
async def import_template(
    data: TemplateImportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Import and validate a structured template assigned to the user's organization."""
    content = data.file_content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Import content cannot be empty")

    user_org_id = await _get_user_primary_org_id(current_user, db)

    is_json = content.startswith("{") and content.endswith("}")
    template_type = data.template_type or ("schema_jsonld" if is_json else "content_markdown")
    category = data.category or ("schema" if is_json else "local_content")
    name = data.name or ("Imported Local Schema Template" if is_json else "Imported Local Content Template")

    is_valid, errors, warnings, detected_vars = TemplateEngine.validate_template(content, template_type)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={"message": "Import validation failed. Please correct syntax errors.", "errors": errors}
        )

    vars_list = [{"name": v, "label": v.replace("_", " ").title(), "required": False} for v in detected_vars]
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")

    template = Template(
        name=name,
        slug=slug,
        category=category,
        template_type=template_type,
        standard_type="Imported Template Standard",
        description=data.description or "User-imported template asset.",
        content=content,
        variables=vars_list,
        required_fields=[],
        is_system=False,
        organization_id=user_org_id,
        created_by=current_user.full_name or current_user.email,
        version=1,
        usage_count=0
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template
