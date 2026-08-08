"""User model — clients, trainers and admins share one table with a role."""
from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.client_note import ClientNote
    from app.models.message import Message
    from app.models.nutrition_plan import NutritionPlan
    from app.models.payment import Payment
    from app.models.progress import ProgressEntry
    from app.models.workout_plan import WorkoutPlan


class UserRole(str, enum.Enum):
    client = "client"
    trainer = "trainer"
    admin = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.client, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Fitness profile
    goal: Mapped[str | None] = mapped_column(String(120))
    weight_lbs: Mapped[float | None] = mapped_column(Float)
    height: Mapped[str | None] = mapped_column(String(20))

    # Billing
    stripe_customer_id: Mapped[str | None] = mapped_column(String(120))

    # Only ever meaningful for role=client rows — which Trainer this
    # client is assigned to, set by an Admin from the dashboard (Clients
    # list or Client Detail). Drives who the client's "Message Coach"
    # resolves to (see users.get_coach) and which clients a Trainer sees
    # in their own Clients list (see admin.list_clients). Left null for
    # staff rows and for clients nobody's assigned yet — those clients
    # still fall back to the primary Admin, so nobody is left unreachable.
    # No SQLAlchemy relationship() is defined for this on purpose: every
    # place that needs the trainer's name already has (or separately
    # fetches) the staff roster, so a plain scalar FK avoids any risk of
    # an unawaited lazy-load in this async codebase.
    assigned_trainer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    # Relationships
    bookings: Mapped[list[Booking]] = relationship(
        back_populates="client", cascade="all, delete-orphan", foreign_keys="Booking.client_id"
    )
    progress_entries: Mapped[list[ProgressEntry]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sent_messages: Mapped[list[Message]] = relationship(
        back_populates="sender",
        foreign_keys="Message.sender_id",
        cascade="all, delete-orphan",
    )
    # Coaching workspace (Notes / Nutrition / Workouts) — only ever
    # meaningful for role=client rows, mirroring progress_entries above.
    # Deleting a client cascades to their coaching records; deleting the
    # Trainer who wrote them does not (see ClientNote.trainer_id etc.).
    client_notes: Mapped[list[ClientNote]] = relationship(
        back_populates="client",
        foreign_keys="ClientNote.client_id",
        cascade="all, delete-orphan",
    )
    nutrition_plans: Mapped[list[NutritionPlan]] = relationship(
        back_populates="client",
        foreign_keys="NutritionPlan.client_id",
        cascade="all, delete-orphan",
    )
    workout_plans: Mapped[list[WorkoutPlan]] = relationship(
        back_populates="client",
        foreign_keys="WorkoutPlan.client_id",
        cascade="all, delete-orphan",
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_staff(self) -> bool:
        return self.role in (UserRole.trainer, UserRole.admin)