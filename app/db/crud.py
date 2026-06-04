"""
CRUD operations for Customer and Booking records.
"""

from __future__ import annotations

import uuid
from datetime import datetime, date, time
from typing import List, Optional, Dict, Any
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.settings import settings
from app.db.models import Customer, Booking


# ── Customer CRUD ──────────────────────────────────────────────────────────

def get_customer(db: Session, customer_id: str) -> Optional[Customer]:
    """Retrieve a customer by ID."""
    return db.query(Customer).filter(Customer.id == customer_id).first()


def get_customer_by_phone_or_email(
    db: Session,
    phone: Optional[str] = None,
    email: Optional[Optional[str]] = None,
) -> Optional[Customer]:
    """
    Search for a customer by phone number or email address.
    """
    if phone:
        phone_stripped = phone.strip()
        cust = db.query(Customer).filter(Customer.phone == phone_stripped).first()
        if cust:
            return cust

    if email:
        email_stripped = email.strip().lower()
        cust = db.query(Customer).filter(func.lower(Customer.email) == email_stripped).first()
        if cust:
            return cust

    return None


def get_customer_by_name(db: Session, name: str) -> Optional[Customer]:
    """Retrieve a customer by exact name."""
    return db.query(Customer).filter(Customer.name == name).order_by(Customer.created_at.desc()).first()


def create_customer(
    db: Session,
    name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> Customer:
    """Create a new customer record."""
    if not customer_id:
        customer_id = f"CUST-{uuid.uuid4().hex[:8].upper()}"

    db_customer = Customer(
        id=customer_id,
        name=name.strip(),
        phone=phone.strip() if phone else None,
        email=email.strip() if email else None,
    )
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer


# ── Booking CRUD ───────────────────────────────────────────────────────────

def get_booking(db: Session, booking_id: str) -> Optional[Booking]:
    """Retrieve a booking by ID."""
    return db.query(Booking).filter(Booking.id == booking_id).first()


def create_booking(
    db: Session,
    booking_id: str,
    customer_id: str,
    service: str,
    datetime_val: datetime,
    status: str = "confirmed",
    source: str = "chat",
    calendar_event_id: Optional[str] = None,
    event_link: Optional[str] = None,
    notes: Optional[str] = None,
) -> Booking:
    """Create a new booking record."""
    db_booking = Booking(
        id=booking_id,
        customer_id=customer_id,
        service=service.strip().lower(),
        datetime=datetime_val,
        status=status,
        source=source,
        calendar_event_id=calendar_event_id,
        event_link=event_link,
        notes=notes,
    )
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    return db_booking


def update_booking_notes_and_customer(
    db: Session,
    booking_id: str,
    notes: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> Optional[Booking]:
    """
    Update notes and/or customer ID of an existing booking.
    Useful when db_log_booking binds details back to a booking created in calendar_create_event.
    """
    db_booking = get_booking(db, booking_id)
    if not db_booking:
        return None

    if notes is not None:
        db_booking.notes = notes
    if customer_id is not None:
        db_booking.customer_id = customer_id

    db.commit()
    db.refresh(db_booking)
    return db_booking


def get_bookings_today(db: Session) -> List[Booking]:
    """
    Retrieve today's bookings, timezone-aligned to settings.BUSINESS_TIMEZONE.
    Avoids N+1 query with joinedload of customer details.
    """
    tz = ZoneInfo(settings.BUSINESS_TIMEZONE)
    local_now = datetime.now(tz)
    local_today = local_now.date()

    # Time boundaries of the day
    start_of_day = datetime.combine(local_today, time.min)
    end_of_day = datetime.combine(local_today, time.max)

    return (
        db.query(Booking)
        .options(joinedload(Booking.customer))
        .filter(Booking.datetime >= start_of_day, Booking.datetime <= end_of_day)
        .order_by(Booking.datetime.asc())
        .all()
    )


def get_aggregate_stats(db: Session) -> Dict[str, Any]:
    """
    Aggregate counts:
      - Total bookings
      - Breakdown per service
      - Breakdown per status (e.g. no-shows, confirmed, cancelled)
      - Total unique customers
    """
    total_bookings = db.query(Booking).count()
    total_customers = db.query(Customer).count()

    # Service breakdown
    services_query = db.query(Booking.service, func.count(Booking.id)).group_by(Booking.service).all()
    service_breakdown = {service: count for service, count in services_query}

    # Status breakdown
    status_query = db.query(Booking.status, func.count(Booking.id)).group_by(Booking.status).all()
    status_breakdown = {status: count for status, count in status_query}

    return {
        "total_bookings": total_bookings,
        "total_customers": total_customers,
        "service_breakdown": service_breakdown,
        "status_breakdown": status_breakdown,
        "no_show_count": status_breakdown.get("no-show", 0),
        "confirmed_count": status_breakdown.get("confirmed", 0),
        "cancelled_count": status_breakdown.get("cancelled", 0),
    }
