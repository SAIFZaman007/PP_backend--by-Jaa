from datetime import datetime

from pydantic import BaseModel, Field


class ClientNoteCreate(BaseModel):
    client_id: int
    content: str = Field(min_length=1, max_length=10_000)


class ClientNoteUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)


class ClientNotePublic(BaseModel):
    id: int
    client_id: int
    trainer_id: int | None
    trainer_name: str
    content: str
    created_at: datetime
    updated_at: datetime