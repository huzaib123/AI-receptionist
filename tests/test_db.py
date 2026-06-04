"""
Tests for app/db package.
"""

from datetime import datetime, timedelta
import pytest
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import settings
from app.db.models import Base, Customer, Booking
from app.db import crud


@pytest.fixture(name="db_session")
def fixture_db_session():
    """Create an in-memory SQLite database session for unit tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_customer_crud(db_session):
    """Test creating and retrieving customers."""
    # Create customer
    cust = crud.create_customer(
        db=db_session,
        name="Jane Doe",
        phone="555-9876",
        email="jane@example.com",
    )
    assert cust.id.startswith("CUST-")
    assert cust.name == "Jane Doe"
    assert cust.phone == "555-9876"
    assert cust.email == "jane@example.com"

    # Fetch by name
    fetched_name = crud.get_customer_by_name(db_session, "Jane Doe")
    assert fetched_name is not None
    assert fetched_name.id == cust.id

    # Fetch by phone
    fetched_phone = crud.get_customer_by_phone_or_email(db_session, phone="555-9876")
    assert fetched_phone is not None
    assert fetched_phone.id == cust.id

    # Fetch by email (case-insensitive)
    fetched_email = crud.get_customer_by_phone_or_email(db_session, email="JANE@example.com")
    assert fetched_email is not None
    assert fetched_email.id == cust.id


def test_booking_crud(db_session):
    """Test creating, logging, and updating bookings."""
    # Create customer
    cust = crud.create_customer(db_session, "Alice Cooper")

    # Create booking
    dt_val = datetime.now()
    booking = crud.create_booking(
        db=db_session,
        booking_id="BK-1234",
        customer_id=cust.id,
        service="haircut",
        datetime_val=dt_val,
        status="confirmed",
        source="chat",
        calendar_event_id="cal-123",
        event_link="https://calendar.google.com/evt",
        notes="First time customer",
    )

    assert booking.id == "BK-1234"
    assert booking.customer_id == cust.id
    assert booking.service == "haircut"
    assert booking.status == "confirmed"
    assert booking.notes == "First time customer"

    # Retrieve booking
    fetched = crud.get_booking(db_session, "BK-1234")
    assert fetched is not None
    assert fetched.customer.name == "Alice Cooper"

    # Update notes and customer
    cust2 = crud.create_customer(db_session, "Bob Cooper")
    updated = crud.update_booking_notes_and_customer(
        db=db_session,
        booking_id="BK-1234",
        notes="Changed time",
        customer_id=cust2.id,
    )
    assert updated.notes == "Changed time"
    assert updated.customer_id == cust2.id


def test_get_bookings_today(db_session):
    """Test retrieving today's bookings (timezone-aligned)."""
    cust = crud.create_customer(db_session, "Charlie Brown")

    tz = ZoneInfo(settings.BUSINESS_TIMEZONE)
    local_now = datetime.now(tz)

    # Local today
    dt_today = local_now.replace(hour=14, minute=0, second=0, microsecond=0).replace(tzinfo=None)
    # Tomorrow
    dt_tomorrow = (local_now + timedelta(days=1)).replace(tzinfo=None)

    # Log booking for today
    crud.create_booking(
        db=db_session,
        booking_id="BK-TODAY",
        customer_id=cust.id,
        service="massage",
        datetime_val=dt_today,
    )

    # Log booking for tomorrow
    crud.create_booking(
        db=db_session,
        booking_id="BK-TOMORROW",
        customer_id=cust.id,
        service="haircut",
        datetime_val=dt_tomorrow,
    )

    # Fetch today's bookings
    today_bookings = crud.get_bookings_today(db_session)
    assert len(today_bookings) == 1
    assert today_bookings[0].id == "BK-TODAY"


def test_get_aggregate_stats(db_session):
    """Test computing booking and customer stats."""
    cust1 = crud.create_customer(db_session, "Alice", phone="111")
    cust2 = crud.create_customer(db_session, "Bob", phone="222")

    dt_now = datetime.now()

    # Create bookings with different statuses
    crud.create_booking(
        db=db_session,
        booking_id="BK-A",
        customer_id=cust1.id,
        service="haircut",
        datetime_val=dt_now,
        status="confirmed",
    )
    crud.create_booking(
        db=db_session,
        booking_id="BK-B",
        customer_id=cust2.id,
        service="massage",
        datetime_val=dt_now,
        status="no-show",
    )
    crud.create_booking(
        db=db_session,
        booking_id="BK-C",
        customer_id=cust1.id,
        service="haircut",
        datetime_val=dt_now,
        status="cancelled",
    )

    stats = crud.get_aggregate_stats(db_session)
    assert stats["total_bookings"] == 3
    assert stats["total_customers"] == 2
    assert stats["service_breakdown"] == {"haircut": 2, "massage": 1}
    assert stats["status_breakdown"] == {"confirmed": 1, "no-show": 1, "cancelled": 1}
    assert stats["no_show_count"] == 1
    assert stats["confirmed_count"] == 1
    assert stats["cancelled_count"] == 1
