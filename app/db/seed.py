"""
Single idempotent database seed — pricing plans, services, testimonials,
site copy, staff/admin accounts, and demo clients.

This used to be split across seed.py + seed_content.py; merged into one
file because they always ran together anyway (seed_content() was only
ever called from here) and keeping "what does a fresh DB look like" in
one place is easier to review and keep in sync.

Idempotent throughout: every block checks for existing rows first, so
re-running this after the app has real data is always safe — it only
ever fills in gaps, never overwrites or duplicates.

Always seeds (or confirms) one Head Coach / Super Admin account from the
FIRST_TRAINER_* settings, with role=admin — the account with full access
to the Coach Console. Every login this script is responsible for is
printed to the terminal at the end of a run; see
_print_credentials_summary().

Run with: python -m app.db.seed
"""
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.booking import Booking, BookingStatus
from app.models.content import Service, SiteContent, Testimonial
from app.models.payment import Payment, PaymentStatus, PaymentType
from app.models.plan import BillingInterval, Plan
from app.models.progress import ProgressEntry
from app.models.user import User, UserRole

logger = logging.getLogger("peak.seed")

# ── Pricing plans ────────────────────────────────────────────────────────

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

# ── Services (purchasable — price_cents is what Stripe actually charges) ──

SERVICES = [
    {"icon": "Video", "name": "Online Consultation", "price_label": "$49", "price_suffix": "session",
     "price_cents": 4900,
     "description": "A deep-dive strategy session to assess your goals, current fitness level, lifestyle, and build your roadmap to results.",
     "image_url": "https://res.cloudinary.com/e4hsg7br/image/upload/v1785935720/Picture2_ya5fov.jpg",
     "sort_order": 1},
    {"icon": "Apple", "name": "Nutrition Counseling", "price_label": "$79", "price_suffix": "month",
     "price_cents": 7900,
     "description": "Custom meal planning and macro coaching designed around your campus lifestyle, budget, and body composition goals.",
     "image_url": "https://images.unsplash.com/photo-1490645935967-10de6ba17061?w=800&q=80&auto=format&fit=crop",
     "sort_order": 2},
    {"icon": "Dumbbell", "name": "1-on-1 Coaching", "price_label": "$149", "price_suffix": "starting",
     "price_cents": 14900,
     "description": "Fully custom programming with weekly check-ins and unlimited messaging.",
     "image_url": "https://res.cloudinary.com/e4hsg7br/image/upload/v1785935894/Picture4_xwky02.jpg",
     "sort_order": 3, "is_featured": True},
    {"icon": "Users", "name": "In-Person Training", "price_label": "$99", "price_suffix": "starting",
     "price_cents": 9900,
     "description": "Hands-on sessions focused on form, intensity and real accountability.",
     "image_url": "https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?w=800&q=80&auto=format&fit=crop",
     "sort_order": 4},
    {"icon": "MonitorSmartphone", "name": "Virtual Training", "price_label": "$89", "price_suffix": "starting",
     "price_cents": 8900,
     "description": "Live-guided remote sessions from anywhere, on your schedule.",
     "image_url": "https://res.cloudinary.com/e4hsg7br/image/upload/v1785935826/Picture3_dskqc0.jpg",
     "sort_order": 5},
    {"icon": "Package", "name": "All-in-One Bundle", "price_label": "$199", "price_suffix": "starting",
     "price_cents": 19900,
     "description": "Training, nutrition and check-ins combined for the complete experience.",
     "image_url": "https://res.cloudinary.com/e4hsg7br/image/upload/v1785935935/Picture5_sakljf.jpg",
     "sort_order": 6},
]

# ── Testimonials ─────────────────────────────────────────────────────────

