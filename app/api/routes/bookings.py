"""Bookings — public lead capture + staff management. Triggers email + calendar."""
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, StaffUser, get_optional_user
from app.db.session import AsyncSessionLocal
from app.models.booking import Booking, BookingStatus
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingPublic, BookingUpdate
from app.schemas.common import Ok
from app.services import google_calendar
from app.services.email import send_booking_notifications
from fastapi import Depends

router = APIRouter(prefix="/bookings", tags=["bookings"])
logger = logging.getLogger("peak.bookings")


async def _process_new_booking(booking_id: int) -> None:
    """Runs after the response: sync to Google Calendar, then email everyone.

    Post-response side effects must never raise — a failure here (calendar down,
    SMTP unreachable, etc.) must not affect the already-created booking.
    """
    try:
        async with AsyncSessionLocal() as db:
            booking = await db.get(Booking, booking_id)
            if booking is None:
                return
            event_id = google_calendar.create_event(booking)
            if event_id:
                booking.google_event_id = event_id
                await db.commit()
                await db.refresh(booking)
            await send_booking_notifications(booking)
    except Exception as exc:  # noqa: BLE001
        logger.error("Post-booking processing failed for booking %s: %s", booking_id, exc)


@router.post("", response_model=BookingPublic, status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreate,
    db: DbSession,
    bg: BackgroundTasks,
    current: User | None = Depends(get_optional_user),
) -> Booking:
    booking = Booking(
        client_id=current.id if current else None,
        name=payload.name,
        email=payload.email.lower(),
        phone=payload.phone,
        goal=payload.goal,
        service=payload.service,
        start_time=payload.start_time,
        notes=payload.notes,
        status=BookingStatus.pending,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    bg.add_task(_process_new_booking, booking.id)
    return booking


@router.get("/me", response_model=list[BookingPublic])
async def my_bookings(user: CurrentUser, db: DbSession) -> list[Booking]:
    rows = await db.scalars(
        select(Booking).where(Booking.client_id == user.id).order_by(Booking.start_time.desc())
    )
    return list(rows)


@router.get("", response_model=list[BookingPublic])
async def list_bookings(
    _staff: StaffUser,
    db: DbSession,
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
) -> list[Booking]:
    stmt = select(Booking).order_by(Booking.start_time.desc())
    if status_filter:
        stmt = stmt.where(Booking.status == status_filter)
    return list(await db.scalars(stmt))


@router.patch("/{booking_id}", response_model=BookingPublic)
async def update_booking(
    booking_id: int, payload: BookingUpdate, _staff: StaffUser, db: DbSession
) -> Booking:
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(booking, field, value)
    await db.commit()
    await db.refresh(booking)
    return booking


@router.post("/{booking_id}/cancel", response_model=Ok)
async def cancel_booking(booking_id: int, user: CurrentUser, db: DbSession) -> Ok:
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    # A client may only cancel their own booking; staff may cancel any.
    if not user.is_staff and booking.client_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    booking.status = BookingStatus.cancelled
    if booking.google_event_id:
        google_calendar.delete_event(booking.google_event_id)
        booking.google_event_id = None
    await db.commit()
    return Ok()
