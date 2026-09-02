"""AI agent + Grok routing with tier gating."""

import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
    messages: list[ChatMessage] | None = None
    prompt: str | None = None
    symbol: str = "AAPL"
    asset_class: str = "stock"
    agent_id: str | None = None
    use_rag: bool = True


class AgentStreamRequest(BaseModel):
    prompt: str
    symbol: str = "AAPL"
    asset_class: str = "stock"
    tier: str | None = None
    user_id: str | None = None


def _extract_prompt(request: AgentRequest) -> str:
    if request.prompt:
        return request.prompt
    if request.messages:
        last = next((m.content for m in reversed(request.messages) if m.role == "user"), None)
        if last:
            return last
    raise HTTPException(status_code=400, detail="No user message")


@router.post("/agent")
async def ai_agent(
    request: AgentRequest,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: Session = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    prompt = _extract_prompt(request)
    route_grok = any(kw in prompt.lower() for kw in ("breaking", "trending", "x.com", "twitter"))
    result = await tier_agent.run(prompt, tier, use_rag=request.use_rag, route_breaking=route_grok)
    log_query(user, "/ai/agent", db)
    return {**result, "symbol": request.symbol, "disclaimer": SEC_DISCLAIMER}


async def _stream_tokens(text: str) -> AsyncGenerator[str, None]:
    words = text.split(" ")
    for i, word in enumerate(words):
        chunk = word if i == 0 else f" {word}"
        yield f"data: {json.dumps({'token': chunk})}\n\n"
    yield f"data: {json.dumps({'done': True, 'disclaimer': SEC_DISCLAIMER})}\n\n"


@router.post("/agent/stream")
async def ai_agent_stream(
    request: AgentStreamRequest,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: Session = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    route_grok = any(kw in request.prompt.lower() for kw in ("breaking", "trending", "x.com", "twitter"))
    result = await tier_agent.run(request.prompt, tier, use_rag=True, route_breaking=route_grok)
    log_query(user, "/ai/agent/stream", db)
    return StreamingResponse(_stream_tokens(result["response"]), media_type="text/event-stream")


@router.post("/grok/breaking")
async def breaking(topic: str = "markets", tier: UserTier = Depends(get_user_tier)):
    return {**(await grok_client.breaking(topic)), "tier": tier.value}


@router.post("/grok/trending")
async def trending(symbols: list[str] | None = None, tier: UserTier = Depends(get_user_tier)):
    return {**(await grok_client.trending(symbols)), "tier": tier.value}
