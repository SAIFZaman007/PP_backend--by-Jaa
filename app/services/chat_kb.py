"""
Rule-based knowledge base for the AI assistant widget.

Design intent: most visitor questions (services, pricing, "how do I start")
are answered instantly and for free by exact/keyword matching here — no LLM
call, no latency, no cost, and the answer is guaranteed on-brand and correct.
Only genuinely open-ended questions fall through to the LLM (see ai_chat.py).

`pricing` and `services` are intentionally NOT hardcoded strings — they're
built from live DB rows (Plan / Service) in routes/chat.py so the bot can
never say something the trainer hasn't actually configured in the dashboard.
"""
import re

STATIC_KB: dict[str, str] = {
    "services": (
        "Check the 'Train Your Way' section above for the full list of "
        "services and starting prices — everything from a single online "
        "consultation to full 1-on-1 coaching. Tell me your goal and I can "
        "point you to the right one."
    ),
    "get started": (
        "Getting started is simple — scroll to the booking section, fill in "
        "your info, pick a call type, and choose a time. Your first intro "
        "call is completely free, no commitment needed."
    ),
    "start": (
        "To begin: use the booking form on this page to pick a date/time for "
        "your free intro call. We'll confirm within a few hours."
    ),
    "lose fat": (
        "For fat loss, a coaching plan pairs custom training with nutrition "
        "coaching. The core levers: a 300–500 calorie deficit, high protein, "
        "and 3–4 lifting sessions a week to preserve muscle. Try the Calorie "
        "Calculator above for your exact numbers, or book a free call."
    ),
    "fat": (
        "Fat loss comes down to a moderate calorie deficit (300–500/day), "
        "high protein (~0.85g/lb), and resistance training so you keep the "
        "muscle while the scale moves. Use the Calorie Calculator above for "
        "your exact numbers."
    ),
    "build muscle": (
        "Muscle building comes down to progressive overload, a slight "
        "calorie surplus (~200–300/day), and about 0.8–1g of protein per "
        "pound of bodyweight. Try the Workout Generator above for a sample "
        "program."
    ),
    "muscle": (
        "Building muscle takes three things working together: progressive "
        "overload in the gym, a slight calorie surplus, and roughly "
        "0.8–1g of protein per pound of bodyweight. Our coaching builds a "
        "periodized program around all three."
    ),
    "schedule": (
        "Training frequency depends on experience: 3–4 days/week is plenty "
        "for beginners, 4–5 for intermediate, 5–6 for advanced lifters. "
        "Rest days are when the muscle actually gets built, so don't skip "
        "them."
    ),
    "email": (
        "Reach us directly at join@trainpeakphysique.com, or book a free "
        "intro call through the form on this page — we respond within 24 "
        "hours."
    ),
    "campus": (
        "Peak Physique is campus-based — we train clients in person on "
        "campus, virtually over video, or through fully remote coaching. "
        "Location is never a barrier."
    ),
    "results": (
        "Clients have lost 15–20+ lbs, built real strength, and rebuilt "
        "their relationship with food and training. Most people notice a "
        "real difference in 4–6 weeks of consistency."
    ),
    "beginner": (
        "Perfect time to start — beginners usually see the fastest results "
        "since there's no plateau to break through yet. A simple 3-day "
        "program plus basic nutrition coaching is all it takes to get "
        "moving. Book a free intro call whenever you're ready."
    ),
    "nutrition": (
        "Nutrition coaching covers custom macro targets, meal timing, and "
        "weekly check-ins. Use the Macro Planner above to get a starting "
        "point, or book a free call for a fully personalized plan."
    ),
    "macros": (
        "Use the Macro Planner above to get your protein/carb/fat targets "
        "based on your stats and goal."
    ),
    "calories": (
        "Use the Calorie Calculator above — it factors in your stats and "
        "activity level to estimate your maintenance calories (TDEE), then "
        "adjusts for fat loss or muscle gain."
    ),
    "workout": (
        "Try the Workout Generator above for a quick sample plan based on "
        "your goal and schedule. A coach can turn that into a fully "
        "periodized program."
    ),
    "supplement": (
        "The short list that's actually worth it: creatine monohydrate "
        "(5g/day), a protein powder to help hit your daily target, and "
        "vitamin D if you're not getting much sun. Everything else is "
        "optional."
    ),
    "contact": (
        "Best way to reach us: use the booking form on this page, or email "
        "us directly — we respond within 24 hours."
    ),
    "hello": "Hey! What's your main fitness goal right now — I can point you in the right direction.",
    "hi": "Hey! Ask me about training, nutrition, pricing, or how to get started.",
    "thanks": "Anytime! When you're ready, the booking form is right above.",
    "bye": "Talk soon — consistency beats perfection. Come back anytime.",
}

# Regex fallbacks for phrasing that doesn't contain an exact KB key.
PATTERN_KB: list[tuple[re.Pattern, str]] = [
    (re.compile(r"start|begin|sign up|join|enroll|ready"), STATIC_KB["start"]),
    (re.compile(r"weight loss|slim|shred|lean|drop weight|cut"), STATIC_KB["lose fat"]),
    (re.compile(r"bulk|gain|grow|bigger|mass|hypertrophy"), STATIC_KB["build muscle"]),
    (re.compile(r"eat|food|diet|meal"), STATIC_KB["nutrition"]),
    (re.compile(r"program|routine|workout plan"), STATIC_KB["workout"]),
    (re.compile(r"creatine|pre.?workout|protein powder"), STATIC_KB["supplement"]),
    (re.compile(r"^\s*(hi|hey|yo|hello)\b"), STATIC_KB["hi"]),
]


def match_static(message: str) -> str | None:
    m = message.lower().strip()
    for key, answer in STATIC_KB.items():
        if key in m:
            return answer
    for pattern, answer in PATTERN_KB:
        if pattern.search(m):
            return answer
    return None


def wants_pricing(message: str) -> bool:
    m = message.lower()
    return bool(re.search(r"price|pricing|how much|cost|\$|afford|payment|plan[s]?\b", m))


def wants_services(message: str) -> bool:
    m = message.lower()
    return "service" in m or "offer" in m