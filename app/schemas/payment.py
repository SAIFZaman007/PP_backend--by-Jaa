from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentItemType, PaymentStatus, PaymentType


class CartItemIn(BaseModel):
    """One line the client wants to buy. Only `type`, `id`, and `quantity`
    are trusted from the browser — price is always re-looked-up server-side
    in payments.py so a tampered request can never buy anything below its
    real price."""

    type: Literal["service", "plan"]
    id: int
    quantity: int = Field(default=1, ge=1, le=20)


class CheckoutRequest(BaseModel):
    # Single-item modes (kept for backward compatibility — the existing
    # Pricing section uses plan_slug directly):
    plan_slug: str | None = None          # for subscription/plan checkout
    amount_cents: int | None = None       # for ad-hoc one-off charges
    description: str | None = None
    type: PaymentType = PaymentType.one_time
    # Cart mode — one or more services/plans bought together. When present,
    # this takes priority over plan_slug/amount_cents.
    items: list[CartItemIn] | None = None


class CheckoutResponse(BaseModel):
    checkout_url: str | None = None
    payment_id: int
    stripe_enabled: bool


class PaymentItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    item_type: PaymentItemType
    service_id: int | None
    plan_id: int | None
    name: str
    unit_price_cents: int
    quantity: int
    subtotal_cents: int


class PaymentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None
    amount_cents: int
    currency: str
    status: PaymentStatus
    type: PaymentType
    description: str | None
    created_at: datetime
    items: list[PaymentItemPublic] = []