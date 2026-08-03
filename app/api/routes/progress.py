"""Client progress log. Clients manage their own; staff can read any client's."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, StaffUser
from app.models.progress import ProgressEntry
from app.models.user import User
from app.schemas.progress import ProgressCreate, ProgressPublic

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/me", response_model=list[ProgressPublic])
async def my_progress(user: CurrentUser, db: DbSession) -> list[ProgressEntry]:
    rows = await db.scalars(
        select(ProgressEntry)
        .where(ProgressEntry.user_id == user.id)
        .order_by(ProgressEntry.entry_date.asc())
    )
    return list(rows)


@router.post("/me", response_model=ProgressPublic, status_code=201)
async def add_progress(
    payload: ProgressCreate, user: CurrentUser, db: DbSession
) -> ProgressEntry:
    entry = ProgressEntry(user_id=user.id, **payload.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/me/{entry_id}", status_code=204)
async def delete_progress(entry_id: int, user: CurrentUser, db: DbSession) -> None:
    entry = await db.get(ProgressEntry, entry_id)
    if entry is None or entry.user_id != user.id:
        raise HTTPException(status_code=404, detail="Entry not found")
    await db.delete(entry)
    await db.commit()


@router.get("/user/{user_id}", response_model=list[ProgressPublic])
async def client_progress(user_id: int, _staff: StaffUser, db: DbSession) -> list[ProgressEntry]:
    """Staff view of a specific client's progress (the cross-device sync)."""
    if await db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    rows = await db.scalars(
        select(ProgressEntry)
        .where(ProgressEntry.user_id == user_id)
        .order_by(ProgressEntry.entry_date.asc())
    )
    return list(rows)
