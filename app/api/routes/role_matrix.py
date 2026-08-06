"""Role Matrix — staff invitations + the dashboard permission matrix.

Two audiences hit this router:
  * Admins (AdminUser-guarded) manage invitations, the staff roster, and
    the module access toggles.
  * Anyone holding a valid invite token (no auth — they don't have an
    account yet) can preview and accept it.

Everything here only ever concerns the Trainer/Admin roles — clients are
untouched by any of this.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession, StaffUser
from app.core.config import settings
from app.core.rbac import DEFAULT_TRAINER_ACCESS, MODULE_KEYS, MODULE_LABELS, MODULES
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.invitation import Invitation, InvitationStatus
from app.models.role_permission import RolePermission
from app.models.user import User, UserRole
from app.schemas.auth import TokenPair
from app.schemas.common import Ok
from app.schemas.role_matrix import (
    InvitationAccept,
    InvitationAcceptPreview,
    InvitationCreate,
    InvitationPublic,
    ModuleAccessRow,
    ModuleAccessUpdate,
    MyAccess,
)
from app.schemas.user import UserPublic
from app.services.email import send_staff_invitation_email

router = APIRouter(prefix="/role-matrix", tags=["role-matrix"])
logger = logging.getLogger("peak.role_matrix")

INVITE_EXPIRE_DAYS = 7


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _invite_url(token: str) -> str:
    return f"{settings.DASHBOARD_URL.rstrip('/')}/accept-invite?token={token}"


async def _expire_stale(db: DbSession) -> None:
    """Lazily flips any pending invite whose expiry has passed — run before
    every read/accept so `status` is always trustworthy without needing a
    background cron job."""
    now = datetime.now(timezone.utc)
    stale = await db.scalars(
        select(Invitation).where(
            Invitation.status == InvitationStatus.pending, Invitation.expires_at < now
        )
    )
    changed = False
    for row in stale:
        row.status = InvitationStatus.expired
        changed = True
    if changed:
        await db.commit()


# ── Invitations (Admin only) ────────────────────────────────────────────


@router.post("/invitations", response_model=InvitationPublic, status_code=status.HTTP_201_CREATED)
async def invite_team_member(
    payload: InvitationCreate, admin: AdminUser, db: DbSession, bg: BackgroundTasks
) -> Invitation:
    email = payload.email.lower()

    existing_user = await db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already has an account.",
        )

    await _expire_stale(db)
    pending = await db.scalar(
        select(Invitation).where(
            Invitation.email == email, Invitation.status == InvitationStatus.pending
        )
    )
    if pending is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An invitation is already pending for this email. Resend it instead.",
        )

    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        email=email,
        role=payload.role,
        token_hash=_hash_token(token),
        status=InvitationStatus.pending,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRE_DAYS),
        invited_by_id=admin.id,
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    bg.add_task(
        send_staff_invitation_email, email, payload.role.value, _invite_url(token), admin.full_name
    )
    return invitation


@router.get("/invitations", response_model=list[InvitationPublic])
async def list_invitations(_admin: AdminUser, db: DbSession) -> list[Invitation]:
    await _expire_stale(db)
    rows = await db.scalars(select(Invitation).order_by(Invitation.created_at.desc()))
    return list(rows)


@router.post("/invitations/{invitation_id}/resend", response_model=InvitationPublic)
async def resend_invitation(
    invitation_id: int, admin: AdminUser, db: DbSession, bg: BackgroundTasks
) -> Invitation:
    invitation = await db.get(Invitation, invitation_id)
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.status not in (InvitationStatus.pending, InvitationStatus.expired):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending or expired invitations can be resent.",
        )

    token = secrets.token_urlsafe(32)
    invitation.token_hash = _hash_token(token)
    invitation.status = InvitationStatus.pending
    invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRE_DAYS)
    await db.commit()
    await db.refresh(invitation)

    bg.add_task(
        send_staff_invitation_email,
        invitation.email,
        invitation.role.value,
        _invite_url(token),
        admin.full_name,
    )
    return invitation


@router.delete("/invitations/{invitation_id}", response_model=Ok)
async def cancel_invitation(invitation_id: int, _admin: AdminUser, db: DbSession) -> Ok:
    invitation = await db.get(Invitation, invitation_id)
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.status != InvitationStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending invitations can be cancelled.",
        )
    invitation.status = InvitationStatus.cancelled
    await db.commit()
    return Ok()


# ── Accept invitation (public — the invitee has no account yet) ────────


@router.get("/invitations/accept", response_model=InvitationAcceptPreview)
async def preview_invitation(token: str, db: DbSession) -> InvitationAcceptPreview:
    await _expire_stale(db)
    invitation = await db.scalar(
        select(Invitation).where(Invitation.token_hash == _hash_token(token))
    )
    if invitation is None or invitation.status != InvitationStatus.pending:
        raise HTTPException(status_code=404, detail="This invitation is invalid or has expired.")
    return InvitationAcceptPreview(email=invitation.email, role=invitation.role)


@router.post("/invitations/accept", response_model=TokenPair)
async def accept_invitation(payload: InvitationAccept, db: DbSession) -> TokenPair:
    await _expire_stale(db)
    invitation = await db.scalar(
        select(Invitation).where(Invitation.token_hash == _hash_token(payload.token))
    )
    if invitation is None or invitation.status != InvitationStatus.pending:
        raise HTTPException(status_code=404, detail="This invitation is invalid or has expired.")

    # Race-condition guard: someone could have registered this email
    # through another path between the invite being sent and accepted.
    existing_user = await db.scalar(select(User).where(User.email == invitation.email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already has an account.",
        )

    user = User(
        email=invitation.email,
        hashed_password=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=invitation.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()  # assign user.id before linking the invitation to it

    invitation.status = InvitationStatus.accepted
    invitation.accepted_at = datetime.now(timezone.utc)
    invitation.accepted_by_id = user.id

    await db.commit()
    await db.refresh(user)

    return TokenPair(
        access_token=create_access_token(user.id), refresh_token=create_refresh_token(user.id)
    )


# ── Staff roster (Admin only — role/active changes reuse admin.py's
#    existing PATCH /admin/users/{id}, which is already Admin-only) ─────


@router.get("/staff", response_model=list[UserPublic])
async def list_staff(_admin: AdminUser, db: DbSession) -> list[User]:
    rows = await db.scalars(
        select(User)
        .where(User.role.in_([UserRole.admin, UserRole.trainer]))
        .order_by(User.created_at.desc())
    )
    return list(rows)


# ── Permission matrix (Admin only to edit; any staff member can read
#    their own effective access via /my-access below) ──────────────────


@router.get("/rules", response_model=list[ModuleAccessRow])
async def get_rules(_admin: AdminUser, db: DbSession) -> list[ModuleAccessRow]:
    rows = await db.scalars(
        select(RolePermission).where(RolePermission.role == UserRole.trainer)
    )
    overrides = {r.module_key: r.can_access for r in rows}
    return [
        ModuleAccessRow(
            module_key=m.key,
            label=m.label,
            admin_access=True,
            trainer_access=overrides.get(m.key, m.default_trainer_access),
        )
        for m in MODULES
    ]


@router.put("/rules/{module_key}", response_model=ModuleAccessRow)
async def update_rule(
    module_key: str, payload: ModuleAccessUpdate, _admin: AdminUser, db: DbSession
) -> ModuleAccessRow:
    if module_key not in MODULE_KEYS:
        raise HTTPException(status_code=404, detail="Unknown module")

    row = await db.scalar(
        select(RolePermission).where(
            RolePermission.role == UserRole.trainer, RolePermission.module_key == module_key
        )
    )
    if row is None:
        row = RolePermission(
            role=UserRole.trainer, module_key=module_key, can_access=payload.can_access
        )
        db.add(row)
    else:
        row.can_access = payload.can_access
    await db.commit()

    return ModuleAccessRow(
        module_key=module_key,
        label=MODULE_LABELS[module_key],
        admin_access=True,
        trainer_access=payload.can_access,
    )


@router.get("/my-access", response_model=MyAccess)
async def my_access(user: StaffUser, db: DbSession) -> MyAccess:
    if user.role == UserRole.admin:
        return MyAccess(modules=list(MODULE_KEYS))

    rows = await db.scalars(
        select(RolePermission).where(RolePermission.role == UserRole.trainer)
    )
    overrides = {r.module_key: r.can_access for r in rows}
    allowed = [
        key for key in MODULE_KEYS if overrides.get(key, DEFAULT_TRAINER_ACCESS[key])
    ]
    return MyAccess(modules=allowed)