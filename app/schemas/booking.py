from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    goal: str | None = Field(default=None, max_length=120)
    service: str = Field(default="Free Intro Call", max_length=120)
    # Optional on purpose: the public booking form no longer collects a
    # client-stated date/time preference (see Booking.jsx) — every call is
    # scheduled from the coach's own calendar after the request comes in,
    # the same "awaiting scheduling" flow already used for bookings that
    # come from a paid checkout (see Booking.start_time / payments.py).
    start_time: datetime | None = None
    notes: str | None = None


class BookingUpdate(BaseModel):
    status: BookingStatus | None = None
    start_time: datetime | None = None
    notes: str | None = None


class BookingPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int | None
    name: str
    email: EmailStr
    phone: str | None
    goal: str | None
    service: str
    # Null means "purchased but not yet scheduled" — see Booking.start_time.
    start_time: datetime | None
    status: BookingStatus
    notes: str | None
    google_event_id: str | None
    # Present when this booking was auto-created from a checkout line item
    # rather than the public booking form.
    payment_item_id: int | None
    created_at: datetime