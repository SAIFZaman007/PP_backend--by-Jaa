from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str = ""
    phone: str | None = None
    goal: str | None = None
    weight_lbs: float | None = None
    height: str | None = None


class UserPublic(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=40)
    goal: str | None = Field(default=None, max_length=120)
    weight_lbs: float | None = None
    height: str | None = Field(default=None, max_length=20)


class AdminUserUpdate(UserUpdate):
    role: UserRole | None = None
    is_active: bool | None = None