TESTIMONIALS = [
    {"name": "Marcus T.", "role": "Sophomore · Lost 18 lbs", "rating": 5, "result_tag": "Lost 18 lbs",
     "avatar_url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&q=80&auto=format&fit=crop&crop=face",
     "quote": "I lost 18 lbs in my first semester and actually kept it off. Peak Physique built a plan around my dining hall and class schedule — it actually fit my life.",
     "sort_order": 1},
    {"name": "DeShawn R.", "role": "Junior · Gained 22 lbs muscle", "rating": 5, "result_tag": "Gained 22 lbs muscle",
     "avatar_url": "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=100&q=80&auto=format&fit=crop&crop=face",
     "quote": "The virtual training sessions are perfect for my schedule. I went from barely benching 95 lbs to 185 lbs in 4 months. The programming is elite.",
     "sort_order": 2},
    {"name": "Aaliyah S.", "role": "Freshman · Body recomp", "rating": 5, "result_tag": "Body recomp",
     "avatar_url": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=100&q=80&auto=format&fit=crop&crop=face",
     "quote": "The nutrition coaching alone was worth every penny. I finally understand how to eat for my goals. The AI tools on the site helped me figure out where I was going wrong.",
     "sort_order": 3},
]

# ── Site copy (hero / about / focus strip / CTA band / booking panel) ─────

SITE_CONTENT = {
    "hero": {
        "eyebrow": "Now Accepting Campus Clients",
        "heading_line1": "Build Your",
        "heading_line2": "Peak",
        "subheading": "Transform your body, fuel your performance, and unlock your full potential — with personalized training built for college life.",
        "cta_primary": "Start Your Journey",
        "cta_secondary": "Try AI Tools",
        "stats": [
            {"num": "100%", "label": "Personalized Programs"},
            {"num": "5+", "label": "Service Options"},
            {"num": "24/7", "label": "AI Support"},
        ],
    },
    "about": {
        "eyebrow": "Our Mission",
        "heading": "Built To Help You Rise",
        # Blank-line-separated paragraphs — About.jsx splits on "\n\n" so
        # this renders as three distinct paragraphs, same as the demo.
        "body": (
            "Peak Physique was built on a mission — to help students build stronger, "
            "healthier lives while navigating the real challenges of campus life.\n\n"
            "We know what it takes to balance classes, late nights, dining hall food, "
            "and still want to look and feel your best. That's exactly why we built "
            "Peak Physique — training programs that actually work in the real world "
            "of college.\n\n"
            "Our approach combines science-based programming with practical nutrition "
            "strategies to help you build the body and the discipline to match your "
            "ambitions. Every program is NASM-certified, science-driven, and built "
            "with intention."
        ),
        "image_url": "https://res.cloudinary.com/e4hsg7br/image/upload/v1785935465/Picture1_ykeldl.jpg",
        "image_caption": "Science-Based Training",
        "stats": [
            {"num": "100%", "label": "Science-Based"},
            {"num": "1:1", "label": "Personalized"},
            {"num": "0", "label": "Cookie-Cutter Plans"},
        ],
        "tags": ["NASM-Certified", "Nutrition Coaching", "Strength & Conditioning",
                  "Body Recomposition", "Campus-Focused", "Real Results"],
    },
    # Full-bleed 4-photo strip between About and the AI tools section.
    "focus_strip": {
        "items": [
            {"label": "Strength", "alt": "Strength training with weights",
             "image_url": "https://images.unsplash.com/photo-1549060279-7e168fcee0c2?w=600&q=80&auto=format&fit=crop&crop=center"},
            {"label": "Cardio", "alt": "Cardio and endurance training",
             "image_url": "https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=600&q=80&auto=format&fit=crop&crop=center"},
            {"label": "Nutrition", "alt": "Nutrition and healthy eating",
             "image_url": "https://images.unsplash.com/photo-1498837167922-ddd27525d352?w=600&q=80&auto=format&fit=crop&crop=center"},
            {"label": "Recovery", "alt": "Flexibility and recovery training",
             "image_url": "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=600&q=80&auto=format&fit=crop&crop=center"},
        ],
    },
    "cta_bottom": {
        "eyebrow": "The Peak Physique Standard",
        "heading_line1": "Your Goals Are",
        "heading_line2": "Not Optional.",
        "body": "Discipline builds the body. Consistency builds the life. We build both — with programs designed around where you are and engineered to get you where you want to be.",
        "cta_label": "Start Today",
        "background_image_url": "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=1920&q=80&auto=format&fit=crop&crop=center",
    },
    "booking": {
        "eyebrow": "Let's Work",
        "heading_line1": "Ready To Build",
        "heading_line2": "Your Peak?",
        "body": "Fill out the form and I'll reach out within 24 hours to schedule your free intro call. No pressure — just a conversation about your goals.",
        "email": "join@trainpeakphysique.com",
        "location": "On Campus · Virtual Available Nationwide",
        "image_url": "https://images.unsplash.com/photo-1599058917765-a780eda07a3e?w=800&q=80&auto=format&fit=crop&crop=center",
        "quote": "The first step is always the most important. Book your call — everything else follows.",
        "quote_author": "Peak Physique",
    },
}

