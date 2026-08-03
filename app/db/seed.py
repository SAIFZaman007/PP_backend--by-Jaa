"""Idempotent database seed: pricing plans, first trainer, and a demo client."""
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.db.seed_content import seed_content
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus, PaymentType
from app.models.plan import BillingInterval, Plan
from app.models.progress import ProgressEntry
from app.models.user import User, UserRole

logger = logging.getLogger("peak.seed")

PLANS = [
    {
        # One-time, not recurring: it's a single $49 strategy session, not
        # a subscription — billing this monthly would silently keep
        # charging clients for a consult they only ever had once.
        "slug": "starter", "name": "Starter", "tagline": "One-time consultation",
        "price_cents": 4900, "interval": BillingInterval.one_time, "sort_order": 1,
        "features": ["60-min strategy session", "Goal assessment & roadmap",
                     "Sample workout template", "Nutrition guidelines", "7-day support"],
    },
    {
        "slug": "peak", "name": "Peak", "tagline": "Our most popular plan",
        "price_cents": 14900, "interval": BillingInterval.month, "sort_order": 2,
        "is_featured": True,
        "features": ["Full 1-on-1 coaching", "Custom workout program",
                     "Nutrition coaching", "Weekly check-ins", "Unlimited messaging",
                     "Progress tracking"],
    },
    {
        "slug": "elite", "name": "Elite", "tagline": "The complete experience",
        "price_cents": 19900, "interval": BillingInterval.month, "sort_order": 3,
        "features": ["Everything in Peak", "4 live training sessions/mo",
                     "In-person OR virtual", "Priority response (<1hr)",
                     "Supplement guidance", "Monthly body analysis",
                     "Campus lifestyle planning"],
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        # --- Plans ---
        existing = await db.scalar(select(Plan).limit(1))
        if existing is None:
            for p in PLANS:
                db.add(Plan(**p))
            logger.info("Seeded %d pricing plans", len(PLANS))

        # --- First trainer / admin ---
        trainer = await db.scalar(
            select(User).where(User.email == str(settings.FIRST_TRAINER_EMAIL).lower())
        )
        if trainer is None:
            name_parts = settings.FIRST_TRAINER_NAME.split(" ", 1)
            trainer = User(
                email=str(settings.FIRST_TRAINER_EMAIL).lower(),
                hashed_password=hash_password(settings.FIRST_TRAINER_PASSWORD),
                first_name=name_parts[0],
                last_name=name_parts[1] if len(name_parts) > 1 else "",
                role=UserRole.admin,
            )
            db.add(trainer)
            logger.info("Seeded first trainer/admin: %s", settings.FIRST_TRAINER_EMAIL)

        # --- Demo client with sample data (handy for first-run demos) ---
        demo = await db.scalar(select(User).where(User.email == "demo@peakphysique.com"))
        if demo is None:
            demo = User(
                email="demo@peakphysique.com",
                hashed_password=hash_password("peak2025"),
                first_name="Alex",
                last_name="Rivera",
                role=UserRole.client,
                goal="Build Muscle",
                weight_lbs=185,
                height="5'11\"",
                phone="(555) 201-4433",
            )
            db.add(demo)
            await db.flush()  # get demo.id

            today = date.today()
            for i in range(8):
                db.add(
                    ProgressEntry(
                        user_id=demo.id,
                        entry_date=today - timedelta(weeks=(7 - i)),
                        weight_lbs=185 - i * 1.2,
                        body_fat_pct=20 - i * 0.5,
                        workouts_completed=3 + (i % 3),
                    )
                )
            db.add(
                Booking(
                    client_id=demo.id,
                    name="Alex Rivera",
                    email="demo@peakphysique.com",
                    phone="(555) 201-4433",
                    goal="Build Muscle",
                    service="1-on-1 Coaching",
                    start_time=datetime.now(timezone.utc) + timedelta(days=2, hours=3),
                    status=BookingStatus.confirmed,
                )
            )
            db.add(
                Payment(
                    user_id=demo.id,
                    amount_cents=14900,
                    description="Peak plan",
                    type=PaymentType.subscription,
                    status=PaymentStatus.succeeded,
                )
            )
            logger.info("Seeded demo client (demo@peakphysique.com / peak2025)")
        await seed_content(db)
        await db.commit()
    logger.info("Seed complete.")


if __name__ == "__main__":
    from app.core.logging import configure_logging

    configure_logging()
    asyncio.run(seed())