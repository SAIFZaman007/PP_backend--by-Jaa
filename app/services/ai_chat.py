"""
LLM fallback for the chat widget.

Only called when the rule-based KB (chat_kb.py) has no match — keeps cost
and latency low, and means the assistant never *needs* a working API key to
answer the 90% of questions that are FAQ-shaped.

Supports two providers, selected by AI_CHAT_PROVIDER:
  - "groq"      → same setup as the client's approved demo (free key from
                  console.groq.com, OpenAI-compatible /chat/completions,
                  llama-3.3-70b-versatile). This is the default.
  - "anthropic" → Claude's native Messages API, if you'd rather use that.

The one architectural difference from the demo: the demo's AI_CONFIG.apiKey
lived in browser JS, so anyone could open dev tools and copy it. Here the
key lives only in this backend's environment and is never sent to or read
by the browser — the frontend only ever talks to our own /chat endpoint.
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("peak.chat")

SYSTEM_PROMPT = (
    "You are the Peak Physique AI assistant — knowledgeable, encouraging, "
    "and concise. Answer in 2-3 short sentences. Stay strictly on topic: "
    "fitness, nutrition, training programs, and this business's services. "
    "If asked something unrelated, gently redirect to fitness/coaching. "
    "Always steer undecided visitors toward booking a free intro call."
)


async def _call_groq(message: str, history: list[dict], context: str) -> str | None:
    """OpenAI-compatible chat completions — same shape the demo's
    callGroqAI() used, just issued from the server instead of the browser."""
    messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nCurrent live pricing/services:\n{context}"},
        *history,
        {"role": "user", "content": message},
    ]
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.AI_CHAT_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.AI_CHAT_MODEL,
                "messages": messages,
                "max_tokens": 220,
                "temperature": 0.7,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        reply = data.get("choices", [{}])[0].get("message", {}).get("content")
        return reply.strip() if reply else None


async def _call_anthropic(message: str, history: list[dict], context: str) -> str | None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.AI_CHAT_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.AI_CHAT_MODEL,
                "max_tokens": 220,
                "system": f"{SYSTEM_PROMPT}\n\nCurrent live pricing/services:\n{context}",
                "messages": [*history, {"role": "user", "content": message}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        return text.strip() or None


_PROVIDERS = {"groq": _call_groq, "anthropic": _call_anthropic}


async def get_ai_reply(message: str, history: list[dict], context: str) -> str | None:
    """Returns a reply string, or None if AI chat is disabled/unavailable/
    misconfigured — callers must have a non-AI fallback ready either way,
    so a bad key or a provider outage degrades gracefully instead of
    breaking the widget."""
    if not settings.AI_CHAT_ENABLED or not settings.AI_CHAT_API_KEY:
        return None

    call = _PROVIDERS.get(settings.AI_CHAT_PROVIDER.lower())
    if call is None:
        logger.warning("Unknown AI_CHAT_PROVIDER %r — falling back to KB.", settings.AI_CHAT_PROVIDER)
        return None

    try:
        return await call(message, history, context)
    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        logger.exception("AI chat provider %s failed", settings.AI_CHAT_PROVIDER)
        return None