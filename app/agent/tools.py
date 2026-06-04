"""
Receptionist tool definitions.

Calendar tools use **real Google Calendar** when credentials are configured,
and fall back to **stub data** otherwise — so the app always works.

Other tools (FAQ, CRM, no‑show prediction) remain stubbed for now.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.integrations.google_calendar import gcal_client
from app.db.session import get_db_session
from app.db import crud
from app.ml.no_show_model import predict_no_show_prob

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# Pydantic schemas for tool I/O
# ═══════════════════════════════════════════════════════════════════════════


class Slot(BaseModel):
    """A single available time‑slot."""

    slot_id: str = Field(..., description="Unique slot identifier.")
    start_time: str = Field(..., description="ISO‑8601 start time.")
    end_time: str = Field(..., description="ISO‑8601 end time.")
    provider: str = Field(..., description="Staff member / resource name.")


class BookingConfirmation(BaseModel):
    """Confirmation returned after creating a calendar event."""

    booking_id: str = Field(..., description="Unique booking reference.")
    customer: str
    service: str
    start_time: str
    provider: str
    status: str = "confirmed"
    event_link: Optional[str] = Field(
        default=None, description="Google Calendar event link (when available)."
    )


class CustomerRecord(BaseModel):
    """Minimal customer record."""

    customer_id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# In‑memory stores (replace with DB later)
# ═══════════════════════════════════════════════════════════════════════════
_customers: List[CustomerRecord] = []
_bookings: List[BookingConfirmation] = []

# ═══════════════════════════════════════════════════════════════════════════
# FAQ knowledge base (stub)
# ═══════════════════════════════════════════════════════════════════════════
_FAQ_DB: dict[str, str] = {
    "hours": "We are open Monday–Saturday, 9 AM to 7 PM. Closed on Sundays.",
    "opening hours": "We are open Monday–Saturday, 9 AM to 7 PM. Closed on Sundays.",
    "location": "We are located at 123 Main Street, Suite 4, Downtown.",
    "address": "We are located at 123 Main Street, Suite 4, Downtown.",
    "parking": "Free parking is available behind the building.",
    "cancellation": "You can cancel or reschedule free of charge up to 2 hours before your appointment.",
    "cancel": "You can cancel or reschedule free of charge up to 2 hours before your appointment.",
    "reschedule": "You can cancel or reschedule free of charge up to 2 hours before your appointment.",
    "payment": "We accept cash, credit/debit cards, and Apple Pay.",
    "price": "Haircut: $30 | Color: $80 | Massage (60 min): $70 | Consultation: Free.",
    "prices": "Haircut: $30 | Color: $80 | Massage (60 min): $70 | Consultation: Free.",
    "services": "We offer haircuts, coloring, massages, facials, and free consultations.",
    "covid": "All staff are vaccinated. Masks are optional. We sanitise between appointments.",
    "wifi": "Free Wi‑Fi is available. Network: GuestNet, Password: welcome123.",
}


# ═══════════════════════════════════════════════════════════════════════════
# Stub helpers (used when Google Calendar is not configured)
# ═══════════════════════════════════════════════════════════════════════════


def _stub_list_slots(service: str, date_pref: str) -> List[dict]:
    """Generate fake slots (no real calendar)."""
    try:
        base = datetime.fromisoformat(date_pref)
    except ValueError:
        base = datetime.now() + timedelta(days=1)

    providers = ["Alice", "Bob", "Carol"]
    slots = []
    for i, provider in enumerate(providers):
        start = base.replace(hour=9 + i * 2, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
        slots.append(
            Slot(
                slot_id=f"slot-{uuid.uuid4().hex[:8]}",
                start_time=start.isoformat(),
                end_time=end.isoformat(),
                provider=provider,
            ).model_dump()
        )
    return slots


def _stub_create_event(customer: str, service: str, start_time: str) -> dict:
    """Generate a fake booking confirmation."""
    confirmation = BookingConfirmation(
        booking_id=f"BK-{uuid.uuid4().hex[:8].upper()}",
        customer=customer,
        service=service,
        start_time=start_time,
        provider=random.choice(["Alice", "Bob", "Carol"]),
    )
    _bookings.append(confirmation)
    return confirmation.model_dump()


# ═══════════════════════════════════════════════════════════════════════════
# Tool definitions
# ═══════════════════════════════════════════════════════════════════════════


@tool
def calendar_list_slots(service: str, date_pref: str) -> List[dict]:
    """List available appointment slots for a given service and preferred date.

    Use this tool when a customer asks about availability or wants to know
    what times are open for a particular service on a specific date.

    Args:
        service: The service the customer wants (e.g. 'haircut', 'massage').
        date_pref: The customer's preferred date (e.g. '2025-06-04', 'tomorrow').
    """
    logger.info("🔧 calendar_list_slots  service=%s  date=%s", service, date_pref)

    if gcal_client.is_configured():
        try:
            return gcal_client.get_free_slots(service=service, date_pref=date_pref)
        except Exception:
            logger.exception("Google Calendar API failed, falling back to stubs")

    return _stub_list_slots(service, date_pref)


@tool
def calendar_create_event(customer: str, service: str, start_time: str) -> dict:
    """Create a calendar booking for a customer.

    Use this tool after the customer has confirmed a specific time‑slot.
    Returns a booking confirmation with a unique reference ID.

    Args:
        customer: Customer's name.
        service: The service being booked (e.g. 'haircut').
        start_time: ISO‑8601 start time for the appointment.
    """
    logger.info(
        "🔧 calendar_create_event  customer=%s  service=%s  time=%s",
        customer,
        service,
        start_time,
    )

    is_gcal = gcal_client.is_configured()
    try:
        if is_gcal:
            res = gcal_client.create_booking_event(
                customer=customer,
                service=service,
                start_time=start_time,
            )
        else:
            res = _stub_create_event(customer, service, start_time)
    except Exception as exc:
        logger.exception("Calendar client failed to create event")
        raise exc

    booking_id = res["booking_id"]
    event_link = res.get("event_link")

    # Parse start_time to datetime object
    try:
        dt_val = datetime.fromisoformat(start_time)
    except ValueError:
        try:
            dt_val = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except ValueError:
            dt_val = datetime.utcnow()

    # Strip tzinfo for naive local time comparison (in settings timezone context)
    if dt_val.tzinfo:
        dt_val = dt_val.replace(tzinfo=None)

    # Persist to database
    try:
        with get_db_session() as db:
            # Look up customer by exact name or create a placeholder customer record
            db_cust = crud.get_customer_by_name(db, customer)
            if not db_cust:
                logger.info("Customer '%s' not found. Creating placeholder customer.", customer)
                db_cust = crud.create_customer(db, name=customer)

            crud.create_booking(
                db=db,
                booking_id=booking_id,
                customer_id=db_cust.id,
                service=service,
                datetime_val=dt_val,
                calendar_event_id=booking_id if is_gcal else None,
                event_link=event_link,
            )
    except Exception as exc:
        logger.error("DB write failed for booking. Rolling back calendar event %s: %s", booking_id, exc)
        if is_gcal:
            try:
                gcal_client.delete_booking_event(booking_id)
            except Exception as del_exc:
                logger.error("Failed to clean up Google Calendar event %s during rollback: %s", booking_id, del_exc)
        raise exc

    return res


@tool
def db_create_customer(name: str, phone: str = "", email: str = "") -> dict:
    """Register a new customer in the system.

    Use this tool when interacting with a first‑time customer to store their
    contact details for future reference.

    Args:
        name: Customer's full name.
        phone: Phone number (optional).
        email: Email address (optional).
    """
    logger.info("🔧 db_create_customer  name=%s  phone=%s  email=%s", name, phone, email)

    with get_db_session() as db:
        # Check if customer already exists by phone or email
        existing = crud.get_customer_by_phone_or_email(
            db=db,
            phone=phone or None,
            email=email or None,
        )
        if existing:
            logger.info("Customer already exists with ID: %s", existing.id)
            return {
                "customer_id": existing.id,
                "name": existing.name,
                "phone": existing.phone,
                "email": existing.email,
            }

        # Otherwise create a new customer
        cust = crud.create_customer(
            db=db,
            name=name,
            phone=phone or None,
            email=email or None,
        )
        return {
            "customer_id": cust.id,
            "name": cust.name,
            "phone": cust.phone,
            "email": cust.email,
        }


@tool
def db_log_booking(booking_id: str, customer_id: str, notes: str = "") -> str:
    """Log a booking event for audit / CRM purposes.

    Call this after a booking has been confirmed to keep a permanent record.

    Args:
        booking_id: The booking reference (e.g. 'BK-A1B2C3D4').
        customer_id: The customer reference (e.g. 'CUST-A1B2C3D4').
        notes: Any additional notes about the booking.
    """
    logger.info(
        "🔧 db_log_booking  booking=%s  customer=%s  notes=%s",
        booking_id,
        customer_id,
        notes,
    )
    with get_db_session() as db:
        booking = crud.update_booking_notes_and_customer(
            db=db,
            booking_id=booking_id,
            notes=notes,
            customer_id=customer_id,
        )
        if not booking:
            logger.warning("Booking %s not found in DB. Creating dummy booking record.", booking_id)
            # Find customer
            cust = crud.get_customer(db, customer_id)
            if not cust:
                raise ValueError(f"Customer with ID {customer_id} does not exist.")
            crud.create_booking(
                db=db,
                booking_id=booking_id,
                customer_id=customer_id,
                service="haircut",  # Default fallback
                datetime_val=datetime.utcnow(),
                notes=notes,
            )

    return f"Booking {booking_id} for customer {customer_id} logged successfully."


@tool
def faq_lookup(question: str) -> str:
    """Look up an answer from the FAQ knowledge base.

    Use this tool when a customer asks a general question about the business
    such as opening hours, location, prices, cancellation policy, etc.

    Args:
        question: The topic or keyword to look up (e.g. 'hours', 'price', 'parking').
    """
    logger.info("🔧 faq_lookup  question=%s", question)

    q_lower = question.lower().strip()

    # Direct match
    if q_lower in _FAQ_DB:
        return _FAQ_DB[q_lower]

    # Substring match
    for key, answer in _FAQ_DB.items():
        if key in q_lower or q_lower in key:
            return answer

    return (
        "I don't have that information in my FAQ database. "
        "Let me connect you with a staff member who can help."
    )


@tool
def predict_no_show(customer_name: str, service: str, hour_of_day: int) -> dict:
    """Predict the probability that a customer will not show up for their appointment.

    Use this tool internally after booking to flag high‑risk appointments
    so staff can send reminders. Do NOT share the raw probability with the
    customer.

    Args:
        customer_name: Name of the customer.
        service: The booked service.
        hour_of_day: Hour of the appointment (0–23).
    """
    logger.info(
        "🔧 predict_no_show  customer=%s  service=%s  hour=%d",
        customer_name,
        service,
        hour_of_day,
    )

    age = 35  # default baseline age
    days_until_appointment = 1  # default fallback
    past_no_shows = 0  # default fallback
    day_of_week = 0  # default Monday

    try:
        with get_db_session() as db:
            customer = crud.get_customer_by_name(db, customer_name)
            if customer:
                # Count actual no-shows from DB
                from app.db.models import Booking
                past_no_shows = db.query(Booking).filter(
                    Booking.customer_id == customer.id,
                    Booking.status == "no-show"
                ).count()

                # Find the booking we just created to get the gap and day of week
                booking = db.query(Booking).filter(
                    Booking.customer_id == customer.id
                ).order_by(Booking.created_at.desc()).first()

                if booking:
                    tz_now = datetime.now()
                    days_until_appointment = max(0, (booking.datetime.date() - tz_now.date()).days)
                    day_of_week = booking.datetime.weekday()
    except Exception:
        logger.exception("Failed to query DB history in predict_no_show; using stubs/defaults")

    try:
        probability = predict_no_show_prob(
            age=age,
            days_until_appointment=days_until_appointment,
            past_no_shows=past_no_shows,
            appointment_hour=hour_of_day,
            day_of_week=day_of_week,
        )
    except Exception:
        logger.exception("ML prediction failed; using default probability fallback")
        probability = 0.15

    risk = "high" if probability > 0.3 else "medium" if probability > 0.15 else "low"

    return {
        "customer_name": customer_name,
        "service": service,
        "no_show_probability": probability,
        "risk_level": risk,
    }


# ═══════════════════════════════════════════════════════════════════════════
# All tools list — import this in agent.py
# ═══════════════════════════════════════════════════════════════════════════
ALL_TOOLS = [
    calendar_list_slots,
    calendar_create_event,
    db_create_customer,
    db_log_booking,
    faq_lookup,
    predict_no_show,
]

