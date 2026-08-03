"""Pricing / subscription plan catalog (Starter, Peak, Elite …)."""
import enum

from sqlalchemy import JSON, Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class BillingInterval(str, enum.Enum):
    one_time = "one_time"
    month = "month"


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(160))
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    interval: Mapped[BillingInterval] = mapped_column(
        Enum(BillingInterval, name="billing_interval"),
        default=BillingInterval.month,
        nullable=False,
    )
    features: Mapped[list] = mapped_column(JSON, default=list)
    stripe_price_id: Mapped[str | None] = mapped_column(String(120))
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
