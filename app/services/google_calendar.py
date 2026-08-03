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
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        _service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return _service
    except Exception as exc:
        logger.error("Could not initialise Google Calendar: %s", exc)
        return None


def create_event(booking) -> str | None:
    """Create a calendar event for a booking; returns the event id or None."""
    service = _get_service()
    if service is None:
        logger.info("Google Calendar disabled — skipping event for booking %s", booking.id)
        return None
    try:
        end = booking.start_time + timedelta(minutes=45)
        event = {
            "summary": f"{booking.service} — {booking.name}",
            "description": f"Goal: {booking.goal or 'n/a'}\nPhone: {booking.phone or 'n/a'}\n"
            f"Email: {booking.email}",
            "start": {"dateTime": booking.start_time.isoformat()},
            "end": {"dateTime": end.isoformat()},
            "attendees": [{"email": booking.email}],
        }
        created = (
            service.events()
            .insert(calendarId=settings.GOOGLE_CALENDAR_ID, body=event, sendUpdates="all")
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
            calendarId=settings.GOOGLE_CALENDAR_ID, eventId=event_id
        ).execute()
    except Exception as exc:
        logger.error("Failed deleting calendar event %s: %s", event_id, exc)
