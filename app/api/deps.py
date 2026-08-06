"""Shared FastAPI dependencies: DB session, current user, role guards."""
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import DEFAULT_TRAINER_ACCESS
from app.core.security import decode_token
from app.db.session import get_session
from app.models.role_permission import RolePermission
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(creds.credentials, expected_type="access")
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User | None:
    """Like get_current_user but returns None instead of raising (public endpoints)."""
    if creds is None:
        return None
    try:
        payload = decode_token(creds.credentials, expected_type="access")
        return await db.get(User, int(payload["sub"]))
    except Exception:
        return None


def require_roles(
    *roles: UserRole,
) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Dependency factory that enforces the current user has one of `roles`."""

    async def _guard(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return user

    return _guard


# Ready-made staff guard (trainer or admin)
StaffUser = Annotated[User, Depends(require_roles(UserRole.trainer, UserRole.admin))]
AdminUser = Annotated[User, Depends(require_roles(UserRole.admin))]


def require_module(module_key: str) -> Callable[..., Coroutine[Any, Any, User]]:
    """Dependency factory enforcing Role Matrix access to a dashboard module.

    Admins always pass — there's no admin row in role_permissions to check
    against, by design (see RolePermission), so the Super Admin account can
    never lock itself out of its own console. Trainers are checked against
    their role_permissions row for `module_key`; if no row exists yet
    (e.g. a module was added after this trainer's rules were last seeded),
    DEFAULT_TRAINER_ACCESS is the fallback — this is what makes the
    Payments/Site Content default-deny an actual guarantee rather than
    something that only holds as long as the seed script ran correctly.
    """

    async def _guard(user: StaffUser, db: DbSession) -> User:
        if user.role == UserRole.admin:
            return user
        allowed = await db.scalar(
            select(RolePermission.can_access).where(
                RolePermission.role == user.role,
                RolePermission.module_key == module_key,
            )
        )
        if allowed is None:
            allowed = DEFAULT_TRAINER_ACCESS.get(module_key, False)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this section. Ask an Admin to grant it in Role Matrix.",
            )
        return user

    return _guard


def ensure_client_visible(client: User, staff: User) -> None:
    """Ownership guard for per-client staff endpoints.

    Trainers may only view/manage clients assigned to them (see
    User.assigned_trainer_id); Admins can see every client — this is the
    read-only-for-everyone-else, visible-to-everyone-for-Admin split the
    client asked for. Raises the same 404 used when a client simply
    doesn't exist, so a Trainer probing another Trainer's client ids can't
    distinguish "not assigned to me" from "doesn't exist".
    """
    if staff.role == UserRole.trainer and client.assigned_trainer_id != staff.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")