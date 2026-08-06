"""Role Matrix — per-role, per-module dashboard access toggles.

Only UserRole.trainer rows are ever meaningfully consulted: admins are
always granted full access in code (see require_module in app/api/deps.py),
so there's intentionally no admin row to toggle off and lock the console
out of itself. `role` is still a real column rather than this table being
hardcoded to "trainer" so that adding another staff role later (e.g. a
future "manager") is a data change, not a schema change.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.user import UserRole


class RolePermission(Base, TimestampMixin):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role", "module_key", name="uq_role_permissions_role_module"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", create_type=False), nullable=False, index=True
    )
    module_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    can_access: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)