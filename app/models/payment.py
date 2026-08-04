"""Payment records — Stripe checkout sessions, sessions & subscriptions."""
from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"


class PaymentType(str, enum.Enum):
    session = "session"
    subscription = "subscription"
    one_time = "one_time"
    cart = "cart"  # multi-item checkout (services and/or plans bought together)


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.pending,
        nullable=False,
        index=True,
    )
    type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="payment_type"), default=PaymentType.one_time, nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(200))

    stripe_session_id: Mapped[str | None] = mapped_column(String(200), index=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(200))

    user: Mapped[User | None] = relationship(back_populates="payments")
    items: Mapped[list[PaymentItem]] = relationship(
        back_populates="payment", cascade="all, delete-orphan", order_by="PaymentItem.id"
    )


class PaymentItemType(str, enum.Enum):
    service = "service"
    plan = "plan"


class PaymentItem(Base, TimestampMixin):
    """One line of a checkout — a specific service or plan, snapshotted at
    purchase time so the receipt stays accurate even if the admin later
    renames or re-prices the underlying Service/Plan."""

    __tablename__ = "payment_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    item_type: Mapped[PaymentItemType] = mapped_column(
        Enum(PaymentItemType, name="payment_item_type"), nullable=False
    )
    # Nullable on purpose: keeps the line item (and the receipt) intact even
    # if the referenced Service/Plan is deleted later.
    service_id: Mapped[int | None] = mapped_column(
        ForeignKey("services.id", ondelete="SET NULL"), index=True
    )
    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)  # snapshot
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # snapshot
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    payment: Mapped[Payment] = relationship(back_populates="items")