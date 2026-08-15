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
    is_approved: bool = True
    created_at: datetime
    # Only meaningful for role=client — see User.assigned_trainer_id.
    assigned_trainer_id: int | None = None


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
    is_approved: bool | None = None
    # Set to a Trainer's user id to assign a client, or null to unassign
    # (falls back to the primary Admin — see users.get_coach).
    assigned_trainer_id: int | None = None


class AdminClientCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    phone: str | None = Field(default=None, max_length=40)
    goal: str | None = Field(default=None, max_length=120)
    weight_lbs: float | None = None
    height: str | None = Field(default=None, max_length=20)
    assigned_trainer_id: int | None = None


class BulkAssignTrainerRequest(BaseModel):
    """Body for PATCH /admin/clients/assign-trainer — the Clients list's
    bulk-assign action. `assigned_trainer_id` of null unassigns every
    selected client back to the default-coach fallback."""
    client_ids: list[int] = Field(min_length=1, max_length=500)
    assigned_trainer_id: int | None = None