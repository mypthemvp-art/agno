"""Authentication: register, login, me."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session, selectinload

from constants import SEC_DISCLAIMER
from db.auth import create_access_token, get_current_user, get_user_tier, hash_password, verify_password
from db.models import Subscription, User
from db.session import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tier: str
    disclaimer: str = SEC_DISCLAIMER


class UserResponse(BaseModel):
    id: int
    email: str
    tier: str
    subscription_active: bool
    disclaimer: str = SEC_DISCLAIMER


def _effective_tier(user: User) -> str:
    if user.subscription and user.subscription.active:
        return user.subscription.tier
    return user.tier


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=request.email, hashed_password=hash_password(request.password), tier="beginner")
    db.add(user)
    db.flush()

    subscription = Subscription(user_id=user.id, tier="beginner", active=False)
    db.add(subscription)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, "beginner", user.email)
    return TokenResponse(access_token=token, tier="beginner")


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .options(selectinload(User.subscription))
        .filter(User.email == request.email)
        .first()
    )
    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    tier = _effective_tier(user)
    token = create_access_token(user.id, tier, user.email)
    return TokenResponse(access_token=token, tier=tier)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    tier = _effective_tier(user)
    return UserResponse(
        id=user.id,
        email=user.email,
        tier=tier,
        subscription_active=bool(user.subscription and user.subscription.active),
    )
