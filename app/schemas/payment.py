from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentStatus, PaymentType


class CheckoutRequest(BaseModel):
    plan_slug: str | None = None          # for subscription/plan checkout
    amount_cents: int | None = None       # for ad-hoc one-off charges
    description: str | None = None
    type: PaymentType = PaymentType.one_time


class CheckoutResponse(BaseModel):
    checkout_url: str | None = None
    payment_id: int
    stripe_enabled: bool


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