# ── Staff & demo client accounts ───────────────────────────────────────
# FIRST_TRAINER_* (from settings) always seeds as the primary admin.
# These two are additional accounts purely so a fresh install has more
# than one login to test role-based access with.

EXTRA_STAFF = [
    {
        "email": "coach@trainpeakphysique.com", "password": "c04ch__123!",
        "first_name": "Jordan", "last_name": "Ade", "role": UserRole.trainer,
    },
]

DEMO_CLIENTS = [
    {
        "email": "demo@peakphysique.com", "password": "peak2025",
        "first_name": "Alex", "last_name": "Rivera", "goal": "Build Muscle",
        "weight_lbs": 185, "height": "5'11\"", "phone": "(555) 201-4433",
        "seed_history": True,
    },
    {
        "email": "priya@peakphysique.com", "password": "peak2025",
        "first_name": "Priya", "last_name": "Kapoor", "goal": "Lose Fat",
        "weight_lbs": 148, "height": "5'5\"", "phone": "(555) 340-9981",
        "seed_history": False,
    },
]


async def _seed_plans(db) -> None:
    if await db.scalar(select(Plan).limit(1)) is None:
        for p in PLANS:
            db.add(Plan(**p))
        logger.info("Seeded %d pricing plans", len(PLANS))


async def _seed_content(db) -> None:
    if await db.scalar(select(Service).limit(1)) is None:
        for s in SERVICES:
            db.add(Service(**s))
        logger.info("Seeded %d services", len(SERVICES))

    if await db.scalar(select(Testimonial).limit(1)) is None:
        for t in TESTIMONIALS:
            db.add(Testimonial(**t))
        logger.info("Seeded %d testimonials", len(TESTIMONIALS))

    for key, data in SITE_CONTENT.items():
        existing = await db.scalar(select(SiteContent).where(SiteContent.section_key == key))
        if existing is None:
            db.add(SiteContent(section_key=key, data=data))
            logger.info("Seeded site_content section: %s", key)


async def _seed_staff(db) -> None:
    trainer = await db.scalar(
        select(User).where(User.email == str(settings.FIRST_TRAINER_EMAIL).lower())
    )
    if trainer is None:
        name_parts = settings.FIRST_TRAINER_NAME.split(" ", 1)
        db.add(User(
            email=str(settings.FIRST_TRAINER_EMAIL).lower(),
            hashed_password=hash_password(settings.FIRST_TRAINER_PASSWORD),
            first_name=name_parts[0],
            last_name=name_parts[1] if len(name_parts) > 1 else "",
            role=UserRole.admin,
        ))
        logger.info("Seeded Head Coach / Super Admin: %s", settings.FIRST_TRAINER_EMAIL)

    for staff in EXTRA_STAFF:
        existing = await db.scalar(select(User).where(User.email == staff["email"]))
        if existing is None:
            db.add(User(
                email=staff["email"],
                hashed_password=hash_password(staff["password"]),
                first_name=staff["first_name"],
                last_name=staff["last_name"],
                role=staff["role"],
            ))
            logger.info("Seeded staff account: %s (%s)", staff["email"], staff["role"].value)


