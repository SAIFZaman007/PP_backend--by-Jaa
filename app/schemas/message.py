from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
