from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.auth import create_access_token, get_current_user, hash_password, verify_password
from backend.app.db.database import get_db
from backend.app.db.models import User


router = APIRouter(prefix="/api", tags=["auth"])


class UserPublic(BaseModel):
    id: int
    username: str
    role: str
    school_id: str
    school_name: str
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: Literal["teacher", "student"]
    school_id: str
    school_name: str
    full_name: str


class LoginRequest(BaseModel):
    username: str
    password: str
    role: Literal["teacher", "student"]


class AuthResponse(BaseModel):
    status: str
    token: str
    role: str
    redirect_url: str
    user: UserPublic


def _get_redirect_url(role: str) -> str:
    return "/teacher" if role == "teacher" else "/student"


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existed = db.query(User).filter(User.username == payload.username).first()
    if existed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该账号已存在",
        )

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        school_id=payload.school_id,
        school_name=payload.school_name,
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return AuthResponse(
        status="ok",
        token=create_access_token(user),
        role=user.role,
        redirect_url=_get_redirect_url(user.role),
        user=UserPublic.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or user.role != payload.role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号、密码或角色不匹配",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号、密码或角色不匹配",
        )

    return AuthResponse(
        status="ok",
        token=create_access_token(user),
        role=user.role,
        redirect_url=_get_redirect_url(user.role),
        user=UserPublic.model_validate(user),
    )


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "status": "ok",
        "user": UserPublic.model_validate(current_user).model_dump(),
    }
