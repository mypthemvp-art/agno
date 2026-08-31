"""Stripe subscription management for Pro and Elite tiers."""

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.constants import SEC_DISCLAIMER, UserTier
from app.dependencies import get_current_user, get_db
from app.models import Subscription, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/billing", tags=["Billing"])

stripe.api_key = settings.stripe_secret_key

TIER_PRICES = {
    UserTier.PRO: settings.stripe_pro_price_id,
    UserTier.ELITE: settings.stripe_elite_price_id,
}


class CheckoutRequest(BaseModel):
    tier: UserTier


@router.post("/checkout")
async def create_checkout(
    request: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if request.tier == UserTier.BEGINNER:
        raise HTTPException(status_code=400, detail="Beginner tier is free")

    price_id = TIER_PRICES.get(request.tier)
    if not price_id:
        raise HTTPException(status_code=500, detail="Stripe price not configured")

    if not user.stripe_customer_id:
        customer = stripe.Customer.create(email=user.email)
        user.stripe_customer_id = customer.id
        await db.commit()

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url="http://localhost:3000/billing/success",
        cancel_url="http://localhost:3000/billing/cancel",
        metadata={"user_id": str(user.id), "tier": request.tier.value},
    )
    return {"checkout_url": session.url, "disclaimer": SEC_DISCLAIMER}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook") from exc

    if event["type"] == "customer.subscription.updated":
        sub_data = event["data"]["object"]
        customer_id = sub_data["customer"]
        result = await db.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
        if user:
            sub_result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
            subscription = sub_result.scalar_one_or_none()
            if not subscription:
                subscription = Subscription(user_id=user.id)
                db.add(subscription)

            subscription.stripe_subscription_id = sub_data["id"]
            subscription.active = sub_data["status"] == "active"
            subscription.tier = sub_data.get("metadata", {}).get("tier", "pro")
            await db.commit()

    elif event["type"] == "customer.subscription.deleted":
        sub_data = event["data"]["object"]
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_data["id"])
        )
        subscription = result.scalar_one_or_none()
        if subscription:
            subscription.active = False
            subscription.tier = "beginner"
            await db.commit()

    return {"status": "ok"}


@router.get("/status")
async def subscription_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    subscription = result.scalar_one_or_none()
    return {
        "tier": subscription.tier if subscription and subscription.active else "beginner",
        "active": subscription.active if subscription else False,
        "disclaimer": SEC_DISCLAIMER,
    }
