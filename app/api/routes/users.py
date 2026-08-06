"""Current-user profile endpoints."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.user import User, UserRole
from app.schemas.user import UserPublic, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/coach", response_model=UserPublic)
async def get_coach(_user: CurrentUser, db: DbSession) -> User:
    """Return the coach this client should message: their assigned
    Trainer if one's been set (see User.assigned_trainer_id) and is still
    active, otherwise the same admin-preferred fallback as before — so an
    unassigned client is never left with no one to message.
    """
    if _user.assigned_trainer_id is not None:
        assigned = await db.get(User, _user.assigned_trainer_id)
        if assigned is not None and assigned.is_active:
            return assigned

    coach = await db.scalar(
        select(User)
        .where(User.role.in_([UserRole.admin, UserRole.trainer]), User.is_active.is_(True))
        .order_by((User.role == UserRole.admin).desc(), User.id)
    )
    if coach is None:
        raise HTTPException(status_code=404, detail="No coach available yet")
    return coach


@router.get("/me", response_model=UserPublic)
async def get_me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserPublic)
async def update_me(payload: UserUpdate, user: CurrentUser, db: DbSession) -> User:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user