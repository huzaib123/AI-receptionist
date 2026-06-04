"""
SQLAlchemy models for the CRM/analytics backend.
"""

from __future__ import annotations

import datetime as dt_module
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class Customer(Base):
    """
    Customer record storing contact details and metadata.
    """
    __tablename__ = "customers"

    id = Column(String(50), primary_key=True)  # CUST-XXXXXXXX
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=dt_module.datetime.utcnow, nullable=False)

    # Relationships
    bookings = relationship(
        "Booking",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id} name={self.name}>"


class Booking(Base):
    """
    Booking record representing calendar appointments.
    """
    __tablename__ = "bookings"

    id = Column(String(50), primary_key=True)  # BK-XXXXXXXX or Google Calendar event_id
    customer_id = Column(String(50), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    service = Column(String(100), nullable=False)
    datetime = Column(DateTime, nullable=False, index=True)  # Naive local time in business timezone
    status = Column(String(50), default="confirmed", nullable=False)  # confirmed, cancelled, no-show, completed
    source = Column(String(50), default="chat", nullable=False)  # chat, manual, web
    calendar_event_id = Column(String(255), nullable=True)
    event_link = Column(String(1024), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=dt_module.datetime.utcnow, nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="bookings")

    def __repr__(self) -> str:
        return f"<Booking id={self.id} customer_id={self.customer_id} service={self.service} datetime={self.datetime}>"
