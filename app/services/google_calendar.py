"""Google Calendar sync for bookings.

Uses a Google *service account* so the server can create events without an
interactive OAuth flow. Enable by setting GOOGLE_CALENDAR_ENABLED=true and
pointing GOOGLE_SERVICE_ACCOUNT_FILE at the key JSON. Disabled by default so
the app runs with no Google credentials.
"""
import logging
from datetime import timedelta

from app.core.config import settings

logger = logging.getLogger("peak.gcal")

_service = None


def _get_service():
    global _service
    if _service is not None:
        return _service
    if not settings.GOOGLE_CALENDAR_ENABLED:
        return None
    try:
        import json
        import os
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = None
        if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            try:
                info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
                creds = service_account.Credentials.from_service_account_info(
                    info,
                    scopes=["https://www.googleapis.com/auth/calendar"],
                )
            except Exception:
                import base64
                info = json.loads(base64.b64decode(settings.GOOGLE_SERVICE_ACCOUNT_JSON).decode("utf-8"))
                creds = service_account.Credentials.from_service_account_info(
                    info,
                    scopes=["https://www.googleapis.com/auth/calendar"],
                )
        elif os.path.exists(settings.GOOGLE_SERVICE_ACCOUNT_FILE):
            creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_SERVICE_ACCOUNT_FILE,
                scopes=["https://www.googleapis.com/auth/calendar"],
            )

        if not creds:
            logger.error("No valid Google Service Account credentials found.")
            return None

        _service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return _service
    except Exception as exc:
        logger.error("Could not initialise Google Calendar: %s", exc)
        return None


def create_event(booking) -> str | None:
    """Create a calendar event for a booking; returns the event id or None."""
    if booking.start_time is None:
        # Awaiting scheduling — nothing to put on the calendar yet. Once the
        # coach assigns a real time from the dashboard, bookings.update_booking
        # calls create_event again via its "newly_scheduled" background task.
        logger.info("Booking %s has no start_time yet — skipping calendar sync", booking.id)
        return None
    service = _get_service()
    if service is None:
        logger.info("Google Calendar disabled — skipping event for booking %s", booking.id)
        return None
    try:
        end = booking.start_time + timedelta(minutes=45)
        event = {
            "summary": f"{booking.service} — {booking.name}",
            "description": (
                f"Client: {booking.name}\n"
                f"Email: {booking.email}\n"
                f"Phone: {booking.phone or 'n/a'}\n"
                f"Goal: {booking.goal or 'n/a'}"
            ),
            "start": {"dateTime": booking.start_time.isoformat()},
            "end": {"dateTime": end.isoformat()},
            # NOTE: Service accounts cannot invite attendees without
            # Domain-Wide Delegation of Authority (DWD). Attendees are
            # intentionally omitted here to avoid a 403 error. The client
            # is notified separately via the SMTP email service.
        }
        created = (
            service.events()
            .insert(
                calendarId=settings.GOOGLE_CALENDAR_ID,
                body=event,
                sendUpdates="none",
            )
            .execute()
        )
        return created.get("id")
    except Exception as exc:
        logger.error("Failed creating calendar event: %s", exc)
        return None


def delete_event(event_id: str) -> None:
    service = _get_service()
    if service is None or not event_id:
        return
    try:
        service.events().delete(
            calendarId=settings.GOOGLE_CALENDAR_ID,
            eventId=event_id,
            sendUpdates="all",
        ).execute()
    except Exception as exc:
        logger.error("Failed deleting calendar event %s: %s", event_id, exc)