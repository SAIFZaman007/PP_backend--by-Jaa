from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.invitation import InvitationStatus
from app.models.user import UserRole

# Invitations are only ever for staff seats — a client never needs one
# (they self-register), and letting an invite target UserRole.client
# would make this a confusing back door into account creation.
_INVITABLE_ROLES = (UserRole.trainer, UserRole.admin)


class InvitationCreate(BaseModel):
    email: EmailStr
    role: UserRole

    @field_validator("role")
    @classmethod
    def _staff_role_only(cls, v: UserRole) -> UserRole:
        if v not in _INVITABLE_ROLES:
            raise ValueError("Invitations can only be sent for the Trainer or Admin role")
        return v


class InvitationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role: UserRole
    status: InvitationStatus
    expires_at: datetime
    accepted_at: datetime | None
    invited_by_id: int | None
    created_at: datetime


class InvitationAcceptPreview(BaseModel):
    email: str
    role: UserRole


class InvitationAccept(BaseModel):
    token: str
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    password: str = Field(min_length=6, max_length=128)


class ModuleAccessRow(BaseModel):
    module_key: str
    label: str
    admin_access: bool = True
    trainer_access: bool


class ModuleAccessUpdate(BaseModel):
    can_access: bool


class MyAccess(BaseModel):
    modules: list[str]