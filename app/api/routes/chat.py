"""Public AI-assistant chat widget endpoint."""
from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import DbSession
from app.core.rate_limit import limiter
from app.models.plan import Plan
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai_chat import get_ai_reply
from app.services.chat_kb import match_static, wants_pricing

router = APIRouter(prefix="/chat", tags=["chat"])

FALLBACK_REPLY = (
    "Great question! For a specific answer tailored to your goals, book a "
    "free intro call and we'll walk through it together — no pressure."
)


async def _pricing_context(db: DbSession) -> str:
    """Live plan data, used both to answer pricing questions directly and
    as grounding context for the LLM fallback so it never quotes stale
    numbers."""
    plans = await db.scalars(
        select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.sort_order)
    )
    lines = []
    for p in plans:
        price = f"${p.price_cents / 100:.0f}"
        unit = "one-time" if p.interval.value == "one_time" else "/mo"
        lines.append(f"{p.name}: {price} {unit}" + (" (most popular)" if p.is_featured else ""))
    return "; ".join(lines) if lines else "Pricing is available on the Pricing section of this page."


@router.post("", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest, db: DbSession) -> ChatResponse:
    context = await _pricing_context(db)

    if wants_pricing(body.message):
        return ChatResponse(reply=f"Current pricing — {context}. No contracts, cancel anytime.", source="kb")

    static = match_static(body.message)
    if static:
        return ChatResponse(reply=static, source="kb")

    history = [{"role": t.role, "content": t.content} for t in body.history]
    ai_reply = await get_ai_reply(body.message, history, context)
    if ai_reply:
        return ChatResponse(reply=ai_reply, source="ai")

    return ChatResponse(reply=FALLBACK_REPLY, source="fallback")