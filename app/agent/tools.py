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
from zoneinfo import ZoneInfo

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.integrations.google_calendar import gcal_client
from app.db.session import get_db_session
from app.db import crud
from app.ml.no_show_model import predict_no_show_prob
from app.core.business_profile import get_business_profile
from app.core.settings import settings

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


MAX_NAME_LENGTH = 80
MAX_PHONE_LENGTH = 32
MAX_BOOKING_DAYS_AHEAD = 60


def _parse_local_time(start_time: str) -> Optional[datetime]:
    """Read an ISO-8601 time as business-local wall time (any offset is dropped)."""
    try:
        dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt.replace(tzinfo=None)


def _check_booking_request(customer: str, service: str, start_time: str, phone: str):
    """Return (problem, local_datetime). problem is None when the booking is allowed."""
    if not customer.strip() or len(customer) > MAX_NAME_LENGTH:
        return "Please give a name of up to 80 characters.", None
    if not service.strip() or len(service) > MAX_NAME_LENGTH:
        return "Please choose one of the listed services.", None
    if len(phone) > MAX_PHONE_LENGTH:
        return "That phone number doesn't look right.", None
    dt = _parse_local_time(start_time)
    if dt is None:
        return "That time couldn't be read. Please pick one of the offered slots.", None
    now = datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).replace(tzinfo=None)
    if dt <= now:
        return "That time has already passed. Please pick a future slot.", None
    if dt > now + timedelta(days=MAX_BOOKING_DAYS_AHEAD):
        return f"Bookings can be made up to {MAX_BOOKING_DAYS_AHEAD} days ahead.", None
    if (dt.weekday() not in settings.BUSINESS_DAYS
            or not settings.BUSINESS_HOURS_START <= dt.hour < settings.BUSINESS_HOURS_END):
        return "That time is outside opening hours.", None
    with get_db_session() as db:
        if crud.booking_exists_at(db, dt):
            return "That slot was just taken. Please pick another one.", None
    return None, dt


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
    """Open slots for a service. date_pref: YYYY-MM-DD."""
    logger.info("🔧 calendar_list_slots  service=%s  date=%s", service, date_pref)

    if gcal_client.is_configured():
        try:
            return gcal_client.get_free_slots(service=service, date_pref=date_pref)
        except Exception:
            logger.exception("Google Calendar API failed, falling back to stubs")

    return _stub_list_slots(service, date_pref)


@tool
def calendar_create_event(customer: str, service: str, start_time: str, phone: str = "") -> dict:
    """Book a confirmed slot. start_time: ISO-8601. Saves the customer too."""
    logger.info(
        "🔧 calendar_create_event  customer=%s  service=%s  time=%s",
        customer,
        service,
        start_time,
    )

    # The model's arguments come from a public chat, so they are checked here
    # rather than trusted: a bot or a crafted message must not be able to fill
    # the calendar with junk, past or out-of-hours bookings.
    problem, dt_val = _check_booking_request(customer, service, start_time, phone)
    if problem:
        return {"status": "rejected", "reason": problem}

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

    # Persist to database
    try:
        with get_db_session() as db:
            # Find the customer by phone, then by exact name, else register them.
            db_cust = crud.get_customer_by_phone_or_email(db, phone=phone or None, email=None) if phone else None
            db_cust = db_cust or crud.get_customer_by_name(db, customer)
            if not db_cust:
                logger.info("Customer '%s' not found. Creating customer record.", customer)
                db_cust = crud.create_customer(db, name=customer, phone=phone or None)

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

    # No-show check runs here rather than as a separate agent step, which
    # would cost another full LLM round trip. Only the flag reaches the model.
    try:
        risk = predict_no_show.func(customer, service, dt_val.hour)["risk_level"]
    except Exception:
        logger.exception("No-show prediction failed during booking")
        risk = "low"
    return {**res, "send_reminder": risk == "high"}


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
    logger.info("🔧 db_create_customer  has_phone=%s  has_email=%s", bool(phone), bool(email))

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
    """Look up a business FAQ by keyword, e.g. 'parking', 'payment'."""
    logger.info("🔧 faq_lookup  question=%s", question)

    q_lower = question.lower().strip()
    kb = get_business_profile().knowledge_base()

    # Direct match
    if q_lower in kb:
        return kb[q_lower]

    # Substring match
    for key, answer in kb.items():
        if key in q_lower or q_lower in key:
            return answer

    return (
        "I don't have that information in my FAQ database. "
        "Let me connect you with a staff member who can help."
    )


@tool
def handoff_to_human(reason: str, customer_name: str = "") -> dict:
    """Get a WhatsApp link to staff. reason: short summary of the need."""
    logger.info("🔧 handoff_to_human  reason=%s  customer=%s", reason, customer_name)

    profile = get_business_profile()
    who = f"I'm {customer_name}. " if customer_name else ""
    link = profile.whatsapp_link(f"Hi {profile.name}, {who}{reason}")
    return {
        "whatsapp_link": link,
        "phone": profile.phone or None,
    }


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
# Tool lists
# ═══════════════════════════════════════════════════════════════════════════
# Every tool definition, kept for tests and direct use.
ALL_TOOLS = [
    calendar_list_slots,
    calendar_create_event,
    db_create_customer,
    db_log_booking,
    faq_lookup,
    predict_no_show,
    handoff_to_human,
]

# The lean set the agent sees. Each tool schema is resent on every LLM call,
# and every tool step costs another full round trip, so customer records and
# the no-show check happen inside calendar_create_event, and FAQ answers are
# placed in the system prompt (faq_lookup is added back only for a large FAQ).
AGENT_TOOLS = [
    calendar_list_slots,
    calendar_create_event,
    handoff_to_human,
]
