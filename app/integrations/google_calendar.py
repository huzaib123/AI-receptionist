"""
Google Calendar integration — real API calls for slot discovery and booking.

Uses a **service account** for server‑to‑server authentication.  The target
calendar must be shared with the service account's email address.

If no credentials file is configured the module exposes ``is_configured()``
→ ``False`` so callers can fall back to stubs gracefully.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build, Resource

from app.core.settings import settings

logger = logging.getLogger(__name__)

# ── Service → default duration mapping (minutes) ──────────────────────────
SERVICE_DURATIONS: Dict[str, int] = {
    "haircut": 30,
    "color": 60,
    "colour": 60,
    "massage": 60,
    "facial": 45,
    "consultation": 15,
}

_DEFAULT_DURATION = 30  # fallback if service is unknown

# Google Calendar API scopes
_SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarClient:
    """Thin wrapper around the Google Calendar v3 API."""

    def __init__(self) -> None:
        self._service: Optional[Resource] = None
        self._configured: bool = bool(settings.GOOGLE_SERVICE_ACCOUNT_FILE)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        """Return True if a credentials file has been provided."""
        return self._configured

    def _get_service(self) -> Resource:
        """Lazy‑build the API client (created once, reused)."""
        if self._service is not None:
            return self._service

        creds = Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=_SCOPES,
        )
        self._service = build("calendar", "v3", credentials=creds)
        logger.info(
            "Google Calendar client initialised  calendar_id=%s",
            settings.GOOGLE_CALENDAR_ID,
        )
        return self._service

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_date(date_pref: str) -> date:
        """Parse a user‑friendly date string into a concrete ``date``."""
        lower = date_pref.strip().lower()
        today = date.today()

        if lower in ("today",):
            return today
        if lower in ("tomorrow", "tmrw"):
            return today + timedelta(days=1)

        # Try ISO format
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
            try:
                return datetime.strptime(date_pref.strip()[:10], "%Y-%m-%d").date()
            except ValueError:
                continue

        # Fallback: tomorrow
        logger.warning("Could not parse date '%s', defaulting to tomorrow", date_pref)
        return today + timedelta(days=1)

    @staticmethod
    def _duration_for_service(service: str) -> int:
        """Look up the expected duration in minutes for *service*."""
        return SERVICE_DURATIONS.get(service.lower().strip(), _DEFAULT_DURATION)

    def _make_tz_datetime(self, d: date, hour: int, minute: int = 0) -> str:
        """Build an RFC 3339 datetime string with the business timezone."""
        dt = datetime(d.year, d.month, d.day, hour, minute)
        return dt.isoformat()

    # ── Public API ─────────────────────────────────────────────────────────

    def get_free_slots(
        self,
        service: str,
        date_pref: str,
    ) -> List[Dict[str, Any]]:
        """
        Query the FreeBusy API and return available appointment slots.

        Returns a list of slot dicts compatible with ``Slot.model_dump()``.
        """
        target_date = self._resolve_date(date_pref)
        duration = self._duration_for_service(service)
        tz = settings.BUSINESS_TIMEZONE

        # Only look at working days (check BEFORE hitting the API)
        if target_date.weekday() not in settings.BUSINESS_DAYS:
            logger.info("Date %s is not a business day", target_date)
            return []

        svc = self._get_service()

        # Build time window
        day_start = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            settings.BUSINESS_HOURS_START,
        )
        day_end = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            settings.BUSINESS_HOURS_END,
        )

        # Query FreeBusy
        body = {
            "timeMin": day_start.isoformat() + "Z"
            if tz == "UTC"
            else day_start.isoformat(),
            "timeMax": day_end.isoformat() + "Z"
            if tz == "UTC"
            else day_end.isoformat(),
            "timeZone": tz,
            "items": [{"id": settings.GOOGLE_CALENDAR_ID}],
        }

        logger.info("FreeBusy query: %s → %s", body["timeMin"], body["timeMax"])
        result = svc.freebusy().query(body=body).execute()

        busy_periods = result["calendars"][settings.GOOGLE_CALENDAR_ID].get("busy", [])
        logger.info("Found %d busy periods", len(busy_periods))

        # Parse busy periods into datetime pairs
        busy_blocks: List[tuple[datetime, datetime]] = []
        for period in busy_periods:
            start = datetime.fromisoformat(period["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(period["end"].replace("Z", "+00:00"))
            # Convert to naive for comparison (assuming same tz)
            busy_blocks.append((start.replace(tzinfo=None), end.replace(tzinfo=None)))

        # Generate candidate slots and filter out conflicts
        buffer = timedelta(minutes=settings.BOOKING_BUFFER_MINUTES)
        slot_duration = timedelta(minutes=duration)
        slots: List[Dict[str, Any]] = []

        cursor = day_start
        while cursor + slot_duration <= day_end:
            slot_end = cursor + slot_duration

            # Check for conflicts with busy blocks
            conflict = False
            for busy_start, busy_end in busy_blocks:
                # Add buffer around busy periods
                if cursor < (busy_end + buffer) and slot_end > (busy_start - buffer):
                    conflict = True
                    break

            if not conflict:
                slots.append(
                    {
                        "slot_id": f"slot-{uuid.uuid4().hex[:8]}",
                        "start_time": cursor.isoformat(),
                        "end_time": slot_end.isoformat(),
                        "provider": "Available",
                    }
                )

            # Advance by duration + buffer
            cursor += slot_duration + buffer

        logger.info("Returning %d free slots for %s on %s", len(slots), service, target_date)
        return slots

    def create_booking_event(
        self,
        customer: str,
        service: str,
        start_time: str,
        duration_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Insert a calendar event and return a booking confirmation dict.

        The returned dict includes ``event_id`` and ``event_link`` from the
        real Google Calendar event.
        """
        svc = self._get_service()
        duration = duration_minutes or self._duration_for_service(service)
        tz = settings.BUSINESS_TIMEZONE

        # Parse start time
        try:
            start_dt = datetime.fromisoformat(start_time)
        except ValueError:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

        # Strip tzinfo for clean isoformat with timezone spec
        if start_dt.tzinfo:
            start_dt = start_dt.replace(tzinfo=None)

        end_dt = start_dt + timedelta(minutes=duration)

        event_body = {
            "summary": f"{service.title()} — {customer}",
            "description": (
                f"Service: {service.title()}\n"
                f"Customer: {customer}\n"
                f"Duration: {duration} min\n"
                f"Booked via AI Receptionist"
            ),
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": tz,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": tz,
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 30},
                ],
            },
        }

        logger.info(
            "Creating event: %s for %s at %s (%d min)",
            service,
            customer,
            start_dt.isoformat(),
            duration,
        )
        event = (
            svc.events()
            .insert(calendarId=settings.GOOGLE_CALENDAR_ID, body=event_body)
            .execute()
        )

        event_id = event.get("id", "")
        event_link = event.get("htmlLink", "")

        logger.info("Event created: id=%s link=%s", event_id, event_link)

        return {
            "booking_id": event_id,
            "customer": customer,
            "service": service,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "provider": "Available",
            "status": "confirmed",
            "event_link": event_link,
        }

    def delete_booking_event(self, event_id: str) -> None:
        """
        Delete/cancel a booking event on Google Calendar.
        Used for rollback when database persistence fails.
        """
        if not self.is_configured():
            logger.info("Google Calendar not configured; skipping event deletion for id=%s", event_id)
            return

        svc = self._get_service()
        try:
            logger.info("Deleting event from Google Calendar: id=%s", event_id)
            svc.events().delete(
                calendarId=settings.GOOGLE_CALENDAR_ID,
                eventId=event_id,
            ).execute()
            logger.info("Event deleted successfully: id=%s", event_id)
        except Exception as exc:
            logger.exception("Failed to delete Google Calendar event id=%s", event_id)
            raise exc


# ── Module‑level singleton ─────────────────────────────────────────────────
gcal_client = GoogleCalendarClient()
