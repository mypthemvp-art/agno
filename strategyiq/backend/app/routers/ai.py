"""AI agent endpoint for tier-gated chat."""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.constants import SEC_DISCLAIMER, TIER_LIMITS, UserTier
from app.dependencies import check_query_limit, get_current_user, get_user_tier, log_query
from app.integrations.grok import grok_client
from app.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db

router = APIRouter(prefix="/ai", tags=["AI Agent"])


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class AgentRequest(BaseModel):
    messages: list[ChatMessage]
    agent_id: str | None = None


class AgentResponse(BaseModel):
    response: str
    tier: str
    agent_id: str | None = None
    disclaimer: str = SEC_DISCLAIMER


@router.post("/agent", response_model=AgentResponse)
async def ai_agent(
    request: AgentRequest,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: AsyncSession = Depends(get_db),
    x_user_tier: str | None = Header(None, alias="X-User-Tier"),
    _: None = Depends(check_query_limit),
):
    """
    Tier-gated AI agent chat endpoint.
    Accepts JWT auth and optional X-User-Tier header from the Next.js proxy.
    """
    if x_user_tier and x_user_tier != tier.value:
        raise HTTPException(
            status_code=403,
            detail="X-User-Tier header does not match authenticated subscription tier",
        )

    if not request.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    last_user_msg = next(
        (m.content for m in reversed(request.messages) if m.role == "user"),
        None,
    )
    if not last_user_msg:
        raise HTTPException(status_code=400, detail="No user message found")

    limits = TIER_LIMITS[tier]

    if limits["custom_agents"]:
        agent_id = request.agent_id or "elite-custom-agent"
        prompt = (
            f"[Agent: {agent_id}] {last_user_msg}\n"
            "Provide detailed market analysis. Financial information only, not financial advice."
        )
    elif limits["signals"]:
        agent_id = request.agent_id or "pro-signals-agent"
        prompt = (
            f"[Signals] {last_user_msg}\n"
            "Include actionable market signals. Financial information only, not financial advice."
        )
    else:
        agent_id = request.agent_id or "beginner-agent"
        prompt = (
            f"{last_user_msg}\n"
            "Keep response concise. Data may be delayed. "
            "Financial information only, not financial advice."
        )

    grok_result = await grok_client.chat(prompt)
    await log_query(user, "/ai/agent", db)

    return AgentResponse(
        response=grok_result["response"],
        tier=tier.value,
        agent_id=agent_id,
    )