async def _seed_demo_clients(db) -> None:
    for c in DEMO_CLIENTS:
        existing = await db.scalar(select(User).where(User.email == c["email"]))
        if existing is not None:
            continue

        client = User(
            email=c["email"],
            hashed_password=hash_password(c["password"]),
            first_name=c["first_name"],
            last_name=c["last_name"],
            role=UserRole.client,
            goal=c["goal"],
            weight_lbs=c["weight_lbs"],
            height=c["height"],
            phone=c["phone"],
        )
        db.add(client)
        await db.flush()  # get client.id

        if not c["seed_history"]:
            logger.info("Seeded demo client: %s", c["email"])
            continue

        today = date.today()
        for i in range(8):
            db.add(ProgressEntry(
                user_id=client.id,
                entry_date=today - timedelta(weeks=(7 - i)),
                weight_lbs=c["weight_lbs"] - i * 1.2,
                body_fat_pct=20 - i * 0.5,
                workouts_completed=3 + (i % 3),
            ))
        db.add(Booking(
            client_id=client.id,
            name=f"{c['first_name']} {c['last_name']}",
            email=c["email"],
            phone=c["phone"],
            goal=c["goal"],
            service="1-on-1 Coaching",
            start_time=datetime.now(timezone.utc) + timedelta(days=2, hours=3),
            status=BookingStatus.confirmed,
        ))
        db.add(Payment(
            user_id=client.id,
            amount_cents=14900,
            description="Peak plan",
            type=PaymentType.subscription,
            status=PaymentStatus.succeeded,
        ))
        logger.info("Seeded demo client with history: %s", c["email"])


def _print_credentials_summary() -> None:
    """Print every seeded login to the terminal so a fresh install (or
    anyone re-running this script) can sign in immediately without
    digging through .env or source. Printed with plain print() rather
    than logger.info() on purpose — this is a one-time interactive
    readout for the person running the command, not something that
    should end up duplicated into structured app logs/log aggregation.

    Runs every time seed() finishes, whether accounts were just created
    or already existed, since "how do I log in" is useful on every run.
    """
    default_admin_password = settings.FIRST_TRAINER_PASSWORD == "Tr@iner__123!"

    lines = [
        "",
        "=" * 62,
        "  PEAK PHYSIQUE — SEEDED LOGIN CREDENTIALS",
        "=" * 62,
        "",
        "  Head Coach / Super Admin  (Coach Console — full access)",
        f"    Name:     {settings.FIRST_TRAINER_NAME}",
        f"    Email:    {settings.FIRST_TRAINER_EMAIL}",
        f"    Password: {settings.FIRST_TRAINER_PASSWORD}",
    ]
    if default_admin_password:
        lines.append(
            "    \u26a0  Still the default password — set FIRST_TRAINER_PASSWORD"
            " in .env before deploying."
        )
    lines.append("")

    if EXTRA_STAFF:
        lines.append("  Additional staff  (Coach Console)")
        for staff in EXTRA_STAFF:
            lines.append(
                f"    {staff['role'].value.capitalize():<9} {staff['email']}  /  {staff['password']}"
            )
        lines.append("")

    if DEMO_CLIENTS:
        lines.append("  Demo clients  (client portal — /login)")
        for c in DEMO_CLIENTS:
            lines.append(f"    {c['email']}  /  {c['password']}")
        lines.append("")

    lines.append("=" * 62)
    lines.append("")
    print("\n".join(lines))


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        await _seed_plans(db)
        await _seed_staff(db)
        await _seed_demo_clients(db)
        await _seed_content(db)
        await db.commit()
    logger.info("Seed complete.")
    _print_credentials_summary()


if __name__ == "__main__":
    from app.core.logging import configure_logging

    configure_logging()
    asyncio.run(seed())