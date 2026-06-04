"""
Tests for app/integrations/google_calendar.py

Unit tests mock the Google API — they always run.
Integration tests (marked ``@pytest.mark.integration``) call the real API
and require valid credentials.  Run them with:

    pytest tests/test_google_calendar.py -v -m integration
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.integrations.google_calendar import (
    GoogleCalendarClient,
    SERVICE_DURATIONS,
)


# ═══════════════════════════════════════════════════════════════════════════
# Unit tests (mocked — always run)
# ═══════════════════════════════════════════════════════════════════════════


class TestResolveDate:
    """GoogleCalendarClient._resolve_date helper."""

    def test_tomorrow(self):
        result = GoogleCalendarClient._resolve_date("tomorrow")
        expected = (datetime.now() + timedelta(days=1)).date()
        assert result == expected

    def test_today(self):
        result = GoogleCalendarClient._resolve_date("today")
        assert result == datetime.now().date()

    def test_iso_date(self):
        result = GoogleCalendarClient._resolve_date("2025-08-15")
        assert result == datetime(2025, 8, 15).date()

    def test_iso_datetime(self):
        result = GoogleCalendarClient._resolve_date("2025-08-15T14:30:00")
        assert result == datetime(2025, 8, 15).date()

    def test_invalid_falls_back_to_tomorrow(self):
        result = GoogleCalendarClient._resolve_date("next wednesday")
        expected = (datetime.now() + timedelta(days=1)).date()
        assert result == expected


class TestDurationForService:
    """Verify service → duration mapping."""

    def test_known_services(self):
        assert GoogleCalendarClient._duration_for_service("haircut") == 30
        assert GoogleCalendarClient._duration_for_service("Massage") == 60
        assert GoogleCalendarClient._duration_for_service("FACIAL") == 45
        assert GoogleCalendarClient._duration_for_service("consultation") == 15

    def test_unknown_defaults_to_30(self):
        assert GoogleCalendarClient._duration_for_service("unknown_service") == 30


class TestServiceDurations:
    """SERVICE_DURATIONS dict sanity checks."""

    def test_all_positive(self):
        for service, dur in SERVICE_DURATIONS.items():
            assert dur > 0, f"{service} has non-positive duration {dur}"

    def test_expected_services_exist(self):
        assert "haircut" in SERVICE_DURATIONS
        assert "massage" in SERVICE_DURATIONS
        assert "facial" in SERVICE_DURATIONS
        assert "consultation" in SERVICE_DURATIONS


class TestGetFreeSlotsUnit:
    """Test slot calculation logic with a mocked Google API response."""

    @patch("app.integrations.google_calendar.settings")
    def test_empty_calendar_returns_slots(self, mock_settings):
        """An empty calendar should return maximum slots within business hours."""
        mock_settings.GOOGLE_SERVICE_ACCOUNT_FILE = "/fake/creds.json"
        mock_settings.GOOGLE_CALENDAR_ID = "test@group.calendar.google.com"
        mock_settings.BUSINESS_TIMEZONE = "Asia/Karachi"
        mock_settings.BUSINESS_HOURS_START = 9
        mock_settings.BUSINESS_HOURS_END = 17  # 8 hour window
        mock_settings.BUSINESS_DAYS = [0, 1, 2, 3, 4, 5]
        mock_settings.BOOKING_BUFFER_MINUTES = 15

        # Mock Google API
        mock_freebusy_result = {
            "calendars": {
                "test@group.calendar.google.com": {
                    "busy": []  # No existing events
                }
            }
        }

        client = GoogleCalendarClient()
        client._configured = True

        mock_service = MagicMock()
        mock_service.freebusy().query().execute.return_value = mock_freebusy_result
        client._service = mock_service

        # Use a known Monday
        slots = client.get_free_slots("haircut", "2025-06-09")

        assert isinstance(slots, list)
        assert len(slots) > 0

        # Each slot should have the expected keys
        for slot in slots:
            assert "slot_id" in slot
            assert "start_time" in slot
            assert "end_time" in slot
            assert "provider" in slot

    @patch("app.integrations.google_calendar.settings")
    def test_busy_calendar_filters_slots(self, mock_settings):
        """Slots overlapping with busy periods should be excluded."""
        mock_settings.GOOGLE_SERVICE_ACCOUNT_FILE = "/fake/creds.json"
        mock_settings.GOOGLE_CALENDAR_ID = "test@group.calendar.google.com"
        mock_settings.BUSINESS_TIMEZONE = "Asia/Karachi"
        mock_settings.BUSINESS_HOURS_START = 9
        mock_settings.BUSINESS_HOURS_END = 12  # short window
        mock_settings.BUSINESS_DAYS = [0, 1, 2, 3, 4, 5]
        mock_settings.BOOKING_BUFFER_MINUTES = 0  # no buffer for simpler test

        # Block 9:00–10:00
        mock_freebusy_result = {
            "calendars": {
                "test@group.calendar.google.com": {
                    "busy": [
                        {
                            "start": "2025-06-09T09:00:00+05:00",
                            "end": "2025-06-09T10:00:00+05:00",
                        }
                    ]
                }
            }
        }

        client = GoogleCalendarClient()
        client._configured = True

        mock_service = MagicMock()
        mock_service.freebusy().query().execute.return_value = mock_freebusy_result
        client._service = mock_service

        slots = client.get_free_slots("haircut", "2025-06-09")  # 30 min slots

        # The 09:00 slot should be filtered out
        start_times = [s["start_time"] for s in slots]
        assert not any("09:00" in t for t in start_times), (
            "09:00 slot should be blocked"
        )

    @patch("app.integrations.google_calendar.settings")
    def test_non_business_day_returns_empty(self, mock_settings):
        """Requesting a non‑business day should return no slots."""
        mock_settings.GOOGLE_SERVICE_ACCOUNT_FILE = "/fake/creds.json"
        mock_settings.BUSINESS_DAYS = [0, 1, 2, 3, 4]  # Mon–Fri only

        client = GoogleCalendarClient()
        client._configured = True

        # 2025-06-08 is a Sunday (weekday 6)
        slots = client.get_free_slots("haircut", "2025-06-08")
        assert slots == []


class TestCreateBookingEventUnit:
    """Test event creation with a mocked Google API."""

    @patch("app.integrations.google_calendar.settings")
    def test_creates_event_and_returns_confirmation(self, mock_settings):
        mock_settings.GOOGLE_SERVICE_ACCOUNT_FILE = "/fake/creds.json"
        mock_settings.GOOGLE_CALENDAR_ID = "test@group.calendar.google.com"
        mock_settings.BUSINESS_TIMEZONE = "Asia/Karachi"

        mock_event_response = {
            "id": "google_evt_abc123",
            "htmlLink": "https://calendar.google.com/event?eid=abc123",
        }

        client = GoogleCalendarClient()
        client._configured = True

        mock_service = MagicMock()
        mock_service.events().insert().execute.return_value = mock_event_response
        client._service = mock_service

        result = client.create_booking_event(
            customer="Sarah Connor",
            service="haircut",
            start_time="2025-06-10T14:00:00",
        )

        assert result["booking_id"] == "google_evt_abc123"
        assert result["customer"] == "Sarah Connor"
        assert result["service"] == "haircut"
        assert result["status"] == "confirmed"
        assert "calendar.google.com" in result["event_link"]


# ═══════════════════════════════════════════════════════════════════════════
# Integration tests (require real credentials)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestGoogleCalendarIntegration:
    """
    These tests call the real Google Calendar API.

    Run with:
        pytest tests/test_google_calendar.py -v -m integration

    Prerequisites:
        - GOOGLE_SERVICE_ACCOUNT_FILE set to a valid JSON key file
        - GOOGLE_CALENDAR_ID set to a calendar shared with the service account
    """

    @pytest.fixture(autouse=True)
    def _skip_if_not_configured(self):
        from app.integrations.google_calendar import gcal_client

        if not gcal_client.is_configured():
            pytest.skip("Google Calendar not configured — skipping integration tests")

    def test_list_slots_live(self):
        """Query real calendar for slots tomorrow."""
        from app.integrations.google_calendar import gcal_client

        slots = gcal_client.get_free_slots("haircut", "tomorrow")
        assert isinstance(slots, list)
        # We can't assert exact count, but structure should be correct
        for slot in slots:
            assert "slot_id" in slot
            assert "start_time" in slot

    def test_create_and_delete_event_live(self):
        """Create a test event, verify it exists, then clean it up."""
        from app.integrations.google_calendar import gcal_client

        result = gcal_client.create_booking_event(
            customer="Integration Test",
            service="consultation",
            start_time=(datetime.now() + timedelta(days=7)).replace(
                hour=10, minute=0, second=0, microsecond=0
            ).isoformat(),
            duration_minutes=15,
        )

        assert result["booking_id"]
        assert result["status"] == "confirmed"

        # Cleanup: delete the test event
        svc = gcal_client._get_service()
        svc.events().delete(
            calendarId="primary",
            eventId=result["booking_id"],
        ).execute()
