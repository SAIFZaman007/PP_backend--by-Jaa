"""Workout plans — training programs a Trainer builds for a client.

Part of the "coaching workspace" (Notes / Nutrition / Workouts) that
replaced the revenue widget on the Trainer dashboard — see
app/api/routes/coaching.py and app/core/rbac.py.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class WorkoutPlan(Base, TimestampMixin):
    __tablename__ = "workout_plans"

    id: Mapped[int] = mapped_column(primary_key=True)

    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # See ClientNote.trainer_id for why this has no relationship() and why
    # it's SET NULL rather than CASCADE.
    trainer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    title: Mapped[str] = mapped_column(String(120), default="Workout Plan", nullable=False)
    # Free-form program body (exercises, sets/reps, weekly split) — kept as
    # a single rich text field rather than a rigid exercise schema so a
    # Trainer can write a plan the way they'd actually hand it to a client.
    content: Mapped[str] = mapped_column(Text, nullable=False)

    client: Mapped[User] = relationship(back_populates="workout_plans", foreign_keys=[client_id])