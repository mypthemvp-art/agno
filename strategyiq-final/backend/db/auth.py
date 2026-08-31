from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from config import settings
from constants import TIER_LIMITS, UserTier
from db.models import QueryLog, Subscription, User
from db.session import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, tier: str, email: str = "") -> str:
    expire = datetime.now(UTC) + timedelta(hours=24)
    payload = {"sub": str(user_id), "tier": tier, "email": email, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = db.query(User).options(selectinload(User.subscription)).filter(User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_user_tier(user: User = Depends(get_current_user)) -> UserTier:
    if user.subscription and user.subscription.active:
        try:
            return UserTier(user.subscription.tier)
        except ValueError:
            return UserTier.BEGINNER
    try:
        return UserTier(user.tier)
    except ValueError:
        return UserTier.BEGINNER


def require_tier(minimum: UserTier):
    order = {UserTier.BEGINNER: 0, UserTier.PRO: 1, UserTier.ELITE: 2}

    def _check(tier: UserTier = Depends(get_user_tier)) -> UserTier:
        if order[tier] < order[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {minimum.value} tier or higher",
            )
        return tier

    return _check


def check_query_limit(
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: Session = Depends(get_db),
) -> None:
    max_queries = TIER_LIMITS[tier]["queries_per_day"]
    if max_queries is None:
        return
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.query(func.count(QueryLog.id)).filter(
        QueryLog.user_id == user.id, QueryLog.created_at >= today
    ).scalar() or 0
    if count >= max_queries:
        raise HTTPException(status_code=429, detail=f"Daily limit ({max_queries}) reached. Upgrade to Pro.")


def log_query(user: User, endpoint: str, db: Session) -> None:
    db.add(QueryLog(user_id=user.id, endpoint=endpoint))
    db.commit()
