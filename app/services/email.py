"""Async SMTP e-mail service.

Solves the client's original problem: booking submissions were configured to
notify via EmailJS but the connection was never switched on. Here notifications
are sent server-side over SMTP (works with Gmail, Mailgun, SES, SendGrid …).
If SMTP is not configured, e-mails are logged instead of failing the request.
"""
import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger("peak.email")


async def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.warning("SMTP not configured — email to %s NOT sent. Subject: %s", to, subject)
        return False

    msg = EmailMessage()
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text or "This email requires an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_STARTTLS,
        )
        logger.info("Email sent to %s (%s)", to, subject)
        return True
    except Exception as exc:  # never let email break the request flow
        logger.error("Failed sending email to %s: %s", to, exc)
        return False


def _wrap(title: str, body_html: str) -> str:
    return f"""\
<div style="font-family:Inter,Arial,sans-serif;background:#0A0A0A;color:#fff;padding:32px;">
  <div style="max-width:560px;margin:auto;background:#111;border:1px solid #222;border-radius:12px;overflow:hidden;">
    <div style="background:#F5A623;color:#0A0A0A;padding:18px 28px;font-weight:800;letter-spacing:1px;">
      PEAK&nbsp;PHYSIQUE
    </div>
    <div style="padding:28px;">
      <h2 style="margin:0 0 16px;color:#F5A623;">{title}</h2>
      {body_html}
    </div>
    <div style="padding:16px 28px;color:#666;font-size:12px;border-top:1px solid #222;">
      Peak Physique · trainpeakphysique.com
    </div>
  </div>
</div>"""


async def send_welcome_email(to: str, first_name: str) -> None:
    html = _wrap(
        f"Welcome, {first_name}!",
        "<p style='color:#ccc;line-height:1.6'>Your Peak Physique account is ready. "
        "Log in to your client portal to track progress, view plans and message your trainer.</p>",
    )
    await send_email(to, "Welcome to Peak Physique", html)


async def send_booking_notifications(booking) -> None:
    """Notify the trainer and confirm to the client that a booking came in."""
    when = booking.start_time.strftime("%A, %d %B %Y at %I:%M %p")

    trainer_html = _wrap(
        "New booking request",
        f"""<table style="color:#ccc;line-height:1.8">
        <tr><td><b>Name:</b></td><td>{booking.name}</td></tr>
        <tr><td><b>Email:</b></td><td>{booking.email}</td></tr>
        <tr><td><b>Phone:</b></td><td>{booking.phone or '—'}</td></tr>
        <tr><td><b>Service:</b></td><td>{booking.service}</td></tr>
        <tr><td><b>Goal:</b></td><td>{booking.goal or '—'}</td></tr>
        <tr><td><b>When:</b></td><td>{when}</td></tr>
        </table>""",
    )
    await send_email(settings.TRAINER_NOTIFY_EMAIL, f"New booking — {booking.name}", trainer_html)

    client_html = _wrap(
        "We've got your request!",
        f"<p style='color:#ccc;line-height:1.6'>Hi {booking.name}, thanks for booking your "
        f"<b>{booking.service}</b> for <b>{when}</b>. Your trainer will confirm shortly.</p>",
    )
    await send_email(booking.email, "Your Peak Physique booking", client_html)
