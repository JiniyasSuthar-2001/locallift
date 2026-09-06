from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, Organization, OrganizationMember, Client, OrgRole

router = APIRouter(prefix="/organizations", tags=["Organizations & Clients"])

@router.get("/clients")
async def list_clients(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    mem_res = await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == current_user.id))
    memberships = mem_res.scalars().all()
    org_ids = [m.organization_id for m in memberships]

    result = await db.execute(
        select(Client).options(selectinload(Client.projects)).where(Client.organization_id.in_(org_ids))
    )
    clients = result.scalars().all()
    return [
        {
            "id": c.id,
            "organization_id": c.organization_id,
            "name": c.name,
            "contact_email": c.contact_email,
            "phone": c.phone,
            "notes": c.notes,
            "projects_count": len(c.projects),
            "projects": [{"id": p.id, "name": p.name, "health_score": p.health_score} for p in c.projects]
        }
        for c in clients
    ]

@router.post("/clients")
async def create_client(
    name: str,
    contact_email: Optional[str] = None,
    phone: Optional[str] = None,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    mem_res = await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == current_user.id))
    mem = mem_res.scalars().first()
    if not mem:
        raise HTTPException(status_code=400, detail="User is not part of an organization")

    client = Client(
        organization_id=mem.organization_id,
        name=name,
        contact_email=contact_email,
        phone=phone,
        notes=notes
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client
