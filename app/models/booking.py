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
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"),
        default=BookingStatus.pending,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    # Google Calendar event id once synced.
    google_event_id: Mapped[str | None] = mapped_column(String(200))

    client: Mapped[User | None] = relationship(
        back_populates="bookings", foreign_keys=[client_id]
    )
