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


async def send_staff_invitation_email(
    to: str, role: str, invite_url: str, invited_by_name: str | None = None
) -> None:
    """Sent when an Admin invites a new Trainer/Admin from the Role Matrix
    page. The link carries a one-time token (see Invitation.token_hash) —
    accepting it is what actually creates the account, so this email never
    contains a password.
    """
    role_label = role.capitalize()
    inviter = f" by {invited_by_name}" if invited_by_name else ""
    html = _wrap(
        "You're invited to Peak Physique",
        f"<p style='color:#ccc;line-height:1.6'>You've been invited{inviter} to join the "
        f"Peak Physique Coach Console as <b>{role_label}</b>.</p>"
        f"<p style='margin-top:20px'><a href='{invite_url}' "
        "style='background:#F5A623;color:#0A0A0A;padding:12px 24px;border-radius:4px;"
        "text-decoration:none;font-weight:700;display:inline-block'>Accept Invitation</a></p>"
        f"<p style='color:#666;font-size:12px;margin-top:20px;line-height:1.6'>"
        f"This link expires in 7 days. If the button doesn't work, copy and paste this "
        f"link into your browser:<br>{invite_url}</p>",
    )
    await send_email(to, "You're invited to join Peak Physique", html)


async def send_welcome_email(to: str, first_name: str) -> None:
    html = _wrap(
        f"Welcome, {first_name}!",
        "<p style='color:#ccc;line-height:1.6'>Your Peak Physique account is ready. "
        "Log in to your client portal to track progress, view plans and message your trainer.</p>",
    )
    await send_email(to, "Welcome to Peak Physique", html)


async def send_booking_notifications(booking) -> None:
    """Notify the trainer and confirm to the client that a booking came in.

    `booking.start_time` is nullable (see Booking.start_time) — the public
    booking form no longer collects a preferred date/time at all, so this
    almost always fires with no time yet; the coach picks the real slot
    from the dashboard, which is what send_schedule_confirmation below is
    for.
    """
    when = (
        booking.start_time.strftime("%A, %d %B %Y at %I:%M %p")
        if booking.start_time
        else "a time to be confirmed"
    )

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
        f"<p style='color:#ccc;line-height:1.6'>Hi {booking.name}, thanks for requesting your "
        f"<b>{booking.service}</b>. We'll reach out shortly to lock in {when} on the calendar.</p>",
    )
    await send_email(booking.email, "Your Peak Physique booking request", client_html)


async def send_schedule_confirmation(booking) -> None:
    """Tells the client their session now has a confirmed time.

    The counterpart to send_booking_notifications above, but for a booking
    that already existed and just moved from "awaiting scheduling" to a
    real slot (see Booking.start_time) — the normal path now that every
    public booking starts with no time and the coach assigns one from the
    dashboard's Bookings page.
    """
    when = booking.start_time.strftime("%A, %d %B %Y at %I:%M %p")
    html = _wrap(
        "Your session is confirmed",
        f"<p style='color:#ccc;line-height:1.6'>Hi {booking.name}, your <b>{booking.service}</b> "
        f"is confirmed for <b>{when}</b>. We'll see you then!</p>",
    )
    await send_email(booking.email, "Your Peak Physique session is confirmed", html)