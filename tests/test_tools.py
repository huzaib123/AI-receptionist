"""
Unit tests for app/agent/tools.py

Validates that every tool:
  1. Has a valid LangChain tool schema (name, description, args_schema).
  2. Returns the expected data structure.
  3. Handles edge cases gracefully.

Note: Calendar tools always fall back to stubs in CI (no Google credentials).
"""

import json

import pytest

from app.agent.tools import (
    ALL_TOOLS,
    calendar_list_slots,
    calendar_create_event,
    db_create_customer,
    db_log_booking,
    faq_lookup,
    predict_no_show,
    Slot,
    BookingConfirmation,
    CustomerRecord,
)


# ═══════════════════════════════════════════════════════════════════════════
# Schema / metadata tests
# ═══════════════════════════════════════════════════════════════════════════


class TestToolSchemas:
    """Every tool must expose a name, description, and JSON‑serialisable args schema."""

    def test_all_tools_have_names(self):
        for tool in ALL_TOOLS:
            assert tool.name, f"Tool {tool} is missing a name"

    def test_all_tools_have_descriptions(self):
        for tool in ALL_TOOLS:
            assert tool.description, f"Tool {tool.name} is missing a description"

    def test_all_tools_have_args_schema(self):
        for tool in ALL_TOOLS:
            schema = tool.args_schema
            assert schema is not None, f"Tool {tool.name} has no args_schema"
            # Schema should be JSON‑serialisable
            json_schema = schema.model_json_schema()
            assert isinstance(json_schema, dict)
            assert "properties" in json_schema

    def test_tool_count(self):
        assert len(ALL_TOOLS) == 6

    def test_tool_names(self):
        names = {t.name for t in ALL_TOOLS}
        expected = {
            "calendar_list_slots",
            "calendar_create_event",
            "db_create_customer",
            "db_log_booking",
            "faq_lookup",
            "predict_no_show",
        }
        assert names == expected


# ═══════════════════════════════════════════════════════════════════════════
# Return‑type / logic tests (stub fallback)
# ═══════════════════════════════════════════════════════════════════════════


class TestCalendarListSlots:
    def test_returns_list_of_slots(self):
        result = calendar_list_slots.invoke(
            {"service": "haircut", "date_pref": "2025-06-10"}
        )
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_slot_structure(self):
        result = calendar_list_slots.invoke(
            {"service": "massage", "date_pref": "2025-06-10"}
        )
        slot = result[0]
        assert "slot_id" in slot
        assert "start_time" in slot
        assert "end_time" in slot
        assert "provider" in slot

    def test_handles_invalid_date(self):
        """Should fall back gracefully when date_pref isn't ISO format."""
        result = calendar_list_slots.invoke(
            {"service": "haircut", "date_pref": "tomorrow"}
        )
        assert isinstance(result, list)
        assert len(result) >= 1


class TestCalendarCreateEvent:
    def test_returns_confirmation(self):
        result = calendar_create_event.invoke(
            {
                "customer": "Jane Doe",
                "service": "haircut",
                "start_time": "2025-06-10T09:00:00",
            }
        )
        assert isinstance(result, dict)
        assert result["status"] == "confirmed"
        assert result["customer"] == "Jane Doe"
        assert result["service"] == "haircut"
        # booking_id comes from either Google (event ID) or stub (BK-xxxx)
        assert result.get("booking_id")


class TestDbCreateCustomer:
    def test_returns_customer_record(self):
        result = db_create_customer.invoke(
            {"name": "John Smith", "phone": "555-1234", "email": "john@example.com"}
        )
        assert isinstance(result, dict)
        assert result["customer_id"].startswith("CUST-")
        assert result["name"] == "John Smith"
        assert result["phone"] == "555-1234"

    def test_optional_fields(self):
        result = db_create_customer.invoke({"name": "Minimal User"})
        assert result["name"] == "Minimal User"
        assert result["phone"] is None
        assert result["email"] is None


class TestDbLogBooking:
    def test_returns_success_string(self):
        # Seed customer so foreign key check passes
        from app.db.session import get_db_session
        from app.db import crud
        with get_db_session() as db:
            crud.create_customer(db, name="Test Customer", customer_id="CUST-TEST")

        result = db_log_booking.invoke(
            {"booking_id": "BK-TEST", "customer_id": "CUST-TEST", "notes": "VIP"}
        )
        assert isinstance(result, str)
        assert "BK-TEST" in result
        assert "CUST-TEST" in result


class TestFaqLookup:
    def test_direct_match(self):
        result = faq_lookup.invoke({"question": "hours"})
        assert "Monday" in result

    def test_substring_match(self):
        result = faq_lookup.invoke({"question": "What are your opening hours?"})
        assert "9 AM" in result

    def test_unknown_question(self):
        result = faq_lookup.invoke({"question": "quantum physics"})
        assert "don't have" in result.lower() or "staff member" in result.lower()

    def test_case_insensitive(self):
        result = faq_lookup.invoke({"question": "PARKING"})
        assert "parking" in result.lower()


class TestPredictNoShow:
    def test_returns_probability(self):
        result = predict_no_show.invoke(
            {"customer_name": "Alice", "service": "haircut", "hour_of_day": 14}
        )
        assert isinstance(result, dict)
        assert 0.0 <= result["no_show_probability"] <= 1.0
        assert result["risk_level"] in ("low", "medium", "high")

    def test_early_slot_bias(self):
        """Early morning slots should generally have higher no‑show risk."""
        probs = []
        for _ in range(50):
            r = predict_no_show.invoke(
                {"customer_name": "X", "service": "test", "hour_of_day": 7}
            )
            probs.append(r["no_show_probability"])
        # With the +0.1 bias, mean should be > 0.15 most of the time
        assert sum(probs) / len(probs) > 0.10


# ═══════════════════════════════════════════════════════════════════════════
# JSON schema serialisation test
# ═══════════════════════════════════════════════════════════════════════════


class TestJsonSerialisation:
    """Ensure tool outputs are JSON‑serialisable (critical for the agent)."""

    def test_slot_serialises(self):
        s = Slot(
            slot_id="s1",
            start_time="2025-06-10T09:00:00",
            end_time="2025-06-10T10:00:00",
            provider="Alice",
        )
        data = json.loads(s.model_dump_json())
        assert data["slot_id"] == "s1"

    def test_booking_confirmation_serialises(self):
        b = BookingConfirmation(
            booking_id="BK-1",
            customer="Jane",
            service="haircut",
            start_time="2025-06-10T09:00:00",
            provider="Bob",
        )
        data = json.loads(b.model_dump_json())
        assert data["status"] == "confirmed"
        # event_link is optional, defaults to None
        assert "event_link" in data

    def test_booking_confirmation_with_link(self):
        b = BookingConfirmation(
            booking_id="evt_123",
            customer="Jane",
            service="haircut",
            start_time="2025-06-10T09:00:00",
            provider="Available",
            event_link="https://calendar.google.com/event?eid=abc",
        )
        data = json.loads(b.model_dump_json())
        assert data["event_link"].startswith("https://")

    def test_customer_record_serialises(self):
        c = CustomerRecord(customer_id="C1", name="Test")
        data = json.loads(c.model_dump_json())
        assert data["customer_id"] == "C1"
