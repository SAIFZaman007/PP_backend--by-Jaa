"""Payments — list own history, start Stripe checkout, receive webhooks."""
import logging

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models.payment import Payment, PaymentStatus
from app.models.plan import Plan
from app.schemas.payment import CheckoutRequest, CheckoutResponse, PaymentPublic
from app.services import stripe_service

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger("peak.payments")


@router.get("/config")
async def payments_config() -> dict:
    return {
        "stripe_enabled": stripe_service.is_enabled(),
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }


@router.get("/me", response_model=list[PaymentPublic])
async def my_payments(user: CurrentUser, db: DbSession) -> list[Payment]:
    rows = await db.scalars(
        select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.desc())
    )
    return list(rows)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest, user: CurrentUser, db: DbSession
) -> CheckoutResponse:
    # Resolve amount/description from a plan or an ad-hoc amount.
    amount = payload.amount_cents
    description = payload.description or "Peak Physique payment"
    if payload.plan_slug:
        plan = await db.scalar(select(Plan).where(Plan.slug == payload.plan_slug))
        if plan is None:
            raise HTTPException(status_code=404, detail="Plan not found")
        amount = plan.price_cents
        description = f"{plan.name} plan"
    if not amount or amount <= 0:
        raise HTTPException(status_code=400, detail="A valid amount or plan is required")

    payment = Payment(
        user_id=user.id,
        amount_cents=amount,
        description=description,
        type=payload.type,
        status=PaymentStatus.pending,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    checkout_url = stripe_service.create_checkout_session(
        amount_cents=amount,
        description=description,
        customer_email=user.email,
        metadata={"payment_id": str(payment.id), "user_id": str(user.id)},
    )
    if checkout_url:
        payment.stripe_session_id = checkout_url.split("/")[-1][:200]
        await db.commit()

    return CheckoutResponse(
        checkout_url=checkout_url,
        payment_id=payment.id,
        stripe_enabled=stripe_service.is_enabled(),
    )


@router.post("/webhook")
async def stripe_webhook(request: Request, db: DbSession) -> dict:
    if not stripe_service.is_enabled():
        raise HTTPException(status_code=400, detail="Stripe not configured")
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe_service.construct_webhook_event(payload, signature)
    except Exception as exc:
        logger.error("Invalid Stripe webhook: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        payment_id = (session.get("metadata") or {}).get("payment_id")
        if payment_id:
            payment = await db.get(Payment, int(payment_id))
            if payment:
                payment.status = PaymentStatus.succeeded
                payment.stripe_payment_intent_id = session.get("payment_intent")
                await db.commit()
    return {"received": True}
