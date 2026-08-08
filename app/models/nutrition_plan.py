""" 
Nutrition plans — diet guidance + optional macro targets a Trainer sets
for a client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class NutritionPlan(Base, TimestampMixin):
    __tablename__ = "nutrition_plans"

    id: Mapped[int] = mapped_column(primary_key=True)

    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # See ClientNote.trainer_id for why this has no relationship() and why
    # it's SET NULL rather than CASCADE.
    trainer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    title: Mapped[str] = mapped_column(String(120), default="Nutrition Plan", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional daily macro targets — plain nullable integers rather than a
    # separate table; a Trainer fills in only what's relevant to the plan.
    calories_target: Mapped[int | None] = mapped_column(Integer)
    protein_target_g: Mapped[int | None] = mapped_column(Integer)
    carbs_target_g: Mapped[int | None] = mapped_column(Integer)
    fat_target_g: Mapped[int | None] = mapped_column(Integer)

    client: Mapped[User] = relationship(back_populates="nutrition_plans", foreign_keys=[client_id])