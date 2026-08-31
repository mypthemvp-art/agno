"""AI agent + Grok routing with tier gating."""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from constants import SEC_DISCLAIMER, UserTier
from db.auth import check_query_limit, get_current_user, get_user_tier, log_query
from db.models import User
from db.session import get_db
from integrations.grok import grok_client
from rag.agent import tier_agent
from sqlalchemy.orm import Session

router = APIRouter(prefix="/ai", tags=["AI Agent"])


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class AgentRequest(BaseModel):
    messages: list[ChatMessage]
    agent_id: str | None = None
    use_rag: bool = True


@router.post("/agent")
async def ai_agent(
    request: AgentRequest,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: Session = Depends(get_db),
    x_user_tier: str | None = Header(None, alias="X-User-Tier"),
    _: None = Depends(check_query_limit),
):
    if x_user_tier and x_user_tier != tier.value:
        raise HTTPException(status_code=403, detail="X-User-Tier mismatch")

    last = next((m.content for m in reversed(request.messages) if m.role == "user"), None)
    if not last:
        raise HTTPException(status_code=400, detail="No user message")

    route_grok = any(kw in last.lower() for kw in ("breaking", "trending", "x.com", "twitter"))
    result = await tier_agent.run(last, tier, use_rag=request.use_rag, route_breaking=route_grok)
    log_query(user, "/ai/agent", db)
    return {**result, "disclaimer": SEC_DISCLAIMER}


@router.post("/grok/breaking")
async def breaking(topic: str = "markets", tier: UserTier = Depends(get_user_tier)):
    return {**(await grok_client.breaking(topic)), "tier": tier.value}


@router.post("/grok/trending")
async def trending(symbols: list[str] | None = None, tier: UserTier = Depends(get_user_tier)):
    return {**(await grok_client.trending(symbols)), "tier": tier.value}
