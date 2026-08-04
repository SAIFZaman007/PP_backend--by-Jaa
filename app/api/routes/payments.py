"""Payments — list own history, start Stripe checkout, receive webhooks."""
import logging

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models.content import Service
from app.models.payment import Payment, PaymentItem, PaymentItemType, PaymentStatus, PaymentType
from app.models.plan import Plan
from app.schemas.payment import CartItemIn, CheckoutRequest, CheckoutResponse, PaymentPublic
from app.services import stripe_service
from app.services.stripe_service import LineItem

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
        select(Payment)
        .options(selectinload(Payment.items))
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc(), Payment.id.desc())
    )
    return list(rows)


async def _resolve_cart(items: list[CartItemIn], db: DbSession) -> list[PaymentItem]:
    """Turns client-submitted {type, id, quantity} into priced, named
    PaymentItem rows — always looking the price up server-side so a
    tampered request can never pay less than the real price."""
    resolved: list[PaymentItem] = []
    for entry in items:
        if entry.type == "service":
            service = await db.get(Service, entry.id)
            if service is None or not service.is_active or not service.is_purchasable:
                raise HTTPException(
                    status_code=404, detail=f"Service {entry.id} is not available for purchase"
                )
            unit_price = service.price_cents
            if unit_price <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"'{service.name}' doesn't have a price set yet — contact us to book it.",
                )
            resolved.append(
                PaymentItem(
                    item_type=PaymentItemType.service,
                    service_id=service.id,
                    name=service.name,
                    unit_price_cents=unit_price,
                    quantity=entry.quantity,
                    subtotal_cents=unit_price * entry.quantity,
                )
            )
        else:  # "plan"
            plan = await db.get(Plan, entry.id)
            if plan is None or not plan.is_active:
                raise HTTPException(status_code=404, detail=f"Plan {entry.id} is not available")
            resolved.append(
                PaymentItem(
                    item_type=PaymentItemType.plan,
                    plan_id=plan.id,
                    name=plan.name,
                    unit_price_cents=plan.price_cents,
                    quantity=entry.quantity,
                    subtotal_cents=plan.price_cents * entry.quantity,
                )
            )
    if not resolved:
        raise HTTPException(status_code=400, detail="Cart is empty")
    return resolved


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest, user: CurrentUser, db: DbSession
) -> CheckoutResponse:
    # ── Cart mode: one or more services/plans bought together ──────────
    if payload.items is not None:
        line_rows = await _resolve_cart(payload.items, db)
        total = sum(li.subtotal_cents for li in line_rows)
        summary = ", ".join(f"{li.name} x{li.quantity}" for li in line_rows)
        # Snapshot what Stripe needs *before* commit() expires these ORM
        # objects — touching li.name/li.unit_price_cents/li.quantity after
        # commit would trigger an async lazy-refresh outside of an awaited
        # context and crash with MissingGreenlet.
        stripe_items = [
            LineItem(name=li.name, unit_amount_cents=li.unit_price_cents, quantity=li.quantity)
            for li in line_rows
        ]

        payment = Payment(
            user_id=user.id,
            amount_cents=total,
            description=summary[:200],
            type=PaymentType.cart,
            status=PaymentStatus.pending,
        )
        payment.items = line_rows
        db.add(payment)
        await db.commit()
        await db.refresh(payment)

        checkout_url = stripe_service.create_checkout_session(
            items=stripe_items,
            customer_email=user.email,
            metadata={"payment_id": str(payment.id), "user_id": str(user.id)},
        )
        if checkout_url:
            payment.stripe_session_id = checkout_url.split("/")[-1][:200]
            await db.commit()

        return CheckoutResponse(
            checkout_url=checkout_url, payment_id=payment.id, stripe_enabled=stripe_service.is_enabled()
        )

    # ── Legacy single-item mode: a plan slug or an ad-hoc amount ────────
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
        items=[LineItem(name=description, unit_amount_cents=amount, quantity=1)],
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