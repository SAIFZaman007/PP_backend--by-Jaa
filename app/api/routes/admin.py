"""Trainer / admin dashboard endpoints — the live view over all client data."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession, ensure_client_visible, require_module
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.progress import ProgressEntry
from app.models.user import User, UserRole
from app.schemas.common import Ok
from app.schemas.payment import PaymentPublic
from app.schemas.user import AdminUserUpdate, BulkAssignTrainerRequest, UserPublic

router = APIRouter(prefix="/admin", tags=["admin"])

# Role Matrix guards for this file's modules — Admins always pass; Trainers
# are checked against their role_permissions row (see require_module).
# "overview" and "clients" default to open for trainers; "payments" defaults
# closed (see app/core/rbac.py) per the client's explicit request to keep
# financial records Admin-only until granted.
OverviewAccess = Annotated[User, Depends(require_module("overview"))]
ClientsAccess = Annotated[User, Depends(require_module("clients"))]
PaymentsAccess = Annotated[User, Depends(require_module("payments"))]


@router.get("/stats")
async def dashboard_stats(_staff: OverviewAccess, db: DbSession) -> dict:
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
    _staff: ClientsAccess,
    db: DbSession,
    q: str | None = Query(default=None, description="Search name/email"),
) -> list[User]:
    stmt = select(User).where(User.role == UserRole.client).order_by(User.created_at.desc())
    # Trainers only ever see clients assigned to them — Admins see
    # everyone. This is what makes "assigned trainer" a real separation
    # of duties rather than just a label (see User.assigned_trainer_id).
    if _staff.role == UserRole.trainer:
        stmt = stmt.where(User.assigned_trainer_id == _staff.id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(User.email).like(like)
            | func.lower(User.first_name).like(like)
            | func.lower(User.last_name).like(like)
        )
    return list(await db.scalars(stmt))


@router.patch("/clients/assign-trainer", response_model=Ok)
async def bulk_assign_trainer(
    payload: BulkAssignTrainerRequest, _admin: AdminUser, db: DbSession
) -> Ok:
    """Bulk-assign action for the Clients list — sets (or, with a null
    assigned_trainer_id, clears) the assigned Trainer for every listed
    client in one transaction. Admin-only: reassigning clients between
    trainers is a staffing decision, not something a Trainer does to
    their own roster.
    """
    if payload.assigned_trainer_id is not None:
        trainer = await db.get(User, payload.assigned_trainer_id)
        if trainer is None or trainer.role != UserRole.trainer or not trainer.is_active:
            raise HTTPException(
                status_code=400, detail="assigned_trainer_id must reference an active trainer"
            )

    await db.execute(
        update(User)
        .where(User.id.in_(payload.client_ids), User.role == UserRole.client)
        .values(assigned_trainer_id=payload.assigned_trainer_id)
    )
    await db.commit()
    return Ok()


@router.get("/clients/{user_id}")
async def client_detail(user_id: int, _staff: ClientsAccess, db: DbSession) -> dict:
    user = await db.get(User, user_id)
    if user is None or user.role != UserRole.client:
        raise HTTPException(status_code=404, detail="Client not found")
    ensure_client_visible(user, _staff)

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

    update_fields = payload.model_dump(exclude_unset=True)
    if update_fields.get("assigned_trainer_id") is not None:
        trainer = await db.get(User, update_fields["assigned_trainer_id"])
        if trainer is None or trainer.role != UserRole.trainer or not trainer.is_active:
            raise HTTPException(
                status_code=400, detail="assigned_trainer_id must reference an active trainer"
            )

    for field, value in update_fields.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/payments", response_model=list[PaymentPublic])
async def all_payments(_staff: PaymentsAccess, db: DbSession) -> list[Payment]:
    return list(
        await db.scalars(
            select(Payment)
            .options(selectinload(Payment.items))
            .order_by(Payment.created_at.desc(), Payment.id.desc())
            .limit(200)
        )
    )