"""Direct messaging between clients and trainers."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import and_, func, or_, select, update

from app.api.deps import CurrentUser, DbSession
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessagePublic

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/thread/{other_id}", response_model=list[MessagePublic])
async def thread(other_id: int, user: CurrentUser, db: DbSession) -> list[Message]:
    if await db.get(User, other_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    # Mark incoming messages from the other user as read.
    await db.execute(
        update(Message)
        .where(
            and_(
                Message.sender_id == other_id,
                Message.recipient_id == user.id,
                Message.is_read.is_(False),
            )
        )
        .values(is_read=True)
    )
    await db.commit()
    rows = await db.scalars(
        select(Message)
        .where(
            or_(
                and_(Message.sender_id == user.id, Message.recipient_id == other_id),
                and_(Message.sender_id == other_id, Message.recipient_id == user.id),
            )
        )
        .order_by(Message.created_at.asc())
    )
    return list(rows)


@router.post("", response_model=MessagePublic, status_code=201)
async def send_message(payload: MessageCreate, user: CurrentUser, db: DbSession) -> Message:
    if await db.get(User, payload.recipient_id) is None:
        raise HTTPException(status_code=404, detail="Recipient not found")
    msg = Message(sender_id=user.id, recipient_id=payload.recipient_id, body=payload.body)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


@router.get("/unread-count")
async def unread_count(user: CurrentUser, db: DbSession) -> dict:
    count = await db.scalar(
        select(func.count())
        .select_from(Message)
        .where(and_(Message.recipient_id == user.id, Message.is_read.is_(False)))
    )
    return {"unread": count or 0}
