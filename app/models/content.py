"""
CMS content the trainer manages from the admin dashboard: services offered,
client testimonials, and freeform section copy (hero, about, CTA banner).

Design note: SiteContent uses a single `section_key` + JSON `data` blob
instead of one table per section. A landing page has ~5 text/image blocks
that rarely grow in count but often change in shape (a new headline field,
an extra stat) — JSON avoids an Alembic migration every time copy changes,
while `section_key` still gives each section a stable, typed lookup key on
the frontend (`GET /content/hero`).
"""
from sqlalchemy import JSON, Boolean, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Service(Base, TimestampMixin):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    icon: Mapped[str] = mapped_column(String(40), default="Dumbbell")  # lucide-react icon name
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price_label: Mapped[str] = mapped_column(String(40), nullable=False)  # e.g. "$49"
    price_suffix: Mapped[str] = mapped_column(String(30), default="starting")  # "/ starting", "/ mo"
    description: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Testimonial(Base, TimestampMixin):
    __tablename__ = "testimonials"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(160), default="")  # "Sophomore · Lost 18 lbs"
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(SmallInteger, default=5)
    result_tag: Mapped[str | None] = mapped_column(String(60))  # "Lost 18 lbs"
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class SiteContent(Base, TimestampMixin):
    __tablename__ = "site_content"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_key: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)