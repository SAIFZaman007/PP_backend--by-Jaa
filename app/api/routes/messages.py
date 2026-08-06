"""Direct messaging between clients and trainers."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import and_, func, or_, select, update

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models.message import Message
from app.models.user import User, UserRole
from app.schemas.message import (
    ConversationPartner,
    ConversationPublic,
    MessageCreate,
    MessagePublic,
    OversightConversation,
)

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


# ── Admin oversight — read-only visibility into every client<->coach
#    conversation, not just threads the Admin is personally part of. Never
#    marks anything read and has no reply endpoint of its own, so viewing
#    here can't be mistaken for (or used as) replying on a Trainer's
#    behalf — see the client's explicit "read-only" requirement. ─────────


@router.get("/oversight", response_model=list[OversightConversation])
async def oversight_conversations(_admin: AdminUser, db: DbSession) -> list[OversightConversation]:
    """One row per client with any message history, regardless of which
    Trainer/Admin they were messaging — so a client reassigned between
    Trainers still shows up as a single conversation here instead of
    fragmenting by counterpart the way the per-user inbox above does.
    """
    rows = list(
        await db.scalars(select(Message).order_by(Message.created_at.desc(), Message.id.desc()))
    )
    if not rows:
        return []

    user_ids = {m.sender_id for m in rows} | {m.recipient_id for m in rows}
    users = await db.scalars(select(User).where(User.id.in_(user_ids)))
    user_map = {u.id: u for u in users}

    latest_by_client: dict[int, Message] = {}
    unread_by_client: dict[int, int] = {}
    for m in rows:
        sender = user_map.get(m.sender_id)
        recipient = user_map.get(m.recipient_id)
        if sender is None or recipient is None:
            continue
        client_party = None
        if sender.role == UserRole.client:
            client_party = sender
        elif recipient.role == UserRole.client:
            client_party = recipient
        if client_party is None:
            continue  # not a client<->staff message — shouldn't normally happen
        latest_by_client.setdefault(client_party.id, m)  # rows are newest-first already
        if sender.id == client_party.id and not m.is_read:
            unread_by_client[client_party.id] = unread_by_client.get(client_party.id, 0) + 1

    conversations = []
    for client_id, msg in latest_by_client.items():
        counterpart_id = msg.recipient_id if msg.sender_id == client_id else msg.sender_id
        counterpart = user_map.get(counterpart_id)
        if counterpart is None:
            continue
        conversations.append(
            OversightConversation(
                client=ConversationPartner.model_validate(user_map[client_id]),
                counterpart=ConversationPartner.model_validate(counterpart),
                last_message=MessagePublic.model_validate(msg),
                unread_count=unread_by_client.get(client_id, 0),
            )
        )
    conversations.sort(key=lambda c: c.last_message.created_at, reverse=True)
    return conversations


@router.get("/oversight/{client_id}", response_model=list[MessagePublic])
async def oversight_thread(client_id: int, _admin: AdminUser, db: DbSession) -> list[Message]:
    """Full read-only history for one client, across every counterpart
    they've ever messaged. Deliberately does not mark anything as read —
    unlike thread() above, an Admin viewing this must never make a
    Trainer's unread message look like it's already been seen.
    """
    client_user = await db.get(User, client_id)
    if client_user is None or client_user.role != UserRole.client:
        raise HTTPException(status_code=404, detail="Client not found")
    rows = await db.scalars(
        select(Message)
        .where(or_(Message.sender_id == client_id, Message.recipient_id == client_id))
        .order_by(Message.created_at.asc())
    )
    return list(rows)