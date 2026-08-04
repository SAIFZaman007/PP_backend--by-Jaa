"""Stripe integration (checkout sessions + webhook handling).

Fully functional when STRIPE_SECRET_KEY is set. When it is blank the app still
runs; checkout returns a graceful "stripe disabled" response so local dev and
front-end work do not require live keys.
"""
import logging
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger("peak.stripe")

_stripe = None
if settings.stripe_enabled:
    import stripe as _stripe_sdk

    _stripe_sdk.api_key = settings.STRIPE_SECRET_KEY
    _stripe = _stripe_sdk


def is_enabled() -> bool:
    return _stripe is not None


def stripe_get(obj, key: str, default=None):
    """Safely read a field off anything the Stripe SDK hands back.

    Stripe's Python SDK (v15+) represents API responses with its own
    `StripeObject` — it supports `obj["key"]` and `obj.key`, but it does
    *not* implement dict's `.get()`, so `session.get("metadata")` raises
    `AttributeError: get` instead of returning None (this is what was
    breaking payment confirmation). This helper reads the value the safe
    way for a StripeObject, a plain dict (e.g. webhook payloads some SDK
    versions deserialize differently), or anything missing/None — so call
    sites never need to know or care which shape they were handed.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        return obj[key]
    except (KeyError, TypeError):
        return default


@dataclass
class LineItem:
    name: str
    unit_amount_cents: int
    quantity: int = 1


@dataclass
class CheckoutSession:
    url: str
    session_id: str


def create_checkout_session(
    *,
    items: list[LineItem],
    customer_email: str | None,
    mode: str = "payment",
    success_path: str = "/portal/payments?status=success",
    cancel_path: str = "/portal/payments?status=cancelled",
    metadata: dict | None = None,
) -> CheckoutSession | None:
    """Create a Stripe Checkout session from one or more line items and
    return its URL + session id (or None if disabled). A single-item cart
    is just a list of length one — same code path either way."""
    if _stripe is None:
        logger.warning("Stripe disabled — returning no checkout URL.")
        return None

    session = _stripe.checkout.Session.create(
        mode=mode,
        customer_email=customer_email,
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": li.name},
                    "unit_amount": li.unit_amount_cents,
                },
                "quantity": li.quantity,
            }
            for li in items
        ],
        success_url=f"{settings.FRONTEND_URL}{success_path}&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}{cancel_path}",
        metadata=metadata or {},
    )
    return CheckoutSession(url=session.url, session_id=session.id)


def retrieve_checkout_session(session_id: str):
    """Pull a checkout session's current state straight from Stripe's API.

    This is what lets a payment get marked "succeeded" the instant the
    customer lands back on the success page — it doesn't depend on Stripe
    being able to reach this server with a webhook call, which local dev
    (no `stripe listen` running) and some restrictive networks never
    satisfy. The webhook below stays in place as the durable, async
    source of truth for production; this is the same-second, no-extra-
    setup path that makes the UI correct immediately either way.
    """
    if _stripe is None:
        raise RuntimeError("Stripe is not configured")
    return _stripe.checkout.Session.retrieve(session_id)


def construct_webhook_event(payload: bytes, signature: str):
    """Verify and parse a Stripe webhook. Raises on invalid signature."""
    if _stripe is None:
        raise RuntimeError("Stripe is not configured")
    return _stripe.Webhook.construct_event(
        payload, signature, settings.STRIPE_WEBHOOK_SECRET
    )