"""
Seed data for the CMS tables — mirrors the client-approved demo UI content
(services, testimonials, hero/about copy, focus strip, booking panel) so
the moment this migration runs, the live site matches the demo instead of
showing empty sections or placeholder images.

Import `seed_content()` from db/seed.py and call it alongside the existing
plan/user seed. Idempotent per-table/per-section: skips any Service or
Testimonial insert if the table already has rows, and skips any
SiteContent section whose `section_key` already exists — so re-running it
after a trainer has started editing content won't clobber their changes.

NOTE ON RE-RUNNING: if you've already run the old version of this seed,
`services` and `testimonials` already have rows and this file's fixed
image URLs won't be re-applied automatically (that's intentional — it
never overwrites live edits). Easiest path to pick up the corrected demo
images: edit the affected rows once from the dashboard's Site Content tab
(now with direct image upload), or clear those two tables and re-run
`python -m app.db.seed` for a completely fresh, demo-matching dataset.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Service, SiteContent, Testimonial

logger = logging.getLogger("peak.seed")

SERVICES = [
    {"icon": "Video", "name": "Online Consultation", "price_label": "$49", "price_suffix": "session",
     "description": "A deep-dive strategy session to assess your goals, current fitness level, lifestyle, and build your roadmap to results.",
     "image_url": "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=800&q=80&auto=format&fit=crop",
     "sort_order": 1},
    {"icon": "Apple", "name": "Nutrition Counseling", "price_label": "$79", "price_suffix": "month",
     "description": "Custom meal planning and macro coaching designed around your campus lifestyle, budget, and body composition goals.",
     "image_url": "https://images.unsplash.com/photo-1490645935967-10de6ba17061?w=800&q=80&auto=format&fit=crop",
     "sort_order": 2},
    {"icon": "Dumbbell", "name": "1-on-1 Coaching", "price_label": "$149", "price_suffix": "starting",
     "description": "Fully custom programming with weekly check-ins and unlimited messaging.",
     "image_url": "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=800&q=80&auto=format&fit=crop",
     "sort_order": 3, "is_featured": True},
    {"icon": "Users", "name": "In-Person Training", "price_label": "$99", "price_suffix": "starting",
     "description": "Hands-on sessions focused on form, intensity and real accountability.",
     "image_url": "https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?w=800&q=80&auto=format&fit=crop",
     "sort_order": 4},
    {"icon": "MonitorSmartphone", "name": "Virtual Training", "price_label": "$89", "price_suffix": "starting",
     "description": "Live-guided remote sessions from anywhere, on your schedule.",
     "image_url": "https://images.unsplash.com/photo-1599058945522-28d584b6f0ff?w=800&q=80&auto=format&fit=crop",
     "sort_order": 5},
    {"icon": "Package", "name": "All-in-One Bundle", "price_label": "$199", "price_suffix": "starting",
     "description": "Training, nutrition and check-ins combined for the complete experience.",
     "image_url": "https://images.unsplash.com/photo-1526506118085-60ce8714f8c5?w=800&q=80&auto=format&fit=crop",
     "sort_order": 6},
]

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

SITE_CONTENT = {
    "hero": {
        "eyebrow": "Now Accepting Campus Clients",
        "heading_line1": "Build Your",
        "heading_line2": "Peak Physique",
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
        "image_url": "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?w=800&q=85&auto=format&fit=crop",
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
    # Consumed by frontend/src/sections/FocusStrip.jsx.
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
    # Left-hand panel of the booking section (contact links + photo/quote).
    # Consumed by frontend/src/sections/Booking.jsx.
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


async def seed_content(db: AsyncSession) -> None:
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