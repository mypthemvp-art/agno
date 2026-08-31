from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.config import settings
from app.constants import TIER_LIMITS, UserTier
from app.models import QueryLog, Subscription, User

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: int | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    result = await db.execute(
        select(User).options(selectinload(User.subscription)).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_user_tier(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserTier:
    """Resolve effective tier from subscription.active and tier field."""
    tier = UserTier.BEGINNER

    if user.subscription and user.subscription.active:
        try:
            tier = UserTier(user.subscription.tier)
        except ValueError:
            tier = UserTier.BEGINNER
    elif user.tier:
        try:
            tier = UserTier(user.tier)
        except ValueError:
            tier = UserTier.BEGINNER

    return tier


def require_tier(minimum: UserTier):
    """Dependency factory for tier-gated endpoints."""

    tier_order = {UserTier.BEGINNER: 0, UserTier.PRO: 1, UserTier.ELITE: 2}

    async def _check(tier: UserTier = Depends(get_user_tier)) -> UserTier:
        if tier_order[tier] < tier_order[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {minimum.value} tier or higher",
            )
        return tier

    return _check


async def check_query_limit(
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Enforce daily query limits for beginner tier."""
    limits = TIER_LIMITS[tier]
    max_queries = limits["queries_per_day"]
    if max_queries is None:
        return

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(QueryLog.id)).where(
            QueryLog.user_id == user.id,
            QueryLog.created_at >= today_start,
        )
    )
    count = result.scalar() or 0
    if count >= max_queries:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily query limit ({max_queries}) reached. Upgrade to Pro for unlimited access.",
        )


async def log_query(
    user: User,
    endpoint: str,
    db: AsyncSession,
) -> None:
    db.add(QueryLog(user_id=user.id, endpoint=endpoint))
    await db.commit()
