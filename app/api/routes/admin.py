"""Trainer / admin dashboard endpoints — the live view over all client data."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession, ensure_client_visible, require_module
from app.core.security import hash_password
from app.models.booking import Booking, BookingStatus
from app.models.client_note import ClientNote
from app.models.nutrition_plan import NutritionPlan
from app.models.payment import Payment, PaymentStatus
from app.models.progress import ProgressEntry
from app.models.user import User, UserRole
from app.models.workout_plan import WorkoutPlan
from app.schemas.common import Ok
from app.schemas.payment import PaymentPublic
from app.schemas.user import (
    AdminClientCreate,
    AdminUserUpdate,
    BulkAssignTrainerRequest,
    UserPublic,
)

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

    pending_approvals = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.client, User.is_approved.is_(False))
    )

    stats: dict = {
        "total_clients": total_clients or 0,
        "active_clients": active_clients or 0,
        "pending_approvals": pending_approvals or 0,
        "pending_bookings": pending_bookings or 0,
        "upcoming_bookings": upcoming_bookings or 0,
    }

    # Revenue is a company financial record, not a coaching metric — it's
    # computed here only for Admins, full stop. This is intentionally NOT
    # gated by the Role Matrix's "overview" module like the rest of this
    # endpoint: there's no toggle that can hand a Trainer visibility into
    # how much money the company is making (see app/core/rbac.py).
    if _staff.role == UserRole.admin:
        revenue_cents = await db.scalar(
            select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
                Payment.status == PaymentStatus.succeeded
            )
        )
        stats["revenue_cents"] = revenue_cents or 0
    else:
        # In place of revenue, a Trainer's dashboard home page surfaces a
        # snapshot of their own coaching workspace instead — the Notes /
        # Nutrition / Workout tools that replaced the revenue widget (see
        # app/api/routes/coaching.py and dashboard/src/pages/ClientDetail.jsx).
        # Scoped to their assigned roster, same as their Clients list.
        own_clients = select(User.id).where(User.assigned_trainer_id == _staff.id)
        stats["notes_count"] = await db.scalar(
            select(func.count())
            .select_from(ClientNote)
            .where(ClientNote.client_id.in_(own_clients))
        ) or 0
        stats["nutrition_plans_count"] = await db.scalar(
            select(func.count())
            .select_from(NutritionPlan)
            .where(NutritionPlan.client_id.in_(own_clients))
        ) or 0
        stats["workout_plans_count"] = await db.scalar(
            select(func.count())
            .select_from(WorkoutPlan)
            .where(WorkoutPlan.client_id.in_(own_clients))
        ) or 0

    return stats


@router.get("/clients", response_model=list[UserPublic])
async def list_clients(
    _staff: ClientsAccess,
    db: DbSession,
    q: str | None = Query(default=None, description="Search name/email"),
    approval_status: str | None = Query(
        default=None, description="Filter by approval status: pending, approved, or all"
    ),
) -> list[User]:
    stmt = select(User).where(User.role == UserRole.client).order_by(User.created_at.desc())
    # Trainers only ever see clients assigned to them — Admins see
    # everyone. This is what makes "assigned trainer" a real separation
    # of duties rather than just a label (see User.assigned_trainer_id).
    if _staff.role == UserRole.trainer:
        stmt = stmt.where(User.assigned_trainer_id == _staff.id)
    if approval_status == "pending":
        stmt = stmt.where(User.is_approved.is_(False))
    elif approval_status == "approved":
        stmt = stmt.where(User.is_approved.is_(True))
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


@router.post("/clients", response_model=UserPublic, status_code=201)
async def admin_create_client(
    payload: AdminClientCreate, _admin: AdminUser, db: DbSession
) -> User:
    """Admin creates a new client account directly with pre-approved status."""
    existing = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        )
    if payload.assigned_trainer_id is not None:
        trainer = await db.get(User, payload.assigned_trainer_id)
        if trainer is None or trainer.role != UserRole.trainer or not trainer.is_active:
            raise HTTPException(
                status_code=400, detail="assigned_trainer_id must reference an active trainer"
            )
    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        goal=payload.goal,
        weight_lbs=payload.weight_lbs,
        height=payload.height,
        role=UserRole.client,
        is_active=True,
        is_approved=True,
        assigned_trainer_id=payload.assigned_trainer_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/clients/{client_id}", response_model=Ok)
async def admin_delete_client(client_id: int, _admin: AdminUser, db: DbSession) -> Ok:
    """Admin permanently deletes a client account and cascades their coaching data."""
    user = await db.get(User, client_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Client not found")
    if user.role != UserRole.client:
        raise HTTPException(
            status_code=400, detail="Only client accounts can be deleted via this endpoint"
        )
    await db.delete(user)
    await db.commit()
    return Ok()


@router.patch("/clients/{client_id}/approve", response_model=UserPublic)
async def admin_approve_client(client_id: int, _admin: AdminUser, db: DbSession) -> User:
    """Admin approves a pending client account for portal access."""
    user = await db.get(User, client_id)
    if user is None or user.role != UserRole.client:
        raise HTTPException(status_code=404, detail="Client not found")
    user.is_approved = True
    user.is_active = True
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