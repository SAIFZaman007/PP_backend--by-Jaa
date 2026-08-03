"""Declarative base + a shared timestamp mixin.

NOTE: model modules import `Base` from here, so this file must NOT import the
models (that would create a circular import). To ensure every model is
registered on `Base.metadata` before create_all()/Alembic run, import the
`app.models` package (its __init__ imports all models). See app/db/init_db.py.
"""
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Registry root for all ORM models."""


class TimestampMixin:
    """Adds created_at / updated_at to any model that inherits it."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
