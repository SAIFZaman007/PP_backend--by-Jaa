"""Direct messaging between clients and trainers."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import and_, func, or_, select, update

from app.api.deps import CurrentUser, DbSession
from app.models.message import Message
from app.models.user import User
from app.schemas.message import ConversationPartner, ConversationPublic, MessageCreate, MessagePublic

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/conversations", response_model=list[ConversationPublic])
async def list_conversations(user: CurrentUser, db: DbSession) -> list[ConversationPublic]:
    """Every distinct person `user` has exchanged messages with, each with
    their most recent message and unread count — this is what the
    dashboard's Messages inbox lists on the left. Built entirely on the
    existing Message rows (sender_id/recipient_id), no new tables.
    """
    rows = list(
        await db.scalars(
            select(Message)
            .where(or_(Message.sender_id == user.id, Message.recipient_id == user.id))
            .order_by(Message.created_at.desc(), Message.id.desc())
        )
    )
    if not rows:
        return []

    latest_by_partner: dict[int, Message] = {}
    unread_by_partner: dict[int, int] = {}
    for m in rows:
        other_id = m.recipient_id if m.sender_id == user.id else m.sender_id
        latest_by_partner.setdefault(other_id, m)  # rows are newest-first already
        if m.recipient_id == user.id and not m.is_read:
            unread_by_partner[other_id] = unread_by_partner.get(other_id, 0) + 1

    partners = await db.scalars(select(User).where(User.id.in_(latest_by_partner.keys())))
    partner_map = {p.id: p for p in partners}

    conversations = [
        ConversationPublic(
            user=ConversationPartner.model_validate(partner_map[pid]),
            last_message=MessagePublic.model_validate(msg),
            unread_count=unread_by_partner.get(pid, 0),
        )
        for pid, msg in latest_by_partner.items()
        if pid in partner_map  # skip if the other party's account was deleted
    ]
    conversations.sort(key=lambda c: c.last_message.created_at, reverse=True)
    return conversations


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