"""Trainer coaching notes — a running log a Trainer keeps on a client.

Part of the "coaching workspace" (Notes / Nutrition / Workouts) that
replaced the revenue widget on the Trainer dashboard — see
app/api/routes/coaching.py and app/core/rbac.py.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ClientNote(Base, TimestampMixin):
    __tablename__ = "client_notes"

    id: Mapped[int] = mapped_column(primary_key=True)

    # The client this note is about. Cascades on delete like the client's
    # other owned records (progress entries, bookings) — a deleted client
    # account takes its coaching history with it.
    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # The staff member who wrote this entry. Deliberately a plain scalar FK
    # with no relationship() defined — same reasoning as User.assigned_trainer_id:
    # every place that needs the author's name already has (or separately
    # fetches) the staff roster, so this avoids any risk of an unawaited
    # lazy-load in this async codebase. SET NULL (not CASCADE) so a note
    # outlives the staff account that wrote it — reassigning or offboarding
    # a Trainer must never silently delete a client's coaching history.
    trainer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    client: Mapped[User] = relationship(back_populates="client_notes", foreign_keys=[client_id])