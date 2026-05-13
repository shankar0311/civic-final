from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User
from routers.auth import get_current_user
from utils.security import get_password_hash, verify_password

router = APIRouter()


class UserProfileResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    role: str
    is_active: bool


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


def _profile_response(user: User) -> UserProfileResponse:
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.name,
        role=user.role.value,
        is_active=getattr(user, "is_active", True),
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    return _profile_response(current_user)


@router.patch("/me", response_model=UserProfileResponse)
async def update_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update_fields = payload.model_fields_set

    if "email" in update_fields and payload.email is not None and payload.email != current_user.email:
        result = await db.execute(
            select(User).where(User.email == payload.email, User.id != current_user.id)
        )
        if result.scalars().first():
            raise HTTPException(status_code=409, detail="Email already taken")
        current_user.email = payload.email

    if "full_name" in update_fields and payload.full_name is not None:
        current_user.name = payload.full_name

    await db.commit()
    await db.refresh(current_user)
    return _profile_response(current_user)


@router.post("/me/change-password", response_model=UserProfileResponse)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters")

    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.hashed_password = get_password_hash(payload.new_password)
    await db.commit()
    await db.refresh(current_user)
    return _profile_response(current_user)
