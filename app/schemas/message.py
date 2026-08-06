from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class MessageCreate(BaseModel):
    recipient_id: int
    body: str = Field(min_length=1, max_length=5000)


class MessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sender_id: int
    recipient_id: int
    body: str
    is_read: bool
    created_at: datetime


# ── Conversations (inbox view — who's messaged whom) ───────────────────


class ConversationPartner(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    role: UserRole


class ConversationPublic(BaseModel):
    user: ConversationPartner
    last_message: MessagePublic
    unread_count: int


# ── Admin oversight (read-only view across every client<->coach thread) ──


class OversightConversation(BaseModel):
    client: ConversationPartner
    counterpart: ConversationPartner
    last_message: MessagePublic
    unread_count: int