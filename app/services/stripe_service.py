"""Stripe integration (checkout sessions + webhook handling).

Fully functional when STRIPE_SECRET_KEY is set. When it is blank the app still
runs; checkout returns a graceful "stripe disabled" response so local dev and
front-end work do not require live keys.
"""
import logging

from app.core.config import settings

logger = logging.getLogger("peak.stripe")

_stripe = None
if settings.stripe_enabled:
    import stripe as _stripe_sdk

    _stripe_sdk.api_key = settings.STRIPE_SECRET_KEY
    _stripe = _stripe_sdk


def is_enabled() -> bool:
    return _stripe is not None


def create_checkout_session(
    *,
    amount_cents: int,
    description: str,
    customer_email: str | None,
    mode: str = "payment",
    success_path: str = "/portal/payments?status=success",
    cancel_path: str = "/portal/payments?status=cancelled",
    metadata: dict | None = None,
) -> str | None:
    """Create a Stripe Checkout session and return its URL (or None if disabled)."""
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
                    "product_data": {"name": description},
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }
        ],
        success_url=f"{settings.FRONTEND_URL}{success_path}&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}{cancel_path}",
        metadata=metadata or {},
    )
    return session.url


def construct_webhook_event(payload: bytes, signature: str):
    """Verify and parse a Stripe webhook. Raises on invalid signature."""
    if _stripe is None:
        raise RuntimeError("Stripe is not configured")
    return _stripe.Webhook.construct_event(
        payload, signature, settings.STRIPE_WEBHOOK_SECRET
    )
