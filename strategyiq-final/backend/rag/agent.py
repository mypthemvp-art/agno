"""Tier-aware RAG agent — routes to Claude/GPT/Grok by subscription tier."""

from openai import OpenAI
from anthropic import Anthropic

from config import settings
from constants import SEC_DISCLAIMER, TIER_LIMITS, UserTier
from integrations.grok import grok_client
from rag.ingest import search_filings


class TierAgent:
    def __init__(self) -> None:
        self.openai = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.anthropic = Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None

    async def run(
        self,
        query: str,
        tier: UserTier,
        use_rag: bool = True,
        route_breaking: bool = False,
    ) -> dict:
        limits = TIER_LIMITS[tier]
        context = ""

        if use_rag and tier != UserTier.BEGINNER:
            hits = search_filings(query, top_k=5)
            context = "\n".join(h["text"] for h in hits)

        if route_breaking or any(kw in query.lower() for kw in ("breaking", "trending", "news")):
            result = await grok_client.chat(
                f"Context:\n{context}\n\nQuery: {query}\n{SEC_DISCLAIMER}",
                search_mode="on" if tier != UserTier.BEGINNER else "auto",
            )
            return {"response": result["response"], "model": "grok-2", "tier": tier.value}

        system = f"You are StrategyIQ, a financial terminal assistant. {SEC_DISCLAIMER}"
        prompt = f"Context from SEC filings:\n{context}\n\nUser: {query}" if context else query

        if tier == UserTier.ELITE and self.anthropic:
            msg = self.anthropic.messages.create(
                model=limits["model"],
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text if msg.content else ""
            return {"response": text, "model": limits["model"], "tier": tier.value}

        if self.openai:
            model = limits["model"]
            resp = self.openai.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1024,
            )
            text = resp.choices[0].message.content or ""
            return {"response": text, "model": model, "tier": tier.value}

        return {
            "response": "AI provider not configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.",
            "model": "none",
            "tier": tier.value,
        }


tier_agent = TierAgent()
