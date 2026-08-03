from pydantic import BaseModel


class Message(BaseModel):
    detail: str


class Ok(BaseModel):
    ok: bool = True
