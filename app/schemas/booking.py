from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    goal: str | None = Field(default=None, max_length=120)
    service: str = Field(default="Free Intro Call", max_length=120)
    start_time: datetime
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
    start_time: datetime
    status: BookingStatus
    notes: str | None
    google_event_id: str | None
    created_at: datetime
