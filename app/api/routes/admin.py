"""Trainer / admin dashboard endpoints — the live view over all client data."""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession, StaffUser
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.progress import ProgressEntry
from app.models.user import User, UserRole
from app.schemas.payment import PaymentPublic
from app.schemas.user import AdminUserUpdate, UserPublic

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def dashboard_stats(_staff: StaffUser, db: DbSession) -> dict:
    now = datetime.now(timezone.utc)

    total_clients = await db.scalar(
        select(func.count()).select_from(User).where(User.role == UserRole.client)
    )
    active_clients = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.client, User.is_active.is_(True))
    )
    pending_bookings = await db.scalar(
        select(func.count())
        .select_from(Booking)
        .where(Booking.status == BookingStatus.pending)
    )
    upcoming_bookings = await db.scalar(
        select(func.count())
        .select_from(Booking)
        .where(Booking.start_time >= now, Booking.status != BookingStatus.cancelled)
    )
    revenue_cents = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
            Payment.status == PaymentStatus.succeeded
        )
    )
    return {
        "total_clients": total_clients or 0,
        "active_clients": active_clients or 0,
        "pending_bookings": pending_bookings or 0,
        "upcoming_bookings": upcoming_bookings or 0,
        "revenue_cents": revenue_cents or 0,
    }


@router.get("/clients", response_model=list[UserPublic])
async def list_clients(
    _staff: StaffUser,
    db: DbSession,
    q: str | None = Query(default=None, description="Search name/email"),
) -> list[User]:
    stmt = select(User).where(User.role == UserRole.client).order_by(User.created_at.desc())
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(User.email).like(like)
            | func.lower(User.first_name).like(like)
            | func.lower(User.last_name).like(like)
        )
    return list(await db.scalars(stmt))


@router.get("/clients/{user_id}")
async def client_detail(user_id: int, _staff: StaffUser, db: DbSession) -> dict:
    user = await db.get(User, user_id)
    if user is None or user.role != UserRole.client:
        raise HTTPException(status_code=404, detail="Client not found")

    bookings_count = await db.scalar(
        select(func.count()).select_from(Booking).where(Booking.client_id == user_id)
    )
    progress_count = await db.scalar(
        select(func.count()).select_from(ProgressEntry).where(ProgressEntry.user_id == user_id)
    )
    last_progress = await db.scalar(
        select(ProgressEntry)
        .where(ProgressEntry.user_id == user_id)
        .order_by(ProgressEntry.entry_date.desc())
        .limit(1)
    )
    return {
        "user": UserPublic.model_validate(user).model_dump(),
        "bookings_count": bookings_count or 0,
        "progress_count": progress_count or 0,
        "latest_weight_lbs": last_progress.weight_lbs if last_progress else None,
    }


@router.patch("/users/{user_id}", response_model=UserPublic)
async def admin_update_user(
    user_id: int, payload: AdminUserUpdate, _admin: AdminUser, db: DbSession
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/payments", response_model=list[PaymentPublic])
async def all_payments(_staff: StaffUser, db: DbSession) -> list[Payment]:
    return list(
        await db.scalars(select(Payment).order_by(Payment.created_at.desc()).limit(200))
    )
