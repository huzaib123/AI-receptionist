"""
Integration tests for the admin FastAPI routes.
"""

from __future__ import annotations

from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db_session
from app.db import crud

import pytest

from app.core.settings import settings

client = TestClient(app)
STRONG_KEY = "test-admin-key-0123456789abcdef"
HEADERS = {"X-Admin-API-Key": STRONG_KEY}


@pytest.fixture(autouse=True)
def strong_admin_key(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", STRONG_KEY)


def test_admin_auth_failed():
    """Test that admin endpoints return 401 when API key is missing and 403 when invalid."""
    # Missing key
    response = client.get("/admin/stats")
    assert response.status_code == 401

    # Invalid key
    response = client.get("/admin/stats", headers={"X-Admin-API-Key": "wrong_key"})
    assert response.status_code == 403


def test_admin_stats_empty():
    """Test the stats endpoint returns default counts when the database is empty."""
    response = client.get("/admin/stats", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["total_bookings"] == 0
    assert data["total_customers"] == 0
    assert data["no_show_count"] == 0
    assert data["total_chat_requests"] == 0
    assert data["tool_error_count"] == 0
    assert data["avg_model_call_latency_ms"] == 0.0


def test_admin_bookings_today_empty():
    """Test that today's bookings is empty when database is empty."""
    response = client.get("/admin/bookings/today", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_admin_stats_and_bookings_populated():
    """Test stats and bookings list with seeded data."""
    # Seed customer and bookings using the patched DB session
    with get_db_session() as db:
        cust = crud.create_customer(db, name="Admin Test Customer", phone="123-456", email="admin@test.com")
        crud.create_booking(
            db=db,
            booking_id="BK-ADMIN-1",
            customer_id=cust.id,
            service="facial",
            datetime_val=datetime.now(),
            status="confirmed",
            notes="Requires extra buffer",
        )
        crud.create_booking(
            db=db,
            booking_id="BK-ADMIN-2",
            customer_id=cust.id,
            service="massage",
            datetime_val=datetime.now(),
            status="no-show",
        )

    # Test /admin/stats
    response_stats = client.get("/admin/stats", headers=HEADERS)
    assert response_stats.status_code == 200
    stats = response_stats.json()
    assert stats["total_bookings"] == 2
    assert stats["total_customers"] == 1
    assert stats["no_show_count"] == 1
    assert stats["service_breakdown"] == {"facial": 1, "massage": 1}

    # Test /admin/bookings/today
    response_bookings = client.get("/admin/bookings/today", headers=HEADERS)
    assert response_bookings.status_code == 200
    bookings = response_bookings.json()
    assert len(bookings) == 2
    assert bookings[0]["id"] == "BK-ADMIN-1"
    assert bookings[0]["customer"]["name"] == "Admin Test Customer"
    assert bookings[0]["service"] == "facial"
