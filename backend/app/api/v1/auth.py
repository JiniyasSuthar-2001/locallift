from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.config import settings
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.deps import get_current_user
from app.models.user import User, Organization, OrganizationMember, OrgRole
from app.schemas.auth import Token, UserRegister, UserOut, UserLogin

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=Token)
async def register(user_in: UserRegister, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )

    # Create user
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        is_superuser=False
    )
    db.add(user)
    await db.flush()

    # Create initial organization
    org_name = user_in.organization_name or f"{user_in.full_name}'s Agency"
    slug = org_name.lower().replace(" ", "-").replace("'", "") + f"-{user.id}"
    org = Organization(
        name=org_name,
        slug=slug,
        plan="agency_pro"
    )
    db.add(org)
    await db.flush()

    # Create membership as OWNER
    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=OrgRole.OWNER
    )
    db.add(member)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(subject=user.id)
    user_out = UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        organization_id=org.id,
        role=OrgRole.OWNER.value
    )
    return Token(access_token=access_token, token_type="bearer", user=user_out)

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user org membership
    mem_result = await db.execute(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    )
    mem = mem_result.scalars().first()
    org_id = mem.organization_id if mem else None
    role = mem.role.value if mem else "owner"

    access_token = create_access_token(subject=user.id)
    user_out = UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        organization_id=org_id,
        role=role
    )
    return Token(access_token=access_token, token_type="bearer", user=user_out)

@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    mem_result = await db.execute(
        select(OrganizationMember).where(OrganizationMember.user_id == current_user.id)
    )
    mem = mem_result.scalars().first()
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        created_at=current_user.created_at,
        organization_id=mem.organization_id if mem else None,
        role=mem.role.value if mem else "owner"
    )
