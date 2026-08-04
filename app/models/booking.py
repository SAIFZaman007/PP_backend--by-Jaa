"""Booking / intro-call model. Works for logged-in clients AND public leads."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class BookingStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    completed = "completed"
    cancelled = "cancelled"


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Optional link to a registered client; null for anonymous leads.
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    # Contact details captured on the form (kept even for logged-in users).
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    goal: Mapped[str | None] = mapped_column(String(120))

    service: Mapped[str] = mapped_column(String(120), default="Free Intro Call", nullable=False)
    # Nullable on purpose: a session bought through checkout (see
    # payments.py) becomes a booking the instant payment succeeds, but no
    # time slot exists yet — the coach sets one from the dashboard. The
    # public booking form still always supplies a real time (see
    # BookingCreate), so this only ever reads as null for that
    # "awaiting scheduling" case.
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"),
        default=BookingStatus.pending,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    # Google Calendar event id once synced.
    google_event_id: Mapped[str | None] = mapped_column(String(200))

    # Set only for bookings auto-created from a paid checkout line item —
    # lets the coach trace "why does this booking exist" back to the
    # purchase, and keeps that creation idempotent (see payments.py).
    payment_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_items.id", ondelete="SET NULL"), index=True
    )

    client: Mapped[User | None] = relationship(
        back_populates="bookings", foreign_keys=[client_id]
    )